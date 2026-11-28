"""The record of a check of the computation (Epic 36, Story 36.4, ADR-0070).

US-4 AC 1: one result per subject, and a difference holds what differs and the
cell it was read in. US-4 AC 5: the record remembers the verdict it checked.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from insight_blueprint.models.check import (
    CODE_SUBJECTS,
    CheckedBy,
    CheckItem,
    CheckResult,
    CheckSubject,
    DesignCheck,
    verdict_digest,
)

EVERY_SUBJECT = [
    "population",
    "grain",
    "denominator",
    "extraction",
    "metrics",
    "compared_against",
    "figures",
    "criterion",
    "cells",
]


def _items(*, without: tuple[str, ...] = (), **results: dict) -> list[dict]:
    return [
        {"subject": subject, "result": "agrees"} | results.get(subject, {})
        for subject in EVERY_SUBJECT
        if subject not in without
    ]


def _check(items: list[dict] | None = None, **fields: object) -> DesignCheck:
    return DesignCheck.model_validate(
        {
            "design_id": "LIB-H01",
            "verdict_digest": verdict_digest(b"{}"),
            "checked_by": "check_agent",
            "items": _items() if items is None else items,
        }
        | fields
    )


class TestTheSubjectsAndResultsAreTheOnesOfTheDecision:
    def test_the_subjects_are_the_nine(self) -> None:
        assert [s.value for s in CheckSubject] == EVERY_SUBJECT

    def test_a_result_is_one_of_three(self) -> None:
        assert [r.value for r in CheckResult] == ["agrees", "differs", "not_checkable"]

    def test_the_code_looks_at_metrics_figures_and_cells(self) -> None:
        assert set(CODE_SUBJECTS) == {
            CheckSubject.metrics,
            CheckSubject.figures,
            CheckSubject.cells,
        }

    def test_a_check_is_read_by_a_check_agent_or_the_same_session(self) -> None:
        assert [c.value for c in CheckedBy] == ["check_agent", "same_session"]


class TestADifferenceSaysWhatDiffersAndWhere:
    def test_an_item_that_agrees_needs_nothing_more(self) -> None:
        item = CheckItem.model_validate({"subject": "grain", "result": "agrees"})
        assert item.note == "" and item.cell is None

    def test_a_difference_without_a_note_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="note"):
            CheckItem.model_validate(
                {"subject": "grain", "result": "differs", "cell": "data_prep"}
            )

    def test_a_difference_with_a_blank_note_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="note"):
            CheckItem.model_validate(
                {
                    "subject": "grain",
                    "result": "differs",
                    "note": "  ",
                    "cell": "data_prep",
                }
            )

    def test_a_difference_without_a_cell_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="cell"):
            CheckItem.model_validate(
                {"subject": "grain", "result": "differs", "note": "per visit"}
            )

    def test_a_difference_in_the_order_of_the_cells_names_no_one_cell(self) -> None:
        item = CheckItem.model_validate(
            {"subject": "cells", "result": "differs", "note": "six cells"}
        )
        assert item.cell is None

    def test_an_item_not_checkable_says_why(self) -> None:
        with pytest.raises(ValidationError, match="note"):
            CheckItem.model_validate({"subject": "grain", "result": "not_checkable"})


class TestACheckHoldsEachSubjectOnce:
    def test_all_nine_make_a_check(self) -> None:
        assert [i.subject.value for i in _check().items] == EVERY_SUBJECT

    def test_a_check_without_the_criterion_is_one_of_an_exploration(self) -> None:
        check = _check(_items(without=("criterion",)))
        assert CheckSubject.criterion not in {i.subject for i in check.items}

    @pytest.mark.parametrize("missing", [s for s in EVERY_SUBJECT if s != "criterion"])
    def test_any_other_subject_left_out_is_refused(self, missing: str) -> None:
        with pytest.raises(ValidationError, match=missing):
            _check(_items(without=(missing,)))

    def test_a_subject_given_twice_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="grain"):
            _check([*_items(), {"subject": "grain", "result": "agrees"}])

    def test_who_checked_is_required(self) -> None:
        with pytest.raises(ValidationError, match="checked_by"):
            DesignCheck.model_validate(
                {
                    "design_id": "LIB-H01",
                    "verdict_digest": verdict_digest(b"{}"),
                    "items": _items(),
                }
            )


class TestTheDifferencesAreTheItemsThatDiffer:
    def test_a_check_where_all_agree_has_none(self) -> None:
        assert _check().differences() == []

    def test_only_the_items_that_differ_are_differences(self) -> None:
        check = _check(
            _items(
                grain={"result": "differs", "note": "per visit", "cell": "data_prep"},
                population={"result": "not_checkable", "note": "no data_scope"},
            )
        )
        assert [d.subject for d in check.differences()] == [CheckSubject.grain]


class TestACheckRemembersTheVerdictItChecked:
    def test_the_digest_names_the_bytes_of_the_verdict(self) -> None:
        assert verdict_digest(b'{"a": 1}') == verdict_digest(b'{"a": 1}')
        assert verdict_digest(b'{"a": 1}') != verdict_digest(b'{"a": 2}')
        assert verdict_digest(b"{}").startswith("sha256:")

    def test_it_is_current_for_the_verdict_it_checked(self) -> None:
        assert _check().is_current(b"{}")

    def test_it_is_not_current_once_the_verdict_changed(self) -> None:
        assert not _check().is_current(b'{"metrics": {}}')
