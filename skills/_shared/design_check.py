"""The check of the computation: what the code looks at, the record, its reader (ADR-0070).

A check tells whether the notebook computed what its design says. The code
decides three subjects here, from the design, the verdict and the notebook: the
metrics, the figures and the order of the cells. A reader (a check agent, or the
same session) answers the others and ``record_check`` takes them as given.

``check_reading`` is the one place that tells whether the check of a design is
done: the analysis note, the tree page and the skills all read it from here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAMLError

from insight_blueprint.models.check import (
    CODE_SUBJECTS,
    CheckItem,
    CheckResult,
    CheckSubject,
    DesignCheck,
    design_digest,
    verdict_digest,
)
from insight_blueprint.models.design import AnalysisDesign
from insight_blueprint.validate import validate_schema
from skills._shared._atomic import atomic_write_yaml, write_lock
from skills._shared.design_io import DEFAULT_BASE_DIR, load_design, read_yaml
from skills._shared.ids import SAFE_ID_PATTERN
from skills._shared.notebook_files import (
    CONTRACT_CELLS,
    notebook_cells,
    notebook_path,
    notebooks_dir,
    parse_verdict,
    read_own_bytes,
    read_own_text,
    verdict_figures,
    verdict_metrics,
    verdict_path,
)

# The cells a difference the code finds is read in: the metrics are named where
# ``results`` is built, the figures where they are saved.
_METRICS_CELL = "analysis"
_FIGURES_CELL = "viz"


def _named(names: list[str]) -> str:
    return "".join(f"「{name}」" for name in names)


def _metrics_item(design: AnalysisDesign, verdict: dict) -> CheckItem:
    """A metric is the same one when the verdict names it by the design's ``target``."""
    designed = list(dict.fromkeys(metric.target for metric in design.metrics))
    written = [name for name, _ in verdict_metrics(verdict)]
    missing = [name for name in designed if name not in written]
    added = [name for name in written if name not in designed]
    if not missing and not added:
        return CheckItem(subject=CheckSubject.metrics, result=CheckResult.agrees)
    note = ""
    if missing:
        note += (
            f"分析設計の指標{_named(missing)}が、"
            "分析コードの出した結果に同じ名前で無い。"
        )
    if added:
        note += f"分析コードの出した結果の指標{_named(added)}が、分析設計に無い。"
    return CheckItem(
        subject=CheckSubject.metrics,
        result=CheckResult.differs,
        note=note,
        cell=_METRICS_CELL,
    )


def _figures_item(design: AnalysisDesign, verdict: dict, notebooks: Path) -> CheckItem:
    # A figure the note cannot show is not one the notebook drew.
    drawn = len(verdict_figures(verdict, notebooks))
    specified = len(design.chart)
    if drawn == specified:
        return CheckItem(subject=CheckSubject.figures, result=CheckResult.agrees)
    return CheckItem(
        subject=CheckSubject.figures,
        result=CheckResult.differs,
        note=(
            f"分析コードの出した図は {drawn} 枚、分析設計の図の仕様は {specified} 枚。"
        ),
        cell=_FIGURES_CELL,
    )


def _cells_item(notebook: str | None) -> CheckItem:
    if notebook is None:
        return CheckItem(
            subject=CheckSubject.cells,
            result=CheckResult.not_checkable,
            note="分析コードのファイルが無いか、読めない。",
        )
    # The cut of the analysis note is the one reading of the contract's shape.
    if notebook_cells(notebook) is not None:
        return CheckItem(subject=CheckSubject.cells, result=CheckResult.agrees)
    return CheckItem(
        subject=CheckSubject.cells,
        result=CheckResult.differs,
        note=(
            "分析コードの区切りが、決まりの7つ"
            f"（{'、'.join(CONTRACT_CELLS)}）の並びになっていない。"
        ),
    )


def code_items(
    design: AnalysisDesign, verdict: dict, notebook: str | None, notebooks: Path
) -> list[CheckItem]:
    """The subjects the code decides (``CODE_SUBJECTS``), from what is on file.

    *notebook* is the text of the notebook, or None when there is none to read;
    *notebooks* is the folder that holds the figures the verdict lists. The
    metrics and the figures are those the analysis note shows (``notebook_files``).
    """
    return [
        _metrics_item(design, verdict),
        _figures_item(design, verdict, notebooks),
        _cells_item(notebook),
    ]


@dataclass(frozen=True)
class CheckReading:
    """Whether the check of one design is done for its verdict as it is now.

    ``check_reading`` and ``record_check`` are its only makers. *check* is the
    record only when it remembers this very verdict and the design as it reads
    now; a check of another verdict or design says nothing of these, so it is
    not held.
    """

    design_id: str
    has_verdict: bool
    verdict_digest: str | None  # the name of the verdict there now; None without one
    check: DesignCheck | None = None

    @property
    def checked(self) -> bool:
        return self.check is not None


def _record_path(design_id: str, base_dir: Path) -> Path:
    return Path(base_dir) / "designs" / f"{design_id}_check.yaml"


def _reader_items(payload: dict) -> list[CheckItem]:
    """The items of the reader; the subjects of the code are refused.

    Which subjects a check holds for its design is the rule of ``DesignCheck``.
    """
    given = payload.get("items")
    if not isinstance(given, list):
        raise ValueError("items: give the list of the subjects the reader checked")
    items = [CheckItem.model_validate(item) for item in given]
    of_the_code = [i.subject.value for i in items if i.subject in CODE_SUBJECTS]
    if of_the_code:
        raise ValueError(
            f"items: {', '.join(of_the_code)} are decided by design_io check itself; "
            "leave them out"
        )
    return items


def record_check(
    design_id: str, payload: dict, base_dir: Path = DEFAULT_BASE_DIR
) -> CheckReading:
    """Write the check of *design_id* for its verdict as it is now; return its reading.

    *payload* holds ``checked_by`` and the ``items`` a reader answered. The
    subjects of the code are decided here, at the moment of the write. The
    record replaces an earlier one. Neither the design nor its journal is
    written. Raises ValueError, and writes nothing, when the design or its
    verdict is missing or the items are not the ones a reader answers.
    """
    if not isinstance(payload, dict):
        raise ValueError("payload: give a JSON object with checked_by and items")
    with write_lock(base_dir):
        data = load_design(design_id, base_dir)
        if not data:
            raise ValueError(f"Design '{design_id}' not found")
        design = validate_schema(data)
        where = verdict_path(design_id, base_dir)
        verdict_bytes = read_own_bytes(where)
        if verdict_bytes is None:
            raise ValueError(
                f"{design_id} has no verdict: there is no computation to check yet"
            )
        verdict = parse_verdict(verdict_bytes, where.name)
        digest = verdict_digest(verdict_bytes)
        # The notebook writes its verdict outside this lock, so the reader may
        # have read an earlier one: its answers are taken only for this verdict.
        read = payload.get("verdict_digest")
        if not read:
            raise ValueError(
                "verdict_digest: name the verdict the reader read, as "
                "design_io checked gave it before the reading"
            )
        if read != digest:
            raise ValueError(
                f"the verdict of {design_id} changed since it was read "
                "(verdict_digest differs): read it again, then check"
            )
        items = [
            *_reader_items(payload),
            *code_items(
                design,
                verdict,
                read_own_text(notebook_path(design_id, base_dir)),
                notebooks_dir(base_dir),
            ),
        ]
        order = list(CheckSubject)
        check = DesignCheck.model_validate(
            {
                "design_id": design_id,
                "verdict_digest": digest,
                "design_digest": design_digest(data),
                "checked_by": payload.get("checked_by"),
                "items": sorted(items, key=lambda item: order.index(item.subject)),
                "judges": design.form().judges,
            }
        )
        record = check.model_dump(mode="json") | {
            "items": [_item(item) for item in check.items]
        }
        atomic_write_yaml(_record_path(design_id, base_dir), record)
        return _reading(design_id, verdict_bytes, data, check)


def _item(item: CheckItem) -> dict[str, Any]:
    return item.model_dump(mode="json", exclude_defaults=True)


def reading_json(reading: CheckReading) -> dict[str, Any]:
    """*reading* as ``design_io checked`` and ``design_io check`` print it."""
    check = reading.check
    return {
        "design_id": reading.design_id,
        "has_verdict": reading.has_verdict,
        "verdict_digest": reading.verdict_digest,
        "checked": reading.checked,
        "checked_by": check.checked_by.value if check else None,
        "items": [_item(i) for i in check.items] if check else [],
        "differences": [_item(i) for i in check.differences()] if check else [],
    }


def _reading(
    design_id: str,
    verdict: bytes | None,
    design: dict | None,
    check: DesignCheck | None,
) -> CheckReading:
    """*design* is the file of the design as read; None when it does not read."""
    done = (
        check is not None
        and verdict is not None
        and design is not None
        and check.is_current(verdict, design)
    )
    return CheckReading(
        design_id=design_id,
        has_verdict=verdict is not None,
        verdict_digest=None if verdict is None else verdict_digest(verdict),
        # A check of another verdict or design says nothing of these, so none of it is shown.
        check=check if done else None,
    )


def check_reading(design_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> CheckReading:
    """Whether the check of *design_id* is done for its verdict as it is now.

    The reading holds the check only when a record exists and remembers this
    very verdict and the design as it reads now. A design without a verdict has
    nothing to check (``has_verdict`` false). A record, a design or a verdict
    that does not read is no check.
    """
    if not SAFE_ID_PATTERN.fullmatch(design_id):
        raise ValueError(f"Invalid design_id '{design_id}': must match [a-zA-Z0-9_-]+")
    try:
        check = DesignCheck.model_validate(read_yaml(_record_path(design_id, base_dir)))
    # Not UTF-8 and a wrong shape are ValueErrors; a folder in its place is an OSError.
    except (ValueError, YAMLError, OSError):
        check = None
    # A record copied from another design is not the check of this one.
    if check is not None and check.design_id != design_id:
        check = None
    try:
        design = load_design(design_id, base_dir)
    except (ValueError, YAMLError, OSError):
        design = None
    try:
        verdict = read_own_bytes(verdict_path(design_id, base_dir))
    # The verdict is there and does not read: there is one, and no check of it is known.
    except OSError:
        return CheckReading(design_id=design_id, has_verdict=True, verdict_digest=None)
    return _reading(design_id, verdict, design, check)
