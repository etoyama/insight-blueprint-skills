# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **After the hand-over, an analysis asks before it changes what the analyst read, one analysis can be
  stopped, and the endings are asked together.** An execution agent that cannot go on without changing
  the population, grain, denominator, extraction, a source, the primary metric, what a result is
  compared against or the criterion stops
  before it touches the data and records a confirmation with `design_io ask-analyst`; the other analyses
  go on. `/analysis-auto` asks the analyst, records the answer with `design_io answer-analyst`, runs
  premortem again and hands the analysis over again, or stops it. The analyst may stop one analysis at
  any point; a stopped design keeps its status in every write (`transition`, `update`, `review-batch`),
  takes no result and no hearing, and its analysis note says 段階: 止めた with the reason. The page is
  rebuilt by `/analysis-auto` each time an agent returns, and `/analysis-notebook` skips its own render
  when it runs as an execution agent. When the analyses are back, the three questions of
  `/analysis-reflection` are asked for all of them in one question. `design_io stage` gives the stage,
  whether a result is on record and the open confirmations; `design_io journal-append` writes the events
  of a run under the write lock. An answered confirmation is no longer an open question
  ([ADR-0064](docs/adr/0064-a-handed-over-analysis-asks-before-changing-what-was-read-and-can-be-stopped.md),
  [ADR-0062](docs/adr/0062-only-the-dialogue-agent-writes-shared-records-and-read-to-write-is-locked.md), #291).
- **`/analysis-auto` hands several questions over together, after one check.** When the analyst chooses
  several questions that do not wait for each other, the decision names them all and the round designs
  each, saves the designs `in_review`, links them and asks once, with the page of the tree and the rows
  that differ. A comment pasted from the page becomes a review comment of its design, a design left out
  is stopped with the analyst's reason, and each design then runs in an execution agent of its own that
  writes only its notebook, verdict and journal. `tree_io handover` names the designs that state no data
  scope, and such a design is not put to the check. A resumed run enters by the stage of each analysis
  ([ADR-0063](docs/adr/0063-designs-to-hand-over-are-saved-then-read-side-by-side-on-the-page.md),
  [ADR-0062](docs/adr/0062-only-the-dialogue-agent-writes-shared-records-and-read-to-write-is-locked.md), #290).
- **The question tree page lays out the designs to hand over side by side, before they run.** The designs
  not yet run on the questions the last decision names stand in columns, with their intent, what they
  answer, the criterion, population, grain, denominator, sources, method, primary metric, the full
  extraction and the charts. The code marks the population, grain, denominator and source rows whose
  values differ between them, and `tree_io handover` gives the same rows to the chat. Each design has a
  comment box; a button gathers the comments, each after its design id, into one text on the page,
  which sends nothing out. The progress word 検証中 becomes 調べている, the counts read from the furthest,
  stopped takes a dashed frame and stripes, and `tree_io report` names stopped designs apart in
  `stopped_designs`. The synthetic scenario `lib-handover` builds such a page
  ([ADR-0063](docs/adr/0063-designs-to-hand-over-are-saved-then-read-side-by-side-on-the-page.md), #289).
- **The question tree page shows where each analysis stands and what waits for the analyst.** Each linked
  design says its analysis stage in words and a colour, with the reason a stopped one was stopped and what one
  waiting for the analyst asks. The analyses that wait for the analyst lead the page, and no such section is
  shown when none waits. A question whose designs were all stopped reads as stopped in its own colour, and
  stopped designs come after the finished ones. The next question and the list of decisions name every
  question a decision hands over. The synthetic scenario `lib-stages` builds a page with every stage
  ([ADR-0061](docs/adr/0061-a-tree-decision-may-hand-over-several-questions-and-the-stage-is-derived.md), #288).
- **A handed-over analysis can ask the analyst, take the answer and be stopped, and two writers no
  longer lose a record.** `design_io ask-analyst`, `answer-analyst` and `stop` write the marks of a
  confirmation, its answer and a stop into the journal, and are the only writers of them. The stage of an
  analysis is derived, never stored, by `insight_blueprint.models.analysis_stage`. `design_io` holds one lock from
  reading to writing back, so two processes creating designs at once get different ids. A design may hold
  its population, grain and denominator (`data_scope`), shown in the method section of its note; saved
  designs read as before. An event counts as a result only after the analysis mark, so reasoning journaled
  before the run leaves the analysis running. The pre-write hook now refuses a Write or Edit of a journal that
  adds, removes or changes an event with one of the marks
  ([ADR-0067](docs/adr/0067-the-hook-keeps-the-journal-marks-of-design-io.md), [ADR-0061](docs/adr/0061-a-tree-decision-may-hand-over-several-questions-and-the-stage-is-derived.md),
  [ADR-0062](docs/adr/0062-only-the-dialogue-agent-writes-shared-records-and-read-to-write-is-locked.md),
  [ADR-0064](docs/adr/0064-a-handed-over-analysis-asks-before-changing-what-was-read-and-can-be-stopped.md),
  [ADR-0066](docs/adr/0066-a-design-may-state-its-population-grain-and-denominator.md), #286).

### Changed

- **A tree decision may hand over several questions, and the walk reads every one of them.** A decision holds the
  questions handed over with its own (`with_node_ids`); saved trees read and write back as before. `tree_io position`
  returns every node of the last decision with each linked design and its analysis stage, never says the walk is
  concluded while an analysis is unfinished or a handed-over question has no design, and lets a stopped analysis
  go. Progress is folded from the analysis stage and gains 止めた. Every `tree_io` writer holds the write lock, so two
  processes linking at once keep both links. 「ツリーの決定」 is now 「論点ツリーの決定」
  ([ADR-0061](docs/adr/0061-a-tree-decision-may-hand-over-several-questions-and-the-stage-is-derived.md),
  [ADR-0062](docs/adr/0062-only-the-dialogue-agent-writes-shared-records-and-read-to-write-is-locked.md), #287).
- **The tree check no longer counts an id of the tree or a past reflection round as a number.** An answer or a
  decision reason may name a node, a linked design or its event, and "N回目の振り返り" up to the current round;
  any other number still needs a cited event that records it, and `tree_io` now says how to fix it in `fix`
  ([ADR-0065](docs/adr/0065-ids-and-reflection-rounds-are-not-counted-as-numbers.md), #285).
- **A handoff trial record names the model that read.** `scripts.handoff_trial record` takes `--reader-model`
  and stops without it when the reader is Claude; the id comes from `modelUsage` in the reply of
  `claude -p --output-format json`. The records kept through 2026-11-26 have no model and are not rewritten
  ([ADR-0060](docs/adr/0060-a-trial-record-names-the-model-that-read.md), #249).
- **`docs/HANDOFF_TRIAL.md` tells a person to check the key by hand** when the questions or the scoring
  rules change, and to sort a disagreement into the page, the wording of the question or the rule before
  fixing anything (#249).
- **The words a question tree shows the analyst live in one module.** `skills/_shared/tree_words.py`
  holds the word tables, the phrasings the page and the report share, and the legend; the shape of a
  tree (children, page order, ancestors, root) is asked of `QuestionTree`. The page and the report
  read the same as before (#273).

## [0.21.0] - 2026-11-26

### Upgrade note

- **A tree with a decision that has `cites` cannot be read by an earlier version of the
  plugin.** An earlier version rejects any key of a decision it does not know
  ([ADR-0058](docs/adr/0058-a-tree-decision-may-cite-the-events-behind-its-reason.md), #249).
- **`tree_io progress` returns an object for each question, not a word.** A script that read
  `progress[node_id]` as a string reads `progress[node_id]["progress"]`, which is `null` for a question
  shown by the progress below it ([ADR-0057](docs/adr/0057-a-question-without-a-design-shows-the-progress-below-it.md), #249).

### Changed

- **The handoff trial was taken again on the display of Epic 34.** Nine Claude readers read each of `lib`
  and `psy` on the fixed display (e3521d1), and the summary sits beside the records from before
  (`docs/handoff-trials/2026-11-26-after-the-display.md`). Only `lib`'s q5 went up (7 of 9 right before, 9 of 9 after);
  `lib`'s q2 went down to 3 of 9, as six readers left out LIB-Q04, whose card no longer says 未着手, and
  haiku added a reworded or dropped result to q4's evidence four times. The analyst's own reading
  is kept as the human reader's record, untimed. PRD's success criteria name the sixth question, and the
  glossary's trial words say two scenarios and six questions (#269). Both falls were then fixed: 未着手
  follows one rule (ADR-0057), and question 4 of the sheet asks only for the events the changed answer
  newly rests on, not those it rewords or drops (ADR-0059; the key and the scoring do not change).
  Taken again on the fixed display (2cd6547), all 18 runs got all six questions right
  (`docs/handoff-trials/2026-11-26-after-the-gate-fixes.md`); q4 is not a like-for-like comparison,
  since its wording changed (#249).
- **The question tree counts reflections and revisions in words.** A round is shown as N回目の振り返り
  (2回目の振り返り, 前の振り返りから変わったこと（1回目 → 2回目の振り返り）) instead of 回 N, and the table of
  what changed says 言っていたこと / 言っていること without ここから. The mark above an answer reads
  2回目の振り返りで変わったこと (and 2回目の振り返りで初めて答えたこと), so it heads the statements below it. A subject never revised says nothing of
  its revision: 主題の版 1 is gone from the header and from every answer. Once revised, the header says
  主題を1回見直した with a link to the history, and an answer to an earlier subject is 見直す前の主題への答え
  (after two or more, 1回目の見直しの前の主題への答え). `/analysis-reflection`, `/analysis-framing`,
  `/report-export` and the trial's prompt sheet use the same words; the YAML keys do not change.
- **The question tree shows how far the questions under a question have come, why a question was closed,
  and what each decision rests on.** A question with no design of its own but a design somewhere under
  it no longer says 未着手: its card counts the progress of every question under it by word (主題の下に置いた論点
  4 つ: 分析済み 3、未着手 1), and 進捗の数 leaves it out. A question with no design on it or anywhere under
  it still says 未着手 and is counted, so 未着手 and 次の候補 name the same questions. `tree_io progress`,
  the report's table of questions, and the progress `/analysis-reflection` and `/analysis-framing` tell
  the analyst follow the same rule: `tree_io progress` now returns, for each question,
  `{"progress": <word or null>, "below": {<word>: <count>}}`. A question whose latest decision closed it says on
  its card the round it was closed after and why. Under the reason of every decision, the page shows the
  analysis results it cites (id, design and text), or says the reason names none; the first decision is
  not told so. `scripts.handoff_trial build` stops when a decision of the scenario fails the check, and
  the key of question 5 is derived from what the last decision cites ([ADR-0057](docs/adr/0057-a-question-without-a-design-shows-the-progress-below-it.md),
  [ADR-0058](docs/adr/0058-a-tree-decision-may-cite-the-events-behind-its-reason.md), #268).
- **A tree decision can cite the journal events its reason rests on.** `tree_io decide` takes an
  optional `cites`. A decision that cites is checked before it is written: a cite that is not in the
  journal, a cite of a design linked to no node of the tree, or a number in the reason that no cited
  event holds returns `{"violations": [...]}` with exit code 3, and nothing is written. A decision
  without cites is written as before, and a saved tree without them reads as it did. The decision gate
  of `/analysis-reflection` puts the events behind the analyst's reason into the decision, and offers
  主題そのものを見直す beside deepen, return and close; choosing it goes to the step of
  `/analysis-framing` that raises the root revision ([ADR-0058](docs/adr/0058-a-tree-decision-may-cite-the-events-behind-its-reason.md), #266).
- **The theme reflection keeps the words of what did not change, and asks about the results the answers leave out.**
  When `/analysis-reflection {theme_id}` writes a node's answer again, it starts from the current
  answer and sends every statement that the new results do not change character for character, so
  "said differently" on the tree shows real changes; it changes an old statement otherwise only to fix
  a rule it breaks, and says why. Before it writes the answers, it shows the analyst the results that an
  answer below rests on and the answer above does not (まだ答えに入れていない分析結果, and those it rested
  on before), and asks whether to rest on them; the answers are written either way. `/analysis-auto`
  pauses for that choice (#270).
- **The question tree shows the results an answer leaves out, and how the answers above use a result.**
  The top of the page and every question card list the analysis results that answers further down
  rest on and this answer has never used (まだ答えに入れていない分析結果), with the question, round and
  sentences they come from; a result of an analysis that found no difference lands here. Results the
  answer used before and no longer does are folded apart, with the last round that used them and what
  the next answer used instead. A card also lists the answers above it, up to the subject, that rest on
  its results, with their round and sentences and a link to them; when such an answer says something
  else of the result in a round after this card's answer, the card names that round and says this answer
  stayed as it was. `tree_io changes` returns both as JSON under `cited_above` and `uncited_below`
  ([ADR-0056](docs/adr/0056-answer-changes-are-derived-from-cites-and-shown-on-both-cards.md), #267).
- **The question tree opens with the answer to the subject and what it changed.** The page now starts
  with the current answer to the subject, what that answer changed since the answer before it, and the
  question to look into next with its reason; the reading guide is folded. "What changed" lists one row
  per analysis result the answer rests on, with what the earlier round said from it and what this round
  says, sorted into newly used, no longer used, said differently and unchanged. Every question card
  shows the same for its own answer, and an answer of an earlier round says that later rounds left it as
  it is. The rows are derived from the cites of the two answers and never stored, so a tree saved before
  shows them too; a sentence that was only reworded also counts as said differently. `tree_io changes
  --theme <id>` returns the same values as JSON ([ADR-0056](docs/adr/0056-answer-changes-are-derived-from-cites-and-shown-on-both-cards.md), #265).
- **The handoff trial has a second scenario and a sixth question.** `psy` (psychological safety, four
  reflection rounds) holds an analysis that found no difference and a question whose answer and numbers
  stay while the subject's answer cites its evidence in other words. Every scenario now asks q6 (that
  question and its evidence, or none), and the key is derived from the built tree; the library's is
  none. The sheet of questions and HANDOFF_TRIAL say "subject" instead of "root". Records kept before
  have no q6 and keep their score. On the display before Epic 34's changes, all nine Claude readers got
  all six questions of `psy` right ([ADR-0059](docs/adr/0059-the-handoff-trial-has-a-second-scenario-and-a-sixth-question.md), #264).
- **The question tree speaks the analyst's words.** The page, the skills and the report call the
  root question 主題, its revision 主題の版 and an answer to an older revision 見直す前の主題への答え,
  and the kinds of statement これまでわかっていること, 注意すべきこと and まだ決められないこと. The YAML keys
  and values (`root_revisions`, `claim`, …) and `tree_io revise-root` keep their names, so a saved
  tree reads as it did; the glossary copies the table of words to show ([ADR-0055](docs/adr/0055-the-root-question-is-shown-as-the-subject.md), #263).

## [0.20.0] - 2026-11-26

### Changed

- **A confirmatory notebook judges its primary metric by two lines.** The contract has the primary
  metric hold `support_line` and `reject_line` (numbers copied from the design's `comparison`) and a
  `judgment` of `supported`, `rejected` or `inconclusive`; `threshold` and `pass` stay with secondary
  and guardrail metrics. The interval of a value goes in `interval` with its `kind` (`confidence`,
  `hdi`, …), and a metric measured per group holds `by` and `groups` instead of a group in its name.
  A verdict saved before reads as it did, `confidence_interval` included, so nothing has to be
  rewritten; a notebook generated before writes the new items once it is generated again ([ADR-0052](docs/adr/0052-verdict-holds-two-lines-a-judgment-an-interval-kind-and-groups.md), #243).
- **A design whose analysis has started keeps its hypothesis, its criterion and its intent.** When a
  design first enters `analyzing` or a terminal status, `design_io` writes `analysis_started_at` on it,
  and the mark stays through a review of the result. From then on a confirmation (also a saved `mixed`
  and a legacy exploration) refuses a change of `hypothesis_statement`, of its `primary` metrics (their
  `target` and `comparison`; adding, removing or re-tiering one) and of `analysis_intent`, in
  `design_io update` and in a direct write alike, also after the design went back to `in_review`. To
  test another hypothesis or criterion, derive a new design with `parent_id`. The background and the
  other fields can still be edited. A confirmation now enters `analyzing` only when it has a `primary`
  metric and every `primary` metric has its `comparison` written, so write the criterion before the review approves the design.
  The same holds for a write that concludes such a design as `supported` or `rejected` without analyzing it; to
  end it without a criterion, close it as `inconclusive`. A repair of a design whose saved record no
  longer reads keeps the same items fixed once its analysis has started. Designs
  already saved still read; one that is `analyzing` or concluded counts as started
  ([ADR-0053](docs/adr/0053-a-started-confirmation-keeps-its-hypothesis-criterion-and-intent.md), #244).
- **The report's metric table shows the two lines, the judgment and the kind of an interval.** A
  confirmation's table gains 支持の線, 棄却の線 and 判定 (支持, 棄却 or 結論しない) when a metric holds
  them; the interval column is headed 区間 and names its kind (信頼区間, HDI, 等裾信用区間, or the kind as
  written) before its level. A metric measured per group gets a table of its own: rows by one axis
  and columns by the other when it has two axes of values alone, else a column per axis. Values are
  shown as written and never sorted as numbers. A verdict saved before shows the same columns and
  values, its interval now under 区間 as 信頼区間 ([ADR-0052](docs/adr/0052-verdict-holds-two-lines-a-judgment-an-interval-kind-and-groups.md), #246).
- **The analysis note's metric table shows the two lines, the judgment and the kind of interval, and
  gives a metric measured per group a table of its own.** The judgment reads 支持, 棄却 or 結論しない;
  the interval column is headed 区間 and names its kind (信頼区間, HDI, 等裾信用区間, or the kind as
  written). Two axes of values only lay one axis down and one across; any other groups come in a tall
  table. A column no metric fills is left out, so a saved verdict keeps its values with fewer columns
  ([ADR-0052](docs/adr/0052-verdict-holds-two-lines-a-judgment-an-interval-kind-and-groups.md), #245).
- **A review after the analysis reads the result.** When the design has a verdict, `/analysis-review`
  tells the analyst what it reads (the notebook, the verdict, the figures) and checks the lines and
  the judgment against `comparison`, values against judgments, the figures' axes, the guardrails and
  the cells. A review comment may now target `notebook`, `verdict` or `figures`, and each review batch
  records `after_analysis_started`; batches saved before read as they were, without it.
  `/analysis-revision` fixes a comment on the result in the notebook and re-runs it, and answers a
  comment on what a started design keeps with a reason or a derived design instead of
  `design_io update` ([ADR-0054](docs/adr/0054-review-covers-the-result-and-its-comments-reach-the-reader.md), #247).
- **Review comments reach the reader.** The analysis note gains a "レビュー" section that lists every
  review batch of `{id}_reviews.yaml`, newest first, with its time, whether it came after the
  analysis started (left out for a batch saved without it), the status after the review, and each
  comment with its target as written. The question tree shows, on a design's card, how many review
  comments came after the analysis started, or on its row under the derivations when the design is linked
  to no node; none shows nothing. `/analysis-review` rebuilds the design note after it records a batch. A `_reviews.yaml` that cannot be
  read leaves both pages as they were, and the report does not show review comments
  ([ADR-0054](docs/adr/0054-review-covers-the-result-and-its-comments-reach-the-reader.md), #248).

## [0.19.0] - 2026-11-25

### Upgrade note

- **An exploratory design saved with a hypothesis still reads, and is marked "探索（旧形式）"
  (legacy exploration).** It keeps its hypothesis and verdict as written, and checks and concludes like
  a confirmation. Nothing has to be rewritten
  ([ADR-0049](docs/adr/0049-legacy-exploration-stays-readable-and-is-marked.md), #227).
- If such a design was really a confirmation (a hypothesis fixed before the analysis), set its intent
  to `confirmatory`. This works in any status and changes nothing else, as long as its
  `hypothesis_statement` and `hypothesis_background` are written:
  `echo '{"analysis_intent": "confirmatory"}' | design_io update --id <id>`.
  A design whose background is blank is refused; leave it marked as it is rather than writing the
  background after the result. Leave an exploration that put a verdict on an open question as it is too.
- `mixed` can no longer be created, and an intent can be changed only while the design is `in_review`
  or `revision_requested`. A saved `mixed` design still reads and is treated as a confirmation.
  To analyse the other way after the analysis, derive a new design
  ([ADR-0048](docs/adr/0048-intent-decides-the-form-and-the-end-of-a-design.md), #227).

### Changed

- **The design hook checks a write over a saved design the way `design_io update` does.** A direct
  write can no longer change the intent or the form after the analysis, such as rewriting an `analyzing`
  confirmation into an `explored` exploration; it is refused with the same message, which says to derive
  a new design. A new file and a design broken on disk are checked as before (#217).
- **An exploratory design holds a question, not a hypothesis, and ends as `explored`.** `design_io create`
  takes `exploration_question` and `exploration_background` for an exploration, and refuses a hypothesis,
  `next_action`, a verdict and the `mixed` intent. A new confirmatory design needs `hypothesis_statement`
  and `hypothesis_background` written: a blank one, which used to pass, is refused. Designs already saved (an exploration with a hypothesis,
  `mixed`, or no intent) still read and conclude on a verdict as before
  ([ADR-0048](docs/adr/0048-intent-decides-the-form-and-the-end-of-a-design.md),
  [ADR-0049](docs/adr/0049-legacy-exploration-stays-readable-and-is-marked.md), #226).
- **An exploratory notebook keeps what it measured and predicts nothing.** Its `results` have no
  `hypothesis_direction` or `decision_reason`, its metrics no `threshold` or `pass`, and the verdict
  keeps the measured values in `metrics`; its journal evidence carries no `direction`. A confirmation
  copies its threshold from the `comparison` of the primary metric. The docstring writes the
  exploration question in place of the hypothesis
  ([ADR-0050](docs/adr/0050-exploration-keeps-values-and-confirmation-fixes-its-criterion.md), #229).
- **The analysis note and the report word an exploration apart from a confirmation.** An exploration opens
  with its question, shows its evidence as one group and its measured values without a threshold or a pass
  mark, and concludes with 「探索を終えた。判定はしていない。」. A confirmation now says 「検証仮説」 where it
  said 「仮説」, and the report's design table has an intent column. A legacy exploration keeps its old sentences
  and is marked as such ([ADR-0051](docs/adr/0051-designs-nest-under-their-question-and-state-is-worded-by-role.md), #230).
- **The question tree shows each analysis design under the question it is linked to.** The design is a
  dashed card of its own, before the child questions, with its intent, its question or hypothesis, its status
  and a link to its note; a second question that links it shows a short row pointing to the first. The status
  is worded by its role (「探索済み（判定はしない）」, 「検証仮説の判定: 支持」, ...), and the legend maps each word
  to its YAML value. The answer of a question is headed 「現時点の答え」, and an exploration's cited evidence shows
  no direction. The handoff trial's scenario now holds an exploration, and its q3 key splits the cited events
  by the kind of the citing statement ([ADR-0051](docs/adr/0051-designs-nest-under-their-question-and-state-is-worded-by-role.md), #231).

- **`/analysis-design` and `/analysis-auto` ask the intent first.** Before anything else of the design,
  the analyst chooses exploration or confirmation (`mixed` is no longer offered), and then writes
  `exploration_question` for an exploration or `hypothesis_statement` for a confirmation. A
  confirmation writes the criterion of its verdict in the `comparison` of its primary metric at the
  methodology step. The Framing Brief drafts a question or a hypothesis by the intent, and
  `/analysis-review` reads each intent with its own lenses
  ([ADR-0048](docs/adr/0048-intent-decides-the-form-and-the-end-of-a-design.md),
  [ADR-0050](docs/adr/0050-exploration-keeps-values-and-confirmation-fixes-its-criterion.md), #228).
- **`/analysis-reflection` asks whether to have the result reviewed before it records `conclude`.** Taking
  the review records nothing yet; after it, the reflection records one `conclude` and ends the design. Before,
  a review offered after the conclusion left two `conclude` events in the journal (#217).
- **When an exploration's answer states no measured value, `/analysis-reflection` shows the measured values and
  asks again.** The values come from the journal's evidence, the analyst answers the exploration question in terms
  of them, and their words are kept as the answer (#217).
- **A design made without a Framing Brief can be linked to a question of the theme's tree.** When the theme has a
  question tree, `/analysis-design` shows its questions, asks which one the design answers (or none), and links it
  with the same `tree_io link` as the Brief (#217).

- **`/analysis-reflection` asks its three questions by what they ask, and an exploration ends without a verdict.**
  The headings read 「結果から何が言えるか」, 「まだ答えの出ていない問いで、判定は変わるか」 and
  「この分析設計をどう終えるか」. A confirmation shows the criterion of its primary metric before the first, the
  scope of the open questions and what each answer would change before the second, and that the end usually
  follows the first answer before the third. An exploration answers its question and ends as `explored`,
  and may leave a tentative answer to confirm in a derived design. A corrected hypothesis now goes into a
  derived design through `/analysis-design`, instead of rewriting the analyzed design with `design_io update`
  ([ADR-0048](docs/adr/0048-intent-decides-the-form-and-the-end-of-a-design.md), #211, #232).
- **`/analysis-design` explains a metric before it asks about the method, and `/analysis-auto` does so at design ②.**
  Every metric gets one sentence of what number it is. A metric built from two or more quantities that is
  new to the theme also gets how it is made, a worked example, what is easy to get wrong and what changes with
  the other handling, and what it cannot say. The example numbers come from the journal or from another group
  computed the same way, never from the result to be judged. A confirmation's criterion also says what it
  means and how the verdict changes with the handling. The analyst may ask for this on any metric (#210, #233).
- **A branch in `/analysis-journal` now derives its design through `/analysis-design`.** The branch used to
  write the child with `design_io create`, which left its intent `confirmatory` without a criterion and carried
  over the source's hypothesis background. Now `/analysis-design` asks the intent, writes a question to explore
  or a hypothesis to confirm, and fixes the criterion before the new analysis. The `branch` event and
  `tree_io link-derived` stay as before
  ([ADR-0048](docs/adr/0048-intent-decides-the-form-and-the-end-of-a-design.md), #217).

### Fixed

- **A p value written as the notebook contract writes it now shows in the analysis note and the report.**
  The contract writes a metric's `p_value`, and the reader took only `p`, so the value was dropped without a word.
  Both are read now, `p` first (#230).

## [0.18.0] - 2026-11-25

### Upgrade note

- **`insight-blueprint-lineage` is no longer published to PyPI.** The last version there is
  0.17.0, and the PyPI project will be archived: it stays installable but gets no new versions.
  The plugin's env never came from PyPI; it is built from the tagged source
  ([ADR-0047](docs/adr/0047-stop-publishing-to-pypi.md), #207).
- To keep using `insight_blueprint` outside the plugin, install it from a release tag of this
  repository instead: `uv add "insight-blueprint-lineage @ git+https://github.com/etoyama/insight-blueprint-skills@v0.18.0"` (or a later tag).
- The shape of the models (`src/insight_blueprint/models/`) is no longer a public contract. A
  later version may change it while still reading the YAML already saved under `.insight/`, so
  code that imports the models outside the plugin can break on an update.
- `/data-lineage setup` is gone. `/data-lineage` now takes only the notebook `/analysis-notebook`
  made (`.insight/notebooks/{id}.py`); for an id with no design, or for any other file, it points
  you to `/analysis-notebook` and stops. A project that ran `uv add insight-blueprint-lineage` because `/data-lineage` asked
  can drop it with `uv remove insight-blueprint-lineage`; the plugin no longer needs it. Keep it if
  your own scripts import `insight_blueprint` (the removed `setup` mode added such imports)
  ([ADR-0047](docs/adr/0047-stop-publishing-to-pypi.md), #219).

### Changed

- **A release is now a tag and nothing else.** The PyPI publish workflow, the `build-check` CI
  job, `scripts/verify_wheel.py` and the poe tasks `verify-wheel` and `release-dry-run` are gone.
  `ci.yml` now checks a pushed `v*` tag against the `pyproject.toml` version, and
  [docs/RELEASE.md](docs/RELEASE.md) tells to run `uv run poe check-tag-version` before pushing
  the tag ([ADR-0047](docs/adr/0047-stop-publishing-to-pypi.md), #220).
- `/data-lineage` runs the notebook in the plugin's env with the same command as
  `/analysis-notebook` (`uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook python
  .insight/notebooks/{id}.py`, plus `--with` for an allowlisted package in neither the `notebook`
  extra nor the default allowlist). It no longer checks your project's Python for `insight_blueprint`
  or offers to install it ([ADR-0047](docs/adr/0047-stop-publishing-to-pypi.md), #219).
- `/analysis-notebook`, `/data-lineage` and the notebook contract now say never to pass a
  default-allowlist package such as `insight_blueprint` to `--with`. The plugin env already ships
  them, and `--with insight-blueprint-lineage` would layer the 0.17.0 copy from PyPI over the
  plugin's own source (#207).
- `/analysis-notebook` now says in its body that a standard-library module other than `json` and
  `pathlib` is checked against the allowlist like a package. The contract already said so; this
  changes no behavior (Refs #215).

## [0.17.0] - 2026-11-23

### Changed

- **A notebook is now a plain Python script cut into seven `# %% <name>` cells, and it runs in
  one step.** `/analysis-notebook` writes `.insight/notebooks/{id}.py` with a docstring of the
  design and the cells `imports`, `data_load`, `data_prep`, `analysis`, `viz`, `verdict` and
  `lineage`, and runs it with `uv run --project "${CLAUDE_PLUGIN_ROOT}" --extra notebook python
  .insight/notebooks/{id}.py`. It no longer writes `{id}_flat.py` or `{id}.html`. The verdict,
  the figures and the lineage keep their form. marimo leaves the plugin env and the default
  allowlist, which is now `insight_blueprint`, `pandas`, `matplotlib` and `numpy`
  ([ADR-0045](docs/adr/0045-notebook-is-plain-python-with-percent-cells.md),
  [ADR-0046](docs/adr/0046-marimo-leaves-the-plugin-env-and-the-default-allowlist.md), #200).
- **The analysis note reads the new notebook form and shows each cell with its name.** The code
  section lists the cells of `.insight/notebooks/{id}.py` in file order under headings such as
  `cell 3 · data_prep`, without the `data_load` cell and its connection values. A notebook shows
  no code at all when its `data_load` cell cannot be told apart: no `# %%` line, a statement other
  than the docstring before the first one, a `# %%` line inside a statement, no cell or several
  cells named `data_load`, or `raw_df` assigned outside that cell. A marimo notebook is such a
  notebook, so its code no longer appears; the note says that running `/analysis-notebook` again
  brings it back ([ADR-0045](docs/adr/0045-notebook-is-plain-python-with-percent-cells.md), #201).
- **A notebook whose cells differ from the contract's seven shows no code in the analysis note.**
  Any added, missing, renamed or reordered cell, a bare `# %%` or a `# %% [markdown]` line included,
  now hides all the code, because such a line inside `data_load` showed its second half with the
  connection values ([ADR-0045](docs/adr/0045-notebook-is-plain-python-with-percent-cells.md)).
- **A marimo notebook you already have no longer runs in the plugin env as it is.** marimo is
  out of the env and the default allowlist, so running an old `{id}.py` or `{id}_flat.py` stops
  with `ModuleNotFoundError: No module named 'marimo'`. To run one by hand, add `marimo: marimo`
  under `allowed_packages` in `.insight/rules/package_allowlist.yaml` and add `--with marimo`
  after `--extra notebook`. Remove the `marimo` line when you are done, so that notebooks
  importing marimo stop passing the allowlist again. Running `/analysis-notebook` again writes
  the notebook in the new form instead ([ADR-0046](docs/adr/0046-marimo-leaves-the-plugin-env-and-the-default-allowlist.md),
  #202).

## [0.16.0] - 2026-11-23

### Added

- **`tree_io report --theme {theme_id}` writes the final report of a theme.** Code writes
  `.insight/reports/{theme_id}.md` from the question tree: the APA headings, and an Abstract with
  the aim and the current answer to the root question, each sentence followed by the journal
  events it cites. No sentence is written by a model. Nothing is written, and the command exits 3
  with the reasons as JSON, when the theme has no question tree, when the root question has no
  answer under the current root revision, or when the tree check finds a violation. The
  Introduction lists the questions of the tree with their progress. The Method has a table of the
  linked designs (hypothesis, method, why that method) and of their data sources, with no
  connection. The Results give each answered question its answer and the analyses behind it: the
  fixed sentence of the terminal status and the conclude text, the verdict metrics as written, and
  the figures as image links with their captions (`figures` in the JSON lists them). An answer
  given before the root question was revised says so. The Discussion has the evidence against each
  hypothesis, the questions not answered yet, the last tree decision and the answers heard about
  next candidates; there is no section of recommendations. The Appendix lists every journal event
  the report cites, and no other; analysis code and lineage are left out
  ([ADR-0039](docs/adr/0039-report-is-the-final-report-of-a-theme-written-by-code.md), #177).
  Text copied from the records shows as characters: line breaks and tabs fold into one space,
  and a backslash goes before the characters and the marks that would make a tag, an image, a
  link, a table cell, a code span, a fence, a heading or a list. The report says 主題, 記録, 分析,
  上位の論点 and 答えると分かること for the glossary's words a reader does not know.
- **`/report-export {theme_id}` exports the final report of a theme to Claude Docs.** It has
  `tree_io report` write the report, lists the report and its figures with the round that wrote
  the root's answer and the number of unconcluded designs, and creates a new Doc only after you
  approve. When the report cannot be written, it tells you why and sends nothing, even if an older
  report is on disk. Without the host's Claude Docs connector nothing is sent
  ([ADR-0040](docs/adr/0040-report-export-sends-the-report-to-claude-docs.md), #177).

### Changed

- **`/analysis-auto` no longer writes or uploads a report.** The round goes from the design's
  reflection straight to the theme reflection, and a `concluded` position enters there. When the
  walk stops on a theme that has a question tree, the summary names `/report-export {theme_id}`
  for when you judge the theme ready to report; the driver never starts it and does not ask
  ([ADR-0040](docs/adr/0040-report-export-sends-the-report-to-claude-docs.md), #194).
- **The design note no longer links a report.** Its local files list the notebook, the verdict,
  the lineage and the notebook's HTML only (#194).

### Removed

- **`/analysis-report`, `/report-upload`, their template `apa-template.md`, and `report_check`
  (`bin/report_check` and its module).** The per-design report is gone. Read a design in its
  design note (`tree_io render`, inside the question tree's page); send the final report of a
  theme to Claude Docs with `/report-export {theme_id}`. Old reports under
  `.insight/reports/{design_id}.md` stay where they are; nothing deletes them
  ([ADR-0040](docs/adr/0040-report-export-sends-the-report-to-claude-docs.md), #194).
- **A theme without a question tree has no way left to send its results outside this machine.**
  `/report-export` needs the tree, and its designs' notes are standalone pages that no skill
  sends. Build the tree with `/analysis-framing` first. To keep the old skills, pin the plugin to
  the last release that has them: remove the marketplace and add it again at the tag
  (`/plugin marketplace add etoyama/insight-blueprint-skills#v0.15.0`), then install the plugin
  again. Removing a marketplace uninstalls the plugins installed from it.

## [0.15.0] - 2026-11-23

### Added

- **Each analysis design gets a design note, and the question tree's page holds them all.**
  `tree_io render --design {design_id}` builds the note from the design, its journal and the
  notebook's output. The note shows the method, the metric definitions, the data sources, the
  results with the figures embedded, the analysis code (never the data-load cell, which can hold
  connection values), the lineage, every journal event, and the files kept under `.insight/`.
  For a design in a terminal status it also shows the conclusion, copied from the records with
  no text written by the model. `tree_io render --theme` now writes every note of the theme
  below the tree on the same page, and each node links to the notes of its designs with an
  anchor and back. A theme without a tree gets a standalone page under `.insight/notes/`
  ([ADR-0036](docs/adr/0036-design-note-is-a-generated-page-per-design.md), #173).

### Changed

- **`/analysis-reflection` points to the design note before it asks for a conclusion.** Step 2
  rebuilds the page and shows the file to open, where the note is and which nodes link the design,
  instead of listing the figures, the verdict and the notebook in the chat. `/analysis-notebook`
  rebuilds the note after it writes the results (#183).
- **`/tree-upload` sends the tree with its design notes as one file.** The approval text lists
  what the page holds, and a page over 16,000,000 bytes stops before the approval is asked.
  No other file is attached ([ADR-0037](docs/adr/0037-tree-upload-sends-the-design-notes.md), #184).
- **One design that cannot be built stops its theme's page.** The tree page now reads every
  design, verdict and catalog entry of the theme, so a design that does not match its schema, or a
  broken verdict JSON, stops `render --theme` and `render --design` for the theme. The error names
  the design to fix.

## [0.14.1] - 2026-11-22

### Fixed

- **A resumed `/analysis-auto` carried only the first design of a concluded round** (#161).
  When more than one design was finished since the last tree decision, the report and the
  upload named one `design_id`. The driver now carries each design in turn, writing its report
  when missing and starting its upload, so every report reaches its own approval gate. The
  theme reflection and the summary show each report with its upload outcome.

## [0.14.0] - 2026-11-22

### Added

- **`/analysis-reflection` shows what to read before it asks for a conclusion.** Step 2 now
  lists the figures, the verdict and the notebook (`.py` and `.html`) of the design that
  exist under `.insight/notebooks/`, each figure with the title, axes and how-to-read of its
  manifest entry, and every metric of the design as written. Nothing new is written or
  embedded; the analyst opens the files (#140).

### Changed

- **An analyzed design can be concluded directly.** `design_io transition` (and the pre-write
  hook) now accepts `analyzing` → `supported` / `rejected` / `inconclusive`, so
  `/analysis-reflection` closes a design right after its analysis and the default
  `/analysis-auto` walk no longer stops there. Moving back to `in_review` to review the result
  stays available and is optional ([ADR-0029](docs/adr/0029-analyzing-reaches-conclusion-directly.md), #138).
- **A resumed `/analysis-auto` still asks whether to send the report.** When the report of the
  round was written by an earlier run, the walk now goes on to the approval gate of
  `/report-upload` instead of only telling you to run it. Nothing records what was sent, so the
  gate comes with a note: if you sent it before, answer no, since sending again makes a second
  Doc ([epic-27](docs/design/epic-27-resume-upload.md), #139).

### Fixed

- The marketplace now hands out the release tag instead of the tip of `main`, so a version
  number names one content. Changes merged after a release reach you with the next version,
  not on a fresh install in between. This holds from the day the fix is merged, for 0.13.0
  too (#106).
- `catalog_io create` and `update` now refuse a `connection` key named `app_id` (or `appId`),
  `app_key`, `subscription_key` or `pwd`, as they already refuse `api_key`. e-Stat takes its
  API key as `appId`. Put the key in an environment variable and its name in a `*_env` key,
  such as `api_key_env`. A public app id is refused too; write its variable in `app_id_env`.
  A source already stored with such a key can no longer be updated until you fix its YAML by
  hand.
- `/catalog-register` no longer calls an API with the key in the URL to learn a table's
  structure. It reads a response that your project's fetch script saved, or a sample you paste
  with the key removed.
- `catalog_io create` and `update` now judge a nested `connection` key joined to its parent
  keys, so `{"api": {"key": …}}` is refused like `api_key`. They also refuse `consumer_key`,
  `db_pass`, and a key named exactly `authorization` or `sas` (`authorization_url` still
  passes). A nested key that only resembles a credential, such as `api.keyword`, is refused
  too: rename it. A source already stored with such a key can no longer be updated until you
  fix its YAML by hand ([ADR-0034](docs/adr/0034-credential-check-joins-nested-keys.md), #149).
- `/catalog-register` no longer runs a schema query against your database. You run the query
  and paste the results (#149).
- **`/analysis-report` wrote a ratio no input states in Implications** (#105), such as
  「約1.9倍」 when the hypothesis compared two numbers. A ratio, a difference, or a percent change
  between two stated numbers now counts as a computed number, so the report no longer writes one
  unless an input states it.
- **`/report-upload` left out every figure even where the host could upload them** (#103). The
  skill now names the route: upload the PNG into the Doc with the host's asset upload, then link
  it from the Doc. Where the host has no asset upload (such as Claude Code in the terminal at this
  release), the approval list says before you approve that the figures are not sent.
- **`/report-upload` showed no URL when you declined a figure upload** (#155). Declining the
  host's approval card for a figure ends the turn, so the Doc was made but its URL never reached
  you. The skill now shows the URL before it uploads the first figure. Declining one figure
  stops the upload of the rest; they stay as notes in the Doc.
- A design branched off in `/analysis-journal` is now linked to the question nodes of its
  source (`tree_io link-derived`), so it shows in the progress, in the position of the walk and
  in the theme reflection. Nobody is asked for the node
  ([ADR-0033](docs/adr/0033-derived-design-inherits-the-nodes-of-its-source.md), #134).
- `tree_io add-node` with `origin_event_id` no longer ends in a traceback when `events` in
  the journal is not a list, or holds an entry that is not a mapping. It reads only the
  mappings, like every other reader of the journal, and says the event is not found when no
  real event has that id (#141).

## [0.13.0] - 2026-11-22

### Upgrade note

- A project's `.insight/rules/package_allowlist.yaml` can no longer forbid pandas, matplotlib,
  numpy, marimo or insight_blueprint: the default allowlist is always allowed. The packages the
  file already lists stay allowed, so nothing that ran before stops.

### Added

- `/analysis-reflection {theme_id}` now goes on after the current answers: it lists the next
  candidates (the nodes of the question tree with no design on them or below them), can attach a
  question to ask a person, keeps the answer you bring back with who answered and when, and asks
  whether you deepen the same node, return to its parent, or close. Your choice and its reason are
  kept in the tree as a decision.
- A new journal event type, `hearing`, holds what a person answered. `/analysis-design` copies an
  answer kept on a question node into the journal of the design it links to that node, so a later
  answer can cite it. `/analysis-journal` records one too.
- `tree_io get` says on stderr which file it looked for when a theme has no question tree, so
  a tree that exists elsewhere is not taken for a missing one.
- The HTML view of the question tree marks a statement whose every cited event is a `hearing`
  with "人に聞いた答えによる".
- The HTML view of the question tree lists the next candidates, shows the round each decision was
  taken at, and marks an answer that no longer matches the record instead of showing it as the
  current answer.
- `/analysis-framing` makes the HTML view of the question tree with `tree_io render` after it
  writes the tree, and tells you its path.
- `/tree-upload` uploads the HTML view of a theme's question tree to the host's Artifact as a new
  page that only you can see. It lists the file and waits for your approval; without the host's
  Artifact feature nothing is sent and the HTML stays on your machine.

### Changed

- A rerun of `/analysis-framing` on a theme that has a question tree now always asks which node to
  design next. When you pick a node other than the one the latest decision names, it asks for your
  reason and keeps the change as a decision.
- **A project's `.insight/rules/package_allowlist.yaml` now adds packages to the default
  allowlist instead of replacing it.** The default allowlist (pandas, matplotlib, numpy, marimo,
  insight_blueprint) is what every contract notebook imports, so it is always allowed and
  `/analysis-auto` no longer pauses on those imports at the notebook gate. To allow one more
  package, list only that package in the file. Only `json` and `pathlib`, the standard-library modules
  the contract itself imports, need no entry ([ADR-0027](docs/adr/0027-default-allowlist-always-allowed.md), #108).

### Fixed

- **`premortem` showed `unknown` in the INTENT column for every design** (#109). It read an
  `intent` key, but `design_io get` returns the field as `analysis_intent`. The risk level was
  not affected; only the table display was wrong.
- **`design_io`, `catalog_io` and `tree_io` commands without a payload hung when stdin never closed** (#129),
  as in the Bash of the desktop app's Code tab. `get`, `list`, `link`, `progress` and the other
  commands that take no payload no longer read stdin. `catalog_io search` takes its query from
  `--query` only, as `/catalog-register` documents; a query in the stdin payload is no longer read.

## [0.12.0] - 2026-11-20

### Upgrade note

- `catalog_io create` and `update` now refuse a `connection` key that names a credential. A source
  stored earlier with such a key is still read, but `update` refuses it. Edit its YAML by hand: keep
  the secret in an environment variable and name it in a `*_env` key (e.g.
  `"password_env": "PG_PASSWORD"`). Do not ask the model to read the source with `--with-connection`.
- Designs created earlier may carry a file path or table name in `methodology.steps`. They still
  work. To keep the path out of the design and the report, rewrite the step with `{source:ID}`
  through `/analysis-design`.

Epic 17 (#102): a data source's `connection` reaches the model only in `/analysis-notebook`, and the
catalog holds no credentials. Design: `docs/design/epic-17-connection-boundary.md`.

Epic 16 (#101): a project without `.insight/rules/package_allowlist.yaml` uses the default
allowlist instead of stopping at premortem. Design: `docs/design/epic-16-default-allowlist.md`.

### Changed

- **`/analysis-framing` reads the data sources with `catalog_io list`**, which leaves `connection`
  out, instead of opening the catalog YAML. Its cross-search no longer greps the source files
  ([ADR-0022](docs/adr/0022-connection-reaches-only-the-notebook.md)).
- **`/analysis-design` names a data source as `{source:ID}` in `methodology.steps`** and never writes
  a path, host, project id or table name. `/analysis-notebook` replaces each `{source:ID}` with the
  location in that source's `connection` in cell 2. `/analysis-auto`'s data-extraction beat shows
  the data source id instead of the file ([ADR-0022](docs/adr/0022-connection-reaches-only-the-notebook.md)).
- **`catalog_io create` and `update` refuse credential keys in `connection`** (`password`, `token`,
  `api_key`, `secret`, `credential`, `private_key`, `access_key`, nested too) and exit non-zero,
  naming the key but not its value. A `*_env` key such as `password_env` passes when its value is an
  environment variable name (`^[A-Z_][A-Z0-9_]*$`). Reading is unchanged
  ([ADR-0023](docs/adr/0023-catalog-holds-no-credentials.md)).
- **`/premortem` and `/analysis-auto` no longer stop a project that has no
  `.insight/rules/package_allowlist.yaml`.** They use the default allowlist (the packages the plugin
  env ships, listed in the notebook contract). A methodology that needs another package now stops at
  `HARD_BLOCK` instead of `HIGH` (ADR-0021).
- The `HARD_BLOCK` reason for a package outside the allowlist is now
  `package outside allowlist (declare it in .insight/rules/package_allowlist.yaml)`. A script that
  matches the old reason exactly must match its prefix instead.

## [0.11.0] - 2026-11-20

### Upgrade note

- Designs created before this release have an empty `source_ids`. Their report leaves out the data
  source table and says how to add them, `/premortem` returns `HARD_BLOCK`, and `/analysis-notebook`
  stops and points to `/analysis-design`. Add the ids once with `/analysis-design`: open the existing
  design and declare its sources (Step 0 → Step 3b).

Epic 15 (#71): a design declares the data sources it uses in `source_ids`, and every skill reads
them from there. Design: `docs/design/epic-15-declared-source-ids.md`.

Epic 14 (#76): a report written from the same analysis has the same shape whichever model writes
it. The parts of the `/analysis-report` template that were left to the model are now rules.
Design: `docs/design/epic-14-report-template-gaps.md`.

### Added

- **`catalog_io describe --ids a,b`** returns `{"sources": [...], "missing": [...]}`: the registered
  sources in the order given, once each, with only `id`, `name`, `type`, and `description` (never
  `connection`), and every other id under `missing`
  ([ADR-0020](docs/adr/0020-design-declares-sources-in-source-ids.md)).

### Changed

- **`/analysis-design` asks for the data sources and writes them to `source_ids`**, after checking
  the ids with `catalog_io describe`. It never writes an unregistered id. It can also open an
  existing design to declare its sources (Step 0 → Step 3b). `data_source` on a metric or an
  explanatory variable is now a free-form note that no skill reads as an id.
- **`/analysis-report`, `/analysis-notebook`, `/premortem`, and `/analysis-auto` read the data sources
  from `source_ids` only.** The report passes them to `catalog_io describe` and no longer collects
  candidates from `data_source`. `/premortem` returns `HARD_BLOCK` with the reason
  `no data source declared` for a design whose `source_ids` is empty. The model is unchanged.
- **`/analysis-report` names the source of every section.** Open questions follow the journal's
  definition, and the title comes from the design's `title`. The report no longer reads the
  verdict's `evidence_summary` or `open_questions`, which reach it through the journal. Future
  Directions is written from the open questions only. The line written when there is no figure
  depends on why there is none.
- **Fixed formats for tables and numbers.** Method has a table of metrics and one of explanatory
  variables, and a column with no value in any row is left out. `Pass` is written as `✓`, `✗`, or
  `—`. Results splits the evidence into what supports the hypothesis and what contradicts it.
- **Fixed lead sentences.** The Abstract opens with one sentence per terminal status, and
  Recommendation opens with one sentence per row of its table.
- **Discussion.** Limitations is one paragraph built from the limits, the assumptions, and the
  evidence against the conclusion. An empty Limitations or Future Directions is left out, with no
  note in its place.
- **`/analysis-journal`** accepts one id or a list of ids in `metadata.resolves`.

## [0.10.0] - 2026-11-20

Epic 13 (#75): text that came from the analysis inputs is written into the report as characters,
never as markup. Design: `docs/design/epic-13-report-source-text.md`.

### Added

- **`report_check --id {design_id}`** checks a written report for markup that is still active: an
  image that is not a figure, any tag start (`<` followed by a letter, `/`, `!`, or `?`), and, in a
  Mermaid block, a tag other than `<br/>` or a line the lineage export never writes. It fails
  closed: code spans and fences other than Mermaid are checked like any text. It exits 1
  and prints the violations as JSON. `/analysis-report` runs it right after writing the report
  ([ADR-0019](docs/adr/0019-report-source-text-escaped-and-checked.md)).

### Changed

- **`/analysis-report` escapes source text instead of leaving the choice to the model
  ([ADR-0019](docs/adr/0019-report-source-text-escaped-and-checked.md)).** Figure captions,
  data-source fields, lineage reasons, metric names, the decision context, and the title keep
  every word, become one line, and get a backslash before `\` `` ` `` `*` `_` `[` `]` `<` `|`.
  A sentence in them that reads as an instruction stays as text, and the skill tells the analyst
  where it is. A lineage diagram is left out of the Appendix when a label carries a tag other than
  `<br/>` or a line is not one the lineage export writes.

- **`catalog_io` no longer prints a source's `connection` (`get`, `list`, `create`, `update`)
  ([ADR-0018](docs/adr/0018-catalog-io-omits-connection-by-default.md)).** A connection holds file
  paths, queries, hosts, and sometimes credentials, and `/analysis-report` reads `catalog_io get`
  to build a report that can leave the machine. Pass `--with-connection` to get it back;
  `/analysis-notebook` does, because it loads the data. The stored YAML is unchanged.

## [0.9.0] - 2026-11-19

Epic 12 (#62): `/analysis-report` now writes a report a reader can **decide from**, and a new
`/report-upload` skill copies it to Claude Docs. Design: `docs/design/epic-12-decision-ready-report.md`.
Unlike Epic 10 and 11, this touches the PyPI wheel: `insight_blueprint.models.design` gains
`DecisionContext`. Every addition is optional, so existing designs, notebooks, and verdicts keep working.

Epic 11 (#56): the development docs follow the repo-template flow (ADR-0009). Design:
`docs/design/epic-11-repo-template-compliance.md`. The PyPI wheel's runtime (`src/insight_blueprint`)
and the skills are untouched.

### Added

- **`/report-upload` — upload a report to Claude Docs.** Reads `.insight/reports/{id}.md` and its
  figures and creates a **new** Doc, visible only to you until you share it. It never updates,
  overwrites, or shares a Doc. It uses the host's Claude Docs connector; the plugin still ships no
  MCP server ([ADR-0015](docs/adr/0015-host-connectors-for-optional-features.md)). Without the
  connector nothing is sent and the Markdown report stays as it is. A figure that cannot be
  uploaded is left out with a one-line note.
- **Approval before anything leaves the machine ([ADR-0016](docs/adr/0016-approval-before-external-send.md)).**
  `/report-upload` lists the files it would send and waits for your answer. Nothing is created or
  sent before a clear yes. The approval covers that one run and is never remembered, also inside
  `/analysis-auto`.
- **`decision_context` in the design document ([ADR-0014](docs/adr/0014-analysis-design-decision-context.md)).**
  An optional `{decision_maker, decision}` pair: who decides what from this analysis. When present,
  both fields must be non-empty. `/analysis-design` asks for it once after the hypothesis (you can
  skip it), `design_io create` / `update` accept it, and `/analysis-review` checks that it fits the
  hypothesis. Designs without it validate as before.
- **Optional metric items in the notebook contract ([ADR-0013](docs/adr/0013-verdict-metric-optional-items.md)).**
  Each entry of `verdict.metrics` may carry `effect_size` (`{kind, value}`), `confidence_interval`
  (`{level, lower, upper}`), and `sample_size`. The notebook computes them; a method that does not
  define one omits the key. A verdict without them is read as before.

### Changed

- **`/analysis-report` carries what a decision needs.** Introduction shows the decision context.
  Method describes the data sources (name, type, and description from the catalog; never the
  `connection` values) and the row counts through the pipeline (from the lineage diagram). The
  Results table gains Effect size / CI / N columns, each shown only when some metric has a value.
  Discussion gains Implications and Recommendation, and a new Appendix holds the lineage diagram
  and the notebook path. The skill stays read-only and computes no numbers; sections whose inputs
  are missing are omitted, so a report from an older analysis looks as it did.
- **`/analysis-auto` starts `/report-upload` after it builds a report.** The driver does not ask
  whether to upload; the approval of `/report-upload` is the only question.
- Development docs (Epic 11): `CLAUDE.md` holds only a summary and pointers; `CONTRIBUTING.md` keeps Setup / Common Commands /
  Testing / Security Checklist. `docs/UBIQUITOUS_LANGUAGE.md` gets its first edition, and
  `docs/ARCHITECTURE.md` gets a context map and a Domain Model class diagram.
- New development ADRs (Epic 11): [ADR-0010](docs/adr/0010-skill-tdd-structure-tests.md) (skill TDD reading),
  [ADR-0011](docs/adr/0011-domain-model-overview-in-architecture.md) (Domain Model overview),
  [ADR-0012](docs/adr/0012-single-pr-scope.md) (scope of non-Epic PRs).

### Removed

- **`.mcp.json` (user-facing).** The plugin payload is the repository root, so installed plugins
  (up to 0.8.0) carried a `.mcp.json` that registered the dev-only `spec-workflow` MCP server
  (`npx -y @pimzino/spec-workflow-mcp@latest`). The file is gone; the plugin now ships no MCP
  server configuration, matching the "No MCP server" invariant. If you added `spec-workflow` to
  your own setup on purpose, configure it in your project instead.
- `.spec-workflow/` (pre-fork steering docs and templates, superseded by `docs/design/` + `docs/adr/`).

### Fixed

- **`design_io`, `catalog_io`, and `premortem` failed in an installed plugin (since 0.7.1).**
  Claude Code puts the plugin's `bin/` on the Bash tool's PATH but does not export
  `CLAUDE_PLUGIN_ROOT` there, so the wrappers stopped with `CLAUDE_PLUGIN_ROOT is not set`.
  They now fall back to their own location to find the plugin root
  ([ADR-0017](docs/adr/0017-plugin-variables-not-in-bash-env.md)).

## [0.8.0] - 2026-07-08

Epic 10 (#47): a new `/analysis-report` skill that assembles a **distributable APA-style
Markdown report** from a concluded analysis, so results can be explained to others — not just
read in the notebook. Design: `docs/design/epic-10-analysis-report.md`; contract change:
[ADR-0008](docs/adr/0008-notebook-figure-manifest.md). The PyPI wheel's runtime
(`src/insight_blueprint`) is untouched — the surface is skills, the notebook contract, and docs.

### Added

- **`/analysis-report` — APA-style report assembly.** A read-only consumer that reads the design
  (`design_io get`), Insight Journal, notebook verdict, and figure manifest, and writes
  `.insight/reports/{id}.md` with English APA headings (Abstract / Introduction / Method /
  Results / Discussion→Limitations/Future Directions / References); narrative stays in the user's
  language. Requires a terminal status (`supported`/`rejected`/`inconclusive`). Each figure carries
  mandatory **Axes（軸の説明）** and **How to read（図の読み方）** captions. Template:
  `skills/analysis-report/references/apa-template.md`.

### Changed

- **notebook 8-cell contract extended for figures ([ADR-0008](docs/adr/0008-notebook-figure-manifest.md)).**
  The viz cell now saves each figure to `.insight/notebooks/{id}_fig{NN:02d}.png`, and the verdict
  cell records a `figures[]` manifest (`file`/`title`/`axes`/`how_to_read`) plus `metrics` in
  `{id}_verdict.json` — so `/analysis-report` embeds figures with axis + how-to-read captions
  without re-rendering, and the figure's truth lives with the producer. **Backward compatible**:
  a verdict lacking `figures` is treated as `[]` (graceful degrade — the report omits figures and
  notes it). `figures[].file` is constrained to a bare basename (no path traversal into a
  distributable artifact).
- **Pipeline wiring.** `/analysis-reflection` and `/analysis-auto` chain to `/analysis-report`;
  `/analysis-auto` offers report generation as a KEEP gate after a terminal conclusion. README,
  `CLAUDE.md`, and `docs/ARCHITECTURE.md` updated.

## [0.7.3] - 2026-07-06

Patch release closing the two open Epic 09 follow-ups (#40 / #41). Both are hardening /
documentation of the plugin **execution model** shipped in 0.7.1 — no change to the PyPI
wheel's runtime (`src/insight_blueprint` is untouched); the surface is the `bin/` wrappers,
`skills/_shared`, and docs. Source review: `.claude/docs/research/review-security-epic09.md`
(M1/M3/L3) and `review-docs-epic09.md` (F5).

### Security

- **`INSIGHT_BASE_DIR` / `--base-dir` is now a validated trust boundary (M1, #40).** The base
  flows into every read/write path, so it is no longer trusted verbatim. Two layers: the
  `bin/` wrappers (`design_io` / `catalog_io` / `premortem`) assert `${CLAUDE_PROJECT_DIR}`
  exists and that the base ends in `/.insight` **before** `mkdir` (folding in the L1 finding),
  and `design_io` / `catalog_io` gain `_resolve_base_dir()` which rejects an absurd anchor
  (filesystem root, the bare `$HOME`) after `Path.resolve()`. The `.insight` suffix is enforced
  only in the wrapper, so `--base-dir` back-compat and tmp-dir tests are unaffected.
- **Host-variable trust boundaries documented in [ADR-0006](docs/adr/0006-plugin-execution-model.md)
  (M3 / L3, #40).** Claude Code hooks take a single command string (no `argv` form), so
  `CLAUDE_PLUGIN_ROOT` is assumed a Claude-Code-controlled path free of shell metacharacters;
  `UV_PROJECT_ENVIRONMENT` ← `CLAUDE_PLUGIN_DATA` is recorded as the same class of host-var trust.

### Documentation

- **`package_allowlist.yaml` format & package-supply procedure (F5, #41).** New "Package
  allowlist — format & supplying packages" section in
  `skills/analysis-notebook/references/notebook-contract.md`: the file is an `import-name →
  pip-name` map (a boundary declaration, not an installer), and an allowlisted package outside
  the `notebook` extra is supplied to a run ephemerally with `--with <pip-name>` (no mutation of
  the read-only plugin env). `analysis-notebook/SKILL.md` and `docs/ARCHITECTURE.md` now link it.

## [0.7.2] - 2026-07-06

Patch release enriching the **upstream dialogue** of `/analysis-auto`. The autopilot's
single design gate collapsed at runtime into one direction pick, so methodology, figures,
and — most importantly — the actual data pull (SQL) never got a confirmation seat. This
release re-weights the gates toward the epistemic decision points
([ADR-0007](docs/adr/0007-upstream-judgment-gates.md), amending
[ADR-0005](docs/adr/0005-selective-autonomous-chaining.md)).

### Added

- **`data-extraction` gate** (design beat ③, before premortem) — `/analysis-auto` now
  surfaces the actual data-acquisition plan for confirmation before `design_io create`: the
  SQL query text drafted into `methodology.steps` for SQL sources, or the file + columns +
  filter for CSV/others, plus expected grain and a rough row/scan estimate. premortem then
  estimates cost against the **confirmed** query. A source with no SQL still gets this beat.

### Changed

- **`/analysis-auto` design confirmation is now four ordered beats** — hypothesis → methodology
  (+ metrics + explanatory roles + intent) → data-extraction → charts — each presented as its
  own AskUserQuestion so the user can adjust it, instead of a single "confirm the whole design".
  Downstream steps (premortem / notebook / journal) stay AUTO; friction is added only upstream.
- `/analysis-design` Step 2.6 and `/analysis-notebook` cell 2 note that, under the driver, the
  auto-drafted extraction query is user-confirmed and must not silently diverge at execution.

## [0.7.1] - 2026-07-04

Patch release fixing the **installed-plugin execution model** (Epic 09). v0.7.0's skill
commands assumed the dev-repo layout, so the published plugin did not actually run when
installed into a separate project. This release makes the plugin self-contained.

### Fixed

- **The plugin now runs when installed into a user's own project** (Epic 09). Previously
  skill commands assumed the repo cwd and an externally-installed `insight_blueprint`, so an
  installed plugin failed with `ModuleNotFoundError: No module named 'skills'`. Commands now
  go through `bin/` wrappers that execute in the plugin's own uv environment and target the
  user project's `.insight/` via `INSIGHT_BASE_DIR`; the validation hook ships with the plugin
  (`hooks/validate-design.py` + `hooks/hooks.json`) and enforces integrity in the user's
  project too ([ADR-0006](docs/adr/0006-plugin-execution-model.md))
- `/premortem` now reads `.insight/config.yaml` from the user's project (honors
  `INSIGHT_BASE_DIR` / `--base-dir`) instead of silently falling back to default risk
  thresholds
- Pre-write hook now fails **closed** for design documents on an internal error (was
  fail-open), so an unvalidated `*_hypothesis.yaml` write cannot slip through
- Fixed a mermaid parse error in the Epic 09 design doc sequence diagram

### Changed

- Notebook execution borrows the plugin's uv environment
  (`uv run --project ${CLAUDE_PLUGIN_ROOT} --extra notebook`) while keeping the user's cwd, so
  generated artifacts land in the user project's `.insight/notebooks/` and `.insight/lineage/`
- Docs: ARCHITECTURE gains a dev-vs-installed directory-layout section (path-resolution
  mechanisms); README dependency story clarified (the plugin is self-contained;
  `insight-blueprint-lineage` is needed only for hand-written `tracked_pipe` lineage);
  `analysis-design` hook path and README knowledge example corrected

## [0.7.0] - 2026-07-03

Lightweight migration (Epics E1–E8): the platform is now a Claude Code skills plugin —
skills + YAML + an embedded validation library, with no server, daemon, or SQLite.
First release under the PyPI name **`insight-blueprint-lineage`** (import name stays
`insight_blueprint`).

### Added

- New skill `/knowledge-extract` — Claude-native extraction of source-scoped domain knowledge from a concluded analysis, persisted via `catalog_io add-knowledge` (E5b)
- New skill `/analysis-review` — produce a design review batch (producer side of the review loop) via `design_io review-batch` (Epic 06)
- New skill `/analysis-notebook` — generate a marimo notebook from the design's methodology (8-cell contract), run it, and record results to the journal; optional `insight-blueprint-lineage[notebook]` extra (Epic 07)
- New skill `/analysis-auto` — guided autopilot that drives the pipeline and pauses only at genuine decision gates ([ADR-0005](docs/adr/0005-selective-autonomous-chaining.md), Epic 08)
- `catalog_io` / `design_io` server-free YAML helpers backing the skills; `catalog_io add-knowledge` write path (validate + upsert-by-key + atomic write) (E3, E3.5, E5b)
- Pre-write hook (`.claude/hooks/validate-design.py`) enforcing design-document schema + state transitions via `src/insight_blueprint/validate.py` (E2)

### Changed

- `/premortem` is now **report-only** — no approval tokens, no run history, no `.insight/premortem/` writes; it prints a static risk report and exits non-zero on HARD_BLOCK/HIGH (E5a)
- Catalog taxonomy is now **open strings**: source `type` and knowledge `category` accept any non-empty value (conventional values kept as `KNOWN_*` constants); `ColumnSchema`/`DataSource` allow extra fields (ADR-0004, E5c)
- Docs overhauled for public plugin release: corrected install commands and repo naming (`insight-blueprint-skills`), added Quickstart and status/review guidance
- PyPI distribution renamed to **`insight-blueprint-lineage`** to avoid colliding with the upstream `insight-blueprint` (MCP) package; the import name stays `insight_blueprint`. Install the optional lineage library with `uv add insight-blueprint-lineage`

### Fixed

- Path-traversal hardening in `design_io` / `catalog_io`: `design_id` / `source_id` are validated (`[a-zA-Z0-9_-]+`) before being interpolated into `.insight/` paths, closing an escape via `../`

### Removed

- MCP server, REST API, WebUI, and SQLite (E1–E4) — replaced by skills + YAML + `validate.py`
- `batch-analysis` skill and its harness (token / run-history / manifest / crash-recovery), superseded by Claude Code auto mode (E3.5, E5a)
- Pre-fork `.spec-workflow/specs/` design documents and the orphaned `_templates/` package (superseded by `docs/design/` + `docs/adr/`)

## [0.6.0] - 2026-06-16

### Added

- New skill `/rq-problematization` — generate impactful research questions via the Alvesson & Sandberg (2011) problematization framework: surface taken-for-granted assumptions across five types and challenge them with a devil's-advocate critic subagent (assumption-challenging over gap-spotting)
  - Positioned upstream of `/analysis-framing`: rq-problematization (theory-driven RQ) → analysis-framing (data grounding) → analysis-design. Does not chain directly to analysis-design — framing is the data-grounding gate
  - Re-generation path from `/analysis-reflection`: when a hypothesis is rejected/inconclusive, question the underlying assumption instead of only seeking a new angle
  - Bundled `evals/evals.json` — the repository's first eval suite, focused on gap-spotting regression and citation-fabrication checks

## [0.5.1] - 2026-04-21

### Fixed

- Remove `$schema` field from `.claude-plugin/marketplace.json` to restore plugin skill loading (#123)
  - Claude Code's marketplace validator rejected `$schema` as an Unrecognized key,
    causing the runtime to treat the plugin as disabled even when enabled in settings
  - This blocked all insight-blueprint skills (`analysis-design`, `analysis-framing`,
    `catalog-register`, `premortem`, etc.) from loading into the available skills list

## [0.5.0] - 2026-04-21

### Added

- New skill `/premortem` — pre-flight risk evaluation with approval token issuance (#117) — _the approval token was removed in E5a; `/premortem` is now report-only (see [Unreleased])_
- `spec-workflow` MCP server registered in `.mcp.json` (#118)

### Changed

- Batch analysis harness hardened for overnight stability (#117)
  - Flat manifest status contract with `completed` state (was nested `execution.status`)
  - 2-stage design hash verification for safe resume after crash
  - Launcher-owned `finalize_run` for consistent lifecycle termination
  - Hash mismatch detection in claude step + stub env toggles
  - User-facing documentation for risk levels, `.insight/config.example.yaml`, crash recovery

### Fixed

- `uv.lock` self-reference version out of sync with `pyproject.toml` (#119)

### Chore

- Ignore per-clone runtime stubs under `.insight/` (#120)

## [0.4.2] - [0.4.4]

Version bumps and maintenance releases. See git history for details:
`git log v0.4.1..v0.4.4 --oneline`.

## [0.4.1] - 2026-04-06

### Added

- `/batch-analysis` skill for overnight batch execution of queued analysis designs
- `batch-prompt.md` headless orchestration prompt with 8-cell notebook contract
- `next_action` field convention for queue management (`batch_execute` type)
- Claude Code Plugin distribution format (`.claude-plugin/plugin.json`, `.mcp.json`)
- Plugin validation CI job (`plugin-validate`)
- data-lineage Python package prerequisites check
- Migration guide in README
- Custom marketplace for plugin distribution

### Changed

- Skills moved from `src/insight_blueprint/_skills/` to `skills/` (repository root) for Plugin auto-discovery
- Rules (`_rules/`) integrated into SKILL.md definitions
- Extension policy and optional package note added to CLAUDE.md managed section

### Removed

- `upgrade-templates` CLI subcommand
- Skill/rule copy logic from `storage/project.py` (~400 lines)

## [0.4.0] - 2026-03-20

### Added

- `--mode server` for team deployment: serves WebUI + MCP SSE on the same HTTP port
- `--mode headless` for lightweight deployment: MCP SSE only (no WebUI)
- `--host` and `--port` options for server/headless mode (default: 0.0.0.0:4000)
- `--no-browser` flag to suppress browser auto-open in full mode
- Concurrent write safety with `threading.Lock` on `write_yaml`

### Deprecated

- `--headless` flag: use `--no-browser` instead (flag still works with deprecation warning)

## [0.3.0] - 2026-03-17

### Added

- `get_review_comments` MCP tool for reading review batches (closes read/write asymmetry in review workflow)
- `/analysis-revision` skill for structured revision of review comments with per-comment tracking

### Changed

- Added methodology and analysis_intent as reviewable sections in WebUI inline comments

## [0.2.0] - 2026-03-11

### Added

- Analysis Framing skill for structuring analysis scope and approach
- Unified 6-skill chaining: analysis-design → analysis-framing → analysis-journal → analysis-reflection → catalog-register → data-lineage
- `--version` flag for CLI version display

### Changed

- Upgraded shadcn from 4.0.0 to 4.0.2
- Restructured README to prioritize user experience

### CI

- Added Dependabot auto-merge for patch updates

## [0.1.0] - 2026-03-10

### Added

- Analysis Design management with hypothesis-driven workflow
- Data Catalog for domain knowledge and caution registration
- Review workflow with status transitions (draft → reviewing → approved/revised)
- Domain Knowledge suggestion for analysis designs (4 matching strategies)
- Data Lineage tracking for data transformations
- WebUI Dashboard with 2-tab navigation (Designs / Catalog)
- Bundled Skills: analysis-design, analysis-journal, analysis-reflection, catalog-register, data-lineage
- Typed verification models: ExplanatoryVariable, Metric, ChartSpec, Methodology
- YAML direct edit resilience (extra field preservation + corrupt file isolation)
- SQLite FTS5 full-text search index

[unreleased]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.21.0...HEAD
[0.21.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.20.0...v0.21.0
[0.20.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.19.0...v0.20.0
[0.19.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.18.0...v0.19.0
[0.18.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.17.0...v0.18.0
[0.17.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.16.0...v0.17.0
[0.16.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.15.0...v0.16.0
[0.15.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.14.1...v0.15.0
[0.14.1]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.14.0...v0.14.1
[0.14.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.12.0...v0.13.0
[0.12.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.11.0...v0.12.0
[0.11.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.7.3...v0.8.0
[0.7.3]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.7.2...v0.7.3
[0.7.2]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.7.1...v0.7.2
[0.7.1]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.5.1...v0.6.0
[0.5.1]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.4.4...v0.5.0
[0.4.1]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/etoyama/insight-blueprint-skills/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/etoyama/insight-blueprint-skills/releases/tag/v0.1.0
