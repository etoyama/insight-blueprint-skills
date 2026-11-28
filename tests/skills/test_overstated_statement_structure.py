"""Structure tests: a statement that seems to say more than its cites is asked about.

Epic 36, Story 36.6 (US-3 AC 1 to AC 3). Since Story 34.8 a statement no new result
bears on keeps its words, so a claim of an earlier answer that says more than its
cited events stays. The agent no longer fixes it on its own: the question before the
answers are written lists it and asks whether to keep, weaken or drop it (ADR-0069).
A statement with `analyst_view` may be listed, but the agent never writes a weakened
sentence for it: the analyst says the words (ADR-0068). The steps live in prose, so
these tests guard the load-bearing parts.
"""

from __future__ import annotations

import re

from tests.skills._markdown import unwrap
from tests.skills._reflection import reflection_section

OFFER = "#### Before writing: results no answer above rests on"
OVERSTATED = "根拠より強く言っているように見える、前の答えの文"
CHOICE = "残す・弱める・落とす"


def _drafts() -> str:
    return unwrap(reflection_section("### Step T2: "))


def _offer() -> str:
    return reflection_section(OFFER)


def _sentences(prose: str, phrase: str) -> list[str]:
    """Every sentence of ``prose`` that holds ``phrase``."""
    return [s for s in re.split(r"(?<=\.)\s", unwrap(prose)) if phrase in s]


def _part(name: str) -> str:
    """The text of one numbered part of the question, up to the next part."""
    found = re.search(
        rf"^\d\. \*\*{re.escape(name)}\*\*(.*?)(?=^\d\. \*\*)",
        _offer(),
        re.MULTILINE | re.DOTALL,
    )
    assert found, f"no part named {name}"
    return unwrap(found.group(1))


class TestTheDraftNeverFixesAClaimThatSaysMoreOnItsOwn:
    """US-3 AC 2: the agent does not change the sentence before the analyst answers."""

    def test_saying_more_than_the_cites_is_no_longer_a_reason_to_change(
        self,
    ) -> None:
        # Every sentence of Step T2 that names the overreach sends it to Step T3.
        sentences = _sentences(_drafts(), "say more than")
        sentences += _sentences(_drafts(), "says more than")
        assert sentences
        for sentence in sentences:
            assert "Step T3" in sentence, sentence

    def test_the_draft_keeps_such_a_claim_and_asks_about_it(self) -> None:
        assert re.search(
            r"(?i)a claim of the current answer that no new result bears on and that"
            r" seems to say more than the events it cites is sent as the current answer"
            r" has it[^.]*asked about in Step T3[^.]*ADR-0069\)\. Never weaken or drop"
            r" it on your own\.",
            _drafts(),
        )

    def test_a_claim_a_new_result_bears_on_is_rewritten_and_not_asked_about(
        self,
    ) -> None:
        assert re.search(
            r"(?i)a claim a new result bears on is rewritten for that result[^.]*and is"
            r" not asked about",
            _drafts(),
        )

    def test_the_rules_that_still_change_a_kept_statement_hold_the_contradicts_one(
        self,
    ) -> None:
        fixed = re.search(
            r"(?i)a statement no new result bears on is changed only where it breaks"
            r" a rule[^.]*\.",
            _drafts(),
        )
        assert fixed
        # The parenthesis names the contradicts rule and nothing else.
        assert re.search(
            r"breaks a rule of this step \(a `contradicts` event cited outside a"
            r" `weakening`\) or where",
            fixed.group(0),
        )


class TestTheQuestionListsTheStatementsThatSeemToSayMore:
    """US-3 AC 1: the question lists them and asks keep, weaken or drop."""

    def test_the_part_comes_after_the_dropped_results_and_before_the_question(
        self,
    ) -> None:
        parts = re.findall(r"^\d\. \*\*([^*]+)\*\*", _offer(), re.MULTILINE)
        assert parts.index("Overstated") == parts.index("Dropped") + 1
        assert parts.index("The question") == parts.index("Overstated") + 1

    def test_the_part_lists_claims_of_the_current_answer_that_seem_to_say_more(
        self,
    ) -> None:
        assert re.search(
            r"(?i)every claim of the node's current answer that seems to say more than"
            r" the events it cites",
            _part("Overstated"),
        )

    def test_the_block_shows_the_heading_and_asks_keep_weaken_or_drop(self) -> None:
        offer = _offer()
        assert f"{OVERSTATED}（{{N}}件）" in offer
        assert f"{CHOICE}から選べます（書かなければ残します）。" in offer

    def test_the_block_says_what_the_cites_say_next_to_the_sentence(self) -> None:
        assert "← 根拠は{what its cited events say}" in _offer()

    def test_only_a_claim_of_the_current_answer_is_listed_never_the_new_view(
        self,
    ) -> None:
        assert re.search(
            r"(?i)only a claim of the current answer is listed, never the view of this"
            r" round",
            _part("Overstated"),
        )

    def test_a_kept_claim_is_listed_again_while_it_still_seems_to_say_more(
        self,
    ) -> None:
        assert re.search(
            r"(?i)a claim the analyst kept in an earlier round is listed again",
            _part("Overstated"),
        )

    def test_a_node_with_such_a_claim_gets_a_block(self) -> None:
        assert re.search(
            r"(?i)show one block for each node that leaves an event out or has a"
            r" claim that seems to say more than its cites",
            unwrap(_offer()),
        )

    def test_the_question_is_skipped_only_when_no_statement_seems_to_say_more(
        self,
    ) -> None:
        assert re.search(
            r"(?i)skip the question[^.]*only when[^.]*and no claim seems to say"
            r" more than its cites",
            unwrap(_offer()),
        )

    def test_the_closing_question_asks_what_to_do_with_the_statements(self) -> None:
        offer = _offer()
        assert (
            "外す番号、足す番号、見立ての言い直し、前の答えの文の扱いがあれば、"
            "あわせて書いてください。" in unwrap(offer).replace(" ", "")
        )
        assert re.search(
            r"(?i)leave out 、前の答えの文の扱い when no block has the part",
            unwrap(offer),
        )

    def test_two_or_more_statements_are_marked_so_the_analyst_can_name_each(
        self,
    ) -> None:
        assert "文1." in _offer()
        assert re.search(r"(?i)mark them 文1, 文2", unwrap(_offer()))


class TestTheAnalystDecidesWhatHappensToEachStatement:
    """US-3 AC 2 and AC 3."""

    def test_a_statement_the_reply_says_nothing_of_is_kept(self) -> None:
        assert re.search(
            r"(?i)a listed statement the reply says nothing of is kept[^.]*never"
            r" weaken or drop it on your own",
            unwrap(_offer()),
        )

    def test_a_kept_statement_is_sent_character_for_character(self) -> None:
        assert re.search(
            r"^- 残す: the statement is sent character for character",
            _offer(),
            re.MULTILINE,
        )

    def test_a_dropped_statement_is_left_out(self) -> None:
        assert re.search(
            r"^- 落とす: the statement is left out of the draft\.",
            _offer(),
            re.MULTILINE,
        )

    def test_dropping_the_last_statement_of_a_node_is_asked_and_never_reported(
        self,
    ) -> None:
        offer = unwrap(_offer())
        assert re.search(
            r"(?i)when it is the last statement of the node, the answer cannot be"
            r" written without it[^.]*ask whether to keep or weaken it",
            offer,
        )
        assert re.search(r"(?i)never say in Step T5 that it was dropped", offer)

    def test_a_weakened_statement_takes_the_analysts_words_or_says_only_its_cites(
        self,
    ) -> None:
        weaken = unwrap(_offer())
        assert re.search(
            r"^- 弱める: the statement takes the analyst's words, exactly",
            _offer(),
            re.MULTILINE,
        )
        assert re.search(
            r"(?i)the analyst's words, exactly, when they give them, with"
            r" `\"analyst_view\": true`",
            weaken,
        )
        assert re.search(
            r"(?i)rewrite only that statement to say no more than its cited events"
            r"[^.]*same `cites`",
            weaken,
        )

    def test_the_agent_never_writes_a_weakened_sentence_for_a_view(self) -> None:
        offer = unwrap(_offer())
        assert re.search(
            r"(?i)a claim with `analyst_view`[^.]*listed here[^.]*（あなたの見立て）",
            offer,
        )
        assert re.search(
            r"(?i)never write a weakened sentence for a statement with `analyst_view`"
            r"[^.]*ADR-0068",
            offer,
        )
        assert "弱めるときは、文をあなたの言葉で書いてください。" in _offer()

    def test_a_view_to_weaken_without_words_is_asked_for_its_words(self) -> None:
        assert re.search(
            r"(?i)when the analyst chooses 弱める for a view without saying how it"
            r" reads, ask for the words",
            unwrap(_offer()),
        )

    def test_a_view_that_seems_to_say_more_is_listed_once(self) -> None:
        assert re.search(
            r"(?i)not again under \*\*The view\*\*",
            _part("Overstated"),
        )

    def test_step_t5_says_the_choice_in_the_same_words(self) -> None:
        offer = _offer()
        assert "前の答えの文を、あなたが選んだとおり弱めた" in offer
        assert "前の答えの文を、あなたが選んだとおり落とした" in offer
        assert re.search(r"(?i)in Step T5[^.]*`\{reason\}`", unwrap(offer))
