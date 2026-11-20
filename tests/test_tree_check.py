"""Tests for tree_check, the read-only check of cited answers (Epic 18, Story 18.3).

The check exists to stop #105: a number in an answer that no journal record holds.
Synthetic data only (public-library holds, theme LIB).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from skills._shared.tree_check import numbers_in


def values(text: str) -> list[Decimal]:
    return [n.value for n in numbers_in(text)]


class TestNumbersIn:
    def test_a_text_without_digits_has_no_numbers(self) -> None:
        assert numbers_in("取消を除いて比べた") == []

    def test_a_number_keeps_the_token_as_written_and_its_value(self) -> None:
        (found,) = numbers_in("およそ1.90倍")
        assert (found.token, found.value) == ("1.90", Decimal("1.9"))

    def test_numbers_come_in_order_of_appearance(self) -> None:
        assert values("152件と80件") == [Decimal(152), Decimal(80)]

    def test_full_width_forms_equal_the_ascii_forms(self) -> None:
        assert values("３４．６％") == values("34.6%") == [Decimal("34.6")]

    def test_the_token_is_kept_after_normalization(self) -> None:
        assert [n.token for n in numbers_in("１，２３４．５")] == ["1,234.5"]

    def test_a_thousands_separator_is_removed(self) -> None:
        assert values("1,234件") == [Decimal(1234)]

    def test_a_comma_that_is_not_a_thousands_separator_splits_the_number(self) -> None:
        assert values("12,5") == [Decimal(12), Decimal(5)]

    def test_values_compare_by_value_not_by_spelling(self) -> None:
        assert values("1.90") == values("1.9")
        assert values("01") == values("1")

    @pytest.mark.parametrize(
        "text", ["34.6%", "34.6％", "34.6 %", "34.6パーセント", "34.6件"]
    )
    def test_the_unit_is_ignored(self, text: str) -> None:
        assert values(text) == [Decimal("34.6")]

    def test_a_converted_value_is_a_different_number(self) -> None:
        assert values("0.346") != values("34.6")

    def test_a_rounded_value_is_a_different_number(self) -> None:
        assert values("35") != values("34.6")

    def test_the_sign_is_ignored(self) -> None:
        assert values("-3.2") == [Decimal("3.2")]

    def test_a_number_is_a_whole_token_never_a_substring(self) -> None:
        assert Decimal("1.9") not in values("21.95")
        assert Decimal(5) not in values("152")

    def test_nothing_is_exempt_for_looking_like_an_id_or_a_date(self) -> None:
        assert values("LIB-H01-E02は2026年11月21日") == [
            Decimal(1),
            Decimal(2),
            Decimal(2026),
            Decimal(11),
            Decimal(21),
        ]
