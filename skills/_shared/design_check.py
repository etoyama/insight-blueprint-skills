"""The check of the computation: what the code looks at, the record, its reader (ADR-0070).

A check tells whether the notebook computed what its design says. The code
decides three subjects here, from the design, the verdict and the notebook: the
metrics, the figures and the order of the cells. A reader (a check agent, or the
same session) answers the others and ``record_check`` takes them as given.

``check_reading`` is the one place that tells whether the check of a design is
done: the analysis note, the tree page and the skills all read it from here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from ruamel.yaml import YAMLError

from insight_blueprint.models.check import (
    CODE_SUBJECTS,
    CheckItem,
    CheckResult,
    CheckSubject,
    DesignCheck,
    verdict_digest,
)
from insight_blueprint.models.design import AnalysisDesign
from insight_blueprint.validate import validate_schema
from skills._shared._atomic import atomic_write_yaml, write_lock
from skills._shared.design_io import DEFAULT_BASE_DIR, load_design, read_yaml
from skills._shared.design_note_read import CONTRACT_CELLS, notebook_cells

# The cells a difference the code finds is read in: the metrics are named where
# ``results`` is built, the figures where they are saved.
_METRICS_CELL = "analysis"
_FIGURES_CELL = "viz"


def _named(names: list[str]) -> str:
    return "".join(f"「{name}」" for name in names)


def _metrics_item(design: AnalysisDesign, verdict: dict) -> CheckItem:
    """A metric is the same one when the verdict names it by the design's ``target``."""
    designed = list(dict.fromkeys(metric.target for metric in design.metrics))
    metrics = verdict.get("metrics")
    written = list(metrics) if isinstance(metrics, dict) else []
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


def _figures_item(design: AnalysisDesign, verdict: dict) -> CheckItem:
    figures = verdict.get("figures")
    drawn = len(figures) if isinstance(figures, list) else 0
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
    design: AnalysisDesign, verdict: dict, notebook: str | None
) -> list[CheckItem]:
    """The subjects the code decides (``CODE_SUBJECTS``), from what is on file.

    *notebook* is the text of the notebook, or None when there is none to read.
    """
    return [
        _metrics_item(design, verdict),
        _figures_item(design, verdict),
        _cells_item(notebook),
    ]


def _record_path(design_id: str, base_dir: Path) -> Path:
    return Path(base_dir) / "designs" / f"{design_id}_check.yaml"


def _own_bytes(path: Path) -> bytes | None:
    # A link is not read, as the analysis note does not read one.
    return None if path.is_symlink() or not path.is_file() else path.read_bytes()


def _verdict_bytes(design_id: str, base_dir: Path) -> bytes | None:
    return _own_bytes(Path(base_dir) / "notebooks" / f"{design_id}_verdict.json")


def _notebook_text(design_id: str, base_dir: Path) -> str | None:
    source = _own_bytes(Path(base_dir) / "notebooks" / f"{design_id}.py")
    try:
        return None if source is None else source.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


def _reader_items(payload: dict, design: AnalysisDesign) -> list[CheckItem]:
    """The items of the reader, held to the subjects a reader answers for *design*."""
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
    has_criterion = any(i.subject is CheckSubject.criterion for i in items)
    judges = design.form().judges
    if has_criterion and not judges:
        raise ValueError(
            "items: criterion is checked only for a design that judges a hypothesis"
        )
    if judges and not has_criterion:
        raise ValueError("items: not checked: criterion")
    return items


def record_check(
    design_id: str, payload: dict, base_dir: Path = DEFAULT_BASE_DIR
) -> dict[str, Any]:
    """Write the check of *design_id* for its verdict as it is now; return its reading.

    *payload* holds ``checked_by`` and the ``items`` a reader answered. The
    subjects of the code are decided here, at the moment of the write. The
    record replaces an earlier one. Neither the design nor its journal is
    written. Raises ValueError, and writes nothing, when the design or its
    verdict is missing or the items are not the ones a reader answers.
    """
    with write_lock(base_dir):
        data = load_design(design_id, base_dir)
        if not data:
            raise ValueError(f"Design '{design_id}' not found")
        design = validate_schema(data)
        verdict_bytes = _verdict_bytes(design_id, base_dir)
        if verdict_bytes is None:
            raise ValueError(
                f"{design_id} has no verdict: there is no computation to check yet"
            )
        try:
            verdict = json.loads(verdict_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(
                f"{design_id}_verdict.json is not valid JSON: {exc}"
            ) from None
        if not isinstance(verdict, dict):
            raise ValueError(f"{design_id}_verdict.json must hold a JSON object")
        items = [
            *_reader_items(payload, design),
            *code_items(design, verdict, _notebook_text(design_id, base_dir)),
        ]
        order = list(CheckSubject)
        check = DesignCheck.model_validate(
            {
                "design_id": design_id,
                "verdict_digest": verdict_digest(verdict_bytes),
                "checked_by": payload.get("checked_by"),
                "items": sorted(items, key=lambda item: order.index(item.subject)),
            }
        )
        record = check.model_dump(mode="json") | {
            "items": [_item(item) for item in check.items]
        }
        atomic_write_yaml(_record_path(design_id, base_dir), record)
        return _reading(design_id, verdict_bytes, check)


def _item(item: CheckItem) -> dict[str, Any]:
    return item.model_dump(mode="json", exclude_defaults=True)


def _reading(
    design_id: str, verdict: bytes | None, check: DesignCheck | None
) -> dict[str, Any]:
    done = check is not None and verdict is not None and check.is_current(verdict)
    # A check of another verdict says nothing of this one, so none of it is shown.
    shown = check if done else None
    return {
        "design_id": design_id,
        "has_verdict": verdict is not None,
        "checked": done,
        "checked_by": shown.checked_by.value if shown else None,
        "items": [_item(i) for i in shown.items] if shown else [],
        "differences": [_item(i) for i in shown.differences()] if shown else [],
    }


def check_reading(design_id: str, base_dir: Path = DEFAULT_BASE_DIR) -> dict[str, Any]:
    """Whether the check of *design_id* is done for its verdict as it is now.

    ``checked`` is true only when a record exists and remembers this very
    verdict; then ``items`` holds every subject and ``differences`` the ones
    that differ. A design without a verdict has nothing to check
    (``has_verdict`` false). A record that does not read is no check.
    """
    # Validates the id before it reaches a path.
    load_design(design_id, base_dir)
    try:
        check = DesignCheck.model_validate(read_yaml(_record_path(design_id, base_dir)))
    except (ValidationError, YAMLError):
        check = None
    # A record copied from another design is not the check of this one.
    if check is not None and check.design_id != design_id:
        check = None
    return _reading(design_id, _verdict_bytes(design_id, base_dir), check)
