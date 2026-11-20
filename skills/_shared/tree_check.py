"""Check the current answers of a question tree against the journal (Epic 18, ADR-0025).

An answer may only state a number that a cited journal event records, and may
only cite events that exist. This module only reads: it never writes the tree.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

_NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")


@dataclass(frozen=True)
class Number:
    token: str
    value: Decimal


def numbers_in(text: str) -> list[Number]:
    """Numbers in *text*, compared by value: unit, sign and spelling do not count.

    A converted or rounded value is a different number, so an answer cannot pass
    by computing one.
    """
    return [
        Number(m.group(), Decimal(m.group().replace(",", "")))
        for m in _NUMBER.finditer(unicodedata.normalize("NFKC", text))
    ]
