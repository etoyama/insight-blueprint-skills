"""Verdicts in the shapes a project may have saved before Epic 33 (ADR-0052).

A saved verdict must read as it did before: the reader, the analysis note and
the report all take these texts. Each is written by hand, because ``json.dumps``
would drop the trailing zeros a notebook wrote. ``SAVED_VERDICTS`` maps a name
to ``(analysis_intent, verdict text)``; an intent of None is a design saved
without one.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from skills._shared import design_io
from skills._shared._atomic import atomic_write_yaml

# A verdict written before the contract asked for metrics.
NO_METRICS = '{"conclusion": "期限切れは減った", "evidence_summary": ["減った"]}'

# "p" came before "p_value"; a verdict may hold either, or both.
P_AND_P_VALUE = """{
  "metrics": {
    "旧い p": {"value": 1.80, "p": 0.040},
    "契約の p_value": {"value": 1.80, "p_value": 0.030},
    "両方": {"value": 1.80, "p": 0.040, "p_value": 0.030}
  }
}"""

# Before ADR-0013 a metric held no optional item; a partial item reads as absent.
OPTIONAL_ITEMS = """{
  "metrics": {
    "任意の項目なし": {"value": 0.346, "threshold": 0.050, "pass": true},
    "欠けた項目": {
      "value": 1,
      "effect_size": {"value": 0.30},
      "confidence_interval": {"level": 0.95, "lower": 0.10}
    },
    "そろった項目": {
      "value": 0.00010,
      "threshold": 0.050,
      "p": 1e-05,
      "pass": true,
      "effect_size": {"kind": "cohens_d", "value": 0.30},
      "confidence_interval": {"level": 0.95, "lower": 0.10, "upper": 0.50},
      "sample_size": 1520
    }
  }
}"""

# Before ADR-0050 an exploration could carry a threshold and a pass.
EXPLORATION_WITH_A_PASS = """{
  "metrics": {
    "待ち日数の差": {
      "value": 1.80,
      "threshold": 1.0,
      "pass": true,
      "confidence_interval": {"level": 0.95, "lower": 0.40, "upper": 3.20},
      "sample_size": 840
    }
  }
}"""

THRESHOLD_KINDS = """{
  "metrics": {
    "数": {"value": 2.10, "threshold": 2.0, "pass": true},
    "文字": {"value": 2.10, "threshold": "2.0 日以上", "pass": true},
    "その他の JSON": {"value": 2.10, "threshold": {"min": 1.0, "max": [2.0, NaN]}}
  }
}"""

PASS_NOT_A_BOOLEAN = """{
  "metrics": {
    "文字の合否": {"value": 2.10, "threshold": 2.0, "pass": "yes"},
    "数の合否": {"value": 2.10, "threshold": 2.0, "pass": 1},
    "null の合否": {"value": 2.10, "threshold": 2.0, "pass": null}
  }
}"""

# The shape of the FRN verdicts of ib-notebook: a guardrail holds only a pass.
PRIMARY_AND_GUARDRAIL = """{
  "conclusion": "相関は弱い",
  "metrics": {
    "rho": {
      "value": 0.62,
      "threshold": 0.70,
      "pass": true,
      "confidence_interval": {"level": 0.95, "lower": 0.51, "upper": 0.69},
      "sample_size": 412
    },
    "欠損の検査": {"pass": true}
  }
}"""

SAVED_VERDICTS: dict[str, tuple[str | None, str]] = {
    "no_metrics": ("confirmatory", NO_METRICS),
    "p_and_p_value": ("confirmatory", P_AND_P_VALUE),
    "optional_items": ("confirmatory", OPTIONAL_ITEMS),
    "exploration_with_a_pass": ("exploratory", EXPLORATION_WITH_A_PASS),
    "threshold_kinds": ("confirmatory", THRESHOLD_KINDS),
    "pass_not_a_boolean": ("confirmatory", PASS_NOT_A_BOOLEAN),
    "mixed_design": ("mixed", PRIMARY_AND_GUARDRAIL),
    "design_without_an_intent": (None, PRIMARY_AND_GUARDRAIL),
}

_PRIMARY_AND_GUARDRAIL_ROWS = [
    ["指標", "値", "区間", "N", "しきい値", "合否"],
    ["rho", "0.62", "信頼区間 水準 0.95: [0.51, 0.69]", "412", "0.70", "✓"],
    ["欠損の検査", "—", "—", "—", "—", "✓"],
]

# The rows of the note's metric table for each saved verdict, header first. None:
# the note has no table. The values are those the code before Epic 33 laid out
# (main 09fc48a); the columns no metric fills are left out and the interval names
# its kind (ADR-0052 8), as Story 33.2 reads US-1 AC 5.
NOTE_TABLES: dict[str, list[list[str]] | None] = {
    "no_metrics": None,
    "p_and_p_value": [
        ["指標", "値", "p"],
        ["旧い p", "1.80", "0.040"],
        ["契約の p_value", "1.80", "0.030"],
        ["両方", "1.80", "0.040"],
    ],
    "optional_items": [
        ["指標", "値", "効果量", "区間", "N", "しきい値", "p", "合否"],
        ["任意の項目なし", "0.346", "—", "—", "—", "0.050", "—", "✓"],
        ["欠けた項目", "1", "—", "—", "—", "—", "—", "—"],
        [
            "そろった項目",
            "0.00010",
            "0.30（cohens_d）",
            "信頼区間 水準 0.95: [0.10, 0.50]",
            "1520",
            "0.050",
            "1e-05",
            "✓",
        ],
    ],
    "exploration_with_a_pass": [
        ["指標", "値", "区間", "N", "しきい値", "合否"],
        [
            "待ち日数の差",
            "1.80",
            "信頼区間 水準 0.95: [0.40, 3.20]",
            "840",
            "1.0",
            "✓",
        ],
    ],
    "threshold_kinds": [
        ["指標", "値", "しきい値", "合否"],
        ["数", "2.10", "2.0", "✓"],
        ["文字", "2.10", "2.0 日以上", "✓"],
        ["その他の JSON", "2.10", '{"min": 1.0, "max": [2.0, NaN]}', "—"],
    ],
    "pass_not_a_boolean": [
        ["指標", "値", "しきい値"],
        ["文字の合否", "2.10", "2.0"],
        ["数の合否", "2.10", "2.0"],
        ["null の合否", "2.10", "2.0"],
    ],
    "mixed_design": _PRIMARY_AND_GUARDRAIL_ROWS,
    "design_without_an_intent": _PRIMARY_AND_GUARDRAIL_ROWS,
}


def save_design_with_verdict(insight: Path, intent: str | None, verdict: str) -> str:
    """Save a design of *intent* with the text of its verdict; return the design id.

    ``design_io`` creates no mixed design, no legacy exploration and none without
    an intent, so the intent is rewritten in the saved YAML.
    """
    (insight / "designs").mkdir(parents=True, exist_ok=True)
    design_id = design_io.create_design(
        theme_id="LIB",
        title="取り置き期限の延長",
        hypothesis_statement="延ばすと減る",
        hypothesis_background="7日で多い",
        base_dir=insight,
    )["id"]
    data = design_io.load_design(design_id, insight)
    if intent is None:
        del data["analysis_intent"]
    else:
        data["analysis_intent"] = intent
    atomic_write_yaml(insight / "designs" / f"{design_id}_hypothesis.yaml", data)
    notebooks = insight / "notebooks"
    notebooks.mkdir(exist_ok=True)
    (notebooks / f"{design_id}_verdict.json").write_text(verdict, encoding="utf-8")
    return design_id


def table_rows(table_html: str) -> list[list[str]]:
    """The cell texts of each row of one ``<table>``, header row first."""
    return [
        [
            html.unescape(cell)
            for cell in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)
        ]
        for row in re.findall(r"<tr>(.*?)</tr>", table_html, re.S)
    ]
