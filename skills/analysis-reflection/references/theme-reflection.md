# /analysis-reflection — Theme Reflection

The reflection across the designs of a theme, from Step 0 of
[the /analysis-reflection SKILL.md](../SKILL.md).

## Theme Reflection

Writes the current answer of each node of the theme's question tree, then shows the next
candidates and records the decision the analyst takes. An answer is a list
of statements, and each statement cites the journal events it rests on. The analyst sees
an answer only after the tree check has passed (ADR-0025).

### Step T1: Load the tree, its designs and their journals

1. `tree_io get --theme {theme_id}` — load the question tree (JSON). If it prints `{}`,
   the theme has no tree: "このテーマには論点ツリーがない。/analysis-framing {theme_id} で
   主題と論点を決めよう" → exit.
   If `{path}` in `tree_io: no tree at {path}` on stderr is not under this project's
   `.insight`, run it again from the project directory: never `cd` before, since `tree_io`
   reads the `.insight` of the directory it is run from.
2. `tree_io progress --theme {theme_id}` — the progress of each node, derived from its
   linked designs. Each node has `progress`, its word (`not_started` 未着手,
   `investigating` 調べている, `stopped` 止めた, `analyzed` 分析済み), and `below`, how many nodes under it have
   each word. A node with no design of its own but one below it has `progress` `null` and
   is shown by its `below`, as the page shows it (Step T5).
3. For every design id in the `design_ids` of any node, read
   `.insight/designs/{design_id}_journal.yaml` with the Read tool. A design without a
   journal has no events to cite.
4. `tree_io position --theme {theme_id}` — where the walk stands. When its `state` is
   `concluded` and every design of its `design_ids` has the stage `stopped` in `nodes`, the
   round has no result to answer from. Tell the analyst "今回任せた分析はどれも止めたので、
   新しい結果は無い。" and show each of those designs with its 止めた理由, as
   `design_io stage --id {design_id}` gives it in `stop_reason`. Then ask whether the current answers stay as
   they are. When they stay, write no answer for this round: skip Steps T2 to T5 and go to
   Step T6. When the analyst wants an answer changed by what a reason says, go on with
   Step T2 as usual.

### Step T2: Write the statements of each node

Work from the leaves up to the root question. For each node, the source is the journal
events of the designs linked to the node and to the nodes below it. A node whose branch
holds no journal event gets no answer in this round: say so in Step T5 instead.

Each statement has a `kind`, a `text` and `cites`:

| `kind` | What the statement does |
|---|---|
| `claim` | これまでわかっていること — what the cited events let you say about the node's question |
| `undetermined` | まだ決められないこと — what the cited events leave open, even though the analysis ran |
| `weakening` | 注意すべきこと — a cited event that speaks against a claim, or a limit on how far it reaches |

Rules for every statement:

- Every statement cites one or more journal events (`{design_id}-E{nn}`) in `cites`.
  A sentence you cannot cite is not written.
- The answer of a parent node rests on the events of the designs linked to the nodes
  below it, read again for the parent's question: the source is the journal event, not
  the answer of a child. Never answer a parent from the progress of its children or from
  a count of them ("3つのうち2つが分析済み" is not an answer).
- A number appears only the way a cited event wrote it, sign included. Never compute a
  number: no ratio, difference, sum, average, rounding or unit conversion of recorded
  numbers. When the answer needs such a value, say that it is not recorded; the notebook
  computes it and the journal records it before an answer may state it.
- No date in `text`. The digits of `11月21日` are read as numbers and reported as
  violations. An id of a node, of a design linked to a node or of its event, and the N of
  "N回目の振り返り" up to the current round, are not read as numbers; any other id is.
  Event ids go in `cites`, so an answer rarely needs one in `text`.
- An event of kind `evidence` with `direction: contradicts` that bears on the node is
  cited in a `weakening` statement, not left out.

A node that already has an answer starts from the statements of its current answer in
`tree_io get`, not from a blank draft. The new results are the journal events recorded
since that answer (for an answer with no `created_at`, the events of the branch it does
not cite). The display compares the two answers word for word: a statement that differs
by one character under the same cite shows as 「言っていることが変わった」 (ADR-0056), and a
rewording the reader cannot tell from a change buries the change that matters.

- A statement whose meaning the new results do not change is sent character for
  character as the current answer has it: the same `kind`, the same `text` and the same
  `cites`. Rewrite only the statements the new results change, and add a statement for
  what a new result says.
- Never restyle a number, a unit or the order of the words of a kept statement, and never
  merge or split kept statements. Move a statement to another `kind` only when its meaning
  changes (a claim that a new result leaves open becomes `undetermined`) or a rule of this
  step requires it.
- A statement no new result bears on is changed only where it breaks a rule of this step
  (a `contradicts` event cited outside a `weakening`, a claim that says more than its cited
  events) or where `tree_io answer` or `tree_check` reports a violation of it. Change only
  that part, and name the rule or the violation in Step T5. Reading old results again in
  other words is not a reason to change a statement.
- When the 主題の版 has gone up since a node's answer (`root_revision` is lower than the
  current one), rewrite that answer for the new 主題 where its question asks something new,
  and say so in Step T5. A statement the new 主題 does not change still keeps its words.

### Step T3: Write the answers through tree_io

#### Before writing: results no answer above rests on

Ask it once, before the first `tree_io answer` of this reflection. When you come back to
this step from a violation or from Step T4, do not ask again.

First apply the rules of Step T2 to the drafts: a `contradicts` event that bears on a node
is cited in its `weakening`, not offered. Then, for the root and every node with nodes below
it, take every event cited by the answer of a node below it (its draft, or its current
answer when it gets none in this round) but not by its own draft. Split them in two:

- An event that no answer of this node has cited: 「まだ答えに入れていない分析結果」.
- An event that an earlier answer of this node cited and the draft does not:
  「前は答えの根拠にしていて、今は外している分析結果」. Name the last round that cited it.

When no node leaves an event out, skip the question and send the answers. Otherwise show
one block for each node that leaves an event out, each event by its content, and ask once
for all of them:

```
主題「{question}」の答えに、まだ入れていない分析結果:
  - {content}（「{question of the node whose answer rests on it}」の答えが根拠にしている）
  - 人に聞いた答え: {content}（「{question of the node whose answer rests on it}」の答えが根拠にしている）
前は答えの根拠にしていて、今は外している分析結果:
  - {content}（{round}回目の振り返りの答えまで根拠にしていた）

「この中から、答えの根拠にする分析結果を選んでください。選ばなくても答えは書けます。」
```

Use 「論点「{question}」の答えに」 instead of 「主題「{question}」の答えに」 for a node that is not
the root. A `hearing` event is listed as 人に聞いた答え, never as 分析結果. The analyst sees the
contents of journal events here, not the statements of a draft: no answer reaches them
before the tree check (ADR-0025).

The analyst decides. Wait for the answer, and send nothing before it: once the answers are
written, taking in a result the analyst chooses needs another round. For each result they
choose, add or rewrite the statements of the draft that rest on it, under the rules of Step
T2, and do not ask again for the nodes this changes. When they choose none, the answers are
written without them. Never cite a result the analyst did not choose from this list. The
list holds only what the drafts leave out: a new result that a draft already cites under the
rules of Step T2 is not on it.

#### Send the answers

Send the answers of every node of this reflection in one call. One call is one reflection
round: `tree_io` sets `round` and `root_revision` itself, appends the answers, and leaves
earlier rounds as they are.

```bash
echo '{"answers": [
  {"node_id": "LIB-Q02", "statements": [
    {"kind": "claim", "text": "状態の履歴から取消を除き、期限を迎えた予約同士を比べられた", "cites": ["LIB-H01-E01"]}
  ]}
]}' | tree_io answer --theme LIB
```

A long payload may not pass the shell as an inline string. Write it to a temporary JSON
file and run `tree_io answer --theme {theme_id} < {file}` instead.

Never write `.insight/themes/{theme_id}_tree.yaml` with the Write or Edit tool: the hook
rejects a rewritten answer, and only `tree_io answer` checks the answer before it lands.

`tree_io answer` checks the answers first and reports on stdout:

- Exit code 0: the answers are written. `written` lists the nodes that got an answer in
  this round, each with `previous_round` (`null` for a first answer) and `restated`
  (`true` when the statements are the same as before and only the root revision is newer).
  `unchanged` lists the nodes whose statements equal their current answer under the
  current root revision; nothing is written for them. `round` is the last round the tree
  now holds.
- Exit code 3: `violations` is not empty and `tree_io` wrote nothing, for any node. Fix
  each violation in your draft and send the whole call again.
- Exit code 1: nothing was written, and the reason is on stderr. When it names the
  payload (unknown node, a missing field, JSON that does not parse), fix the payload and
  send it again. When a tree, design or journal file cannot be read or holds the same
  event id twice, rewriting the answer cannot help: report the message to the analyst and stop.

| Violation `kind` | How to fix it |
|---|---|
| `number-not-cited` | The number in `text` is in none of the cited events; the violation's `fix` says so. Rewrite it the way the record wrote it: the same digits and the same sign. When the record states the direction in words ("3.2ポイント減った"), use those words instead of a sign ("−3.2"). If another event of the branch records the number, cite it, a value to compare with ("1を超える") included. If no event records it, the number was computed or remembered: take it out |
| `missing-event` | The cited id is not in the journal of its design. Cite the event you actually read, or take the cite out |
| `unlinked-design` | The cited event belongs to a design that is linked neither to the node nor to a node below it. Cite an event from the node's own branch, or take the cite out |

Never edit a journal to make an answer pass, and never add a number to a journal that the
analysis did not produce. When a statement still violates after one rewrite, remove the
statement from the draft and keep a note of its text and the violation for Step T5. When
every statement of a node is removed, send no answer for that node in this round.

### Step T4: Check the tree after writing

Run `tree_check --theme {theme_id}`. It reads the tree and the journals and writes nothing.

- Exit code 0: no violation.
- Exit code 1: the current answer of some node violates. `tree_io answer` already stopped
  the answers of this round, so this is an answer from an earlier round whose journal has
  changed since. Write a new answer for that node (Steps T2 and T3) and check again, once.
  When the node has no event left to cite, or the check still reports it, leave the node:
  an answer cannot be withdrawn. List it under "Stale answers" in Step T5 with its
  violations, show its answer nowhere, and go on with the other nodes.
- Exit code 2: the check could not run (the message is on stderr). Do not rewrite any
  answer: nothing is known to be wrong with them. Report the message to the analyst and stop.

Before Step T5, run `tree_io render --theme {theme_id}` so that the HTML of the tree shows
the new answers. With a stale answer left, tell the analyst that the HTML still shows it.

Show no answer to the analyst before `tree_check` has run, and never show an answer that
`tree_check` reports.

### Step T5: Present the current answers

```
── Theme Reflection: {theme_id}（{round}回目の振り返り{。主題を{n}回見直した}）──
主題: {root question}

{node_id}  {question}
  Progress: {未着手 | 調べている | 止めた | 分析済み}{　この論点の下に置いた論点 {N} つ: 分析済み a、止めた b、調べている c、未着手 d}
  Answer（{round}回目の振り返り{、見直す前の主題への答え}）:
    [これまでわかっていること] {text}  ← {cites}
    [まだ決められないこと] {text}  ← {cites}
    [注意すべきこと] {text}  ← {cites}

── Changed in this round ──
  - {node_id}: 初めての答え | {previous_round}回目の振り返りから変わった（{reason}） | 主題を見直し、同じ文で書き直した

── Unchanged ──
  - {node_id}

── Not answered ──
  - {node_id}: {引用できる出来事がまだ無い | すべての文を除いた}

── Removed statements ──
  - {node_id}: 「{text}」 — {violation kind}: {violation text}

── Stale answers ──
  - {node_id}: {round}回目の振り返りの答えは記録と合わなくなった — {violation kind}: {violation text}

── まだ答えに入れていない分析結果 ──
  - {node_id}: {content}

── 前は答えの根拠にしていて、今は外している分析結果 ──
  - {node_id}: {content}（{round}回目の振り返りの答えまで根拠にしていた）
```

After the render of Step T4, run `tree_io changes --theme {theme_id}`. It writes nothing and
derives what each answer changed the same way the page of the tree shows it. Take what
changed and the results the answers leave out from the output of `tree_io changes`, never
from the drafts: in Step T3 the answers were not written yet, so the list there came from
the drafts.

- Changed and unchanged nodes come from `written`, `previous_round`, `restated` and
  `unchanged` in the output of `tree_io answer`. For a changed node, show the previous
  answer next to the new one. A `restated` answer says the same as before: say so
  instead of calling it changed. For a changed node, say what changed it in `{reason}`:
  the new result each rewritten statement rests on (by its content, as 分析結果 or
  人に聞いた答え), the rule of Step T2 or the violation a statement broke, or the new 主題.
  The record keeps no reason, so this is the one place the analyst hears it.
  The results come from `evidence` in the entry of `answer_changes` for that node and this
  round: say each by its content, with the word the page uses for its kind (`newly_cited`
  新しく根拠にした, `dropped` 根拠から外した, `reworded` 言っていることが変わった).
- Under the last two headings, list each entry of `uncited_below` under the node it is
  keyed by, by the content of its event (a `hearing` event as 人に聞いた答え). An entry whose
  `last_cited_round` is `null` goes under まだ答えに入れていない分析結果; otherwise it goes
  under 前は答えの根拠にしていて、今は外している分析結果, with `last_cited_round` as `{round}`.
  These are the results the analyst did not choose in Step T3. Leave out a heading with nothing under it. The analyst sees them again here, before the
  decision. When a statement that rests on a result the analyst chose was removed in Step
  T3, say so next to it under Removed statements.
- Say the progress the way the page does. The word comes from `progress`. When `below`
  is not empty, add its counts after the word: `この論点の下に置いた論点 {N} つ: 分析済み a、止めた b、調べている c、未着手 d`,
  and `主題の下に置いた論点 {N} つ: 分析済み a、止めた b、調べている c、未着手 d` for the root question.
  `{N}` is their sum, and a word with no count is left out. A node whose `progress` is
  `null` shows the counts alone and is never shown as 未着手: it has no design of its own,
  but one below it (ADR-0057).
- A node under "Stale answers" shows its question and progress, not its answer.
- An answer whose `root_revision` is lower than the current root revision answers an
  earlier root question: mark it "見直す前の主題への答え". After two or more revisions, say
  before which one: "{revision}回目の見直しの前の主題への答え".
- `{n}` in the heading is the number of root revisions minus one. Leave out
  `。主題を{n}回見直した` while it is 0.
- In every sentence for the analyst, call the root question 主題, an answer to an earlier
  root revision 見直す前の主題への答え, and reflection round N N回目の振り返り. Never show the
  word 版 or the number of a root revision: say how many times the 主題 was revised
  (主題を1回見直した), and nothing of it while it was never revised (ADR-0055). The YAML
  keys and `tree_io revise-root` keep the word root.
- List every removed statement with its violation. Never drop one silently: the analyst
  must know what the answer does not say.
- Show the `path` that `tree_io render` printed: the analyst reads the tree there.
  To hand it over by URL, the analyst runs `/tree-upload {theme_id}`, which asks before
  sending. Say so in one line; do not start it.
- Go on to Step T6. The reflection is not finished until the analyst has seen the next
  candidates and has been asked for a decision (Step T7).

### Step T6: Show the next candidates

`tree_io candidates --theme {theme_id}` lists the next candidates: every node other than
the root that has no design linked to it or to a node below it. `[]` means every node is
started: say so and go to Step T7.

A candidate can carry three notes. Draft them where they help the analyst choose:

| Note | What it holds |
|---|---|
| `ask` | 人に聞く問い — one question to put to a person who knows what the data cannot tell (how a status is entered, when a rule changed, who decides) |
| `changes_if` | その答えで変わる判断 — what the analyst does next under each answer. Needs an `ask` |
| `known` | 分かっていること — what the catalog and the domain knowledge already tell about the node |

```bash
echo '{"ask": "本を確保してから実際に通知するまで、曜日によって手順は変わりますか",
  "changes_if": "変わるなら通知の時点を調べる論点に進み、変わらないなら開館日数の論点を深める",
  "known": "今の抽出表に送信日時の列は無い"}' | tree_io candidate --theme LIB --node LIB-Q03
```

- For `known`, read the data sources with `catalog_io list` (names, `schema_info`, tags) and
  the domain knowledge in `.insight/rules/`. `catalog_io list` leaves `connection` out, and
  the source YAML files are never opened instead
  ([ADR-0022](../../../docs/adr/0022-connection-reaches-only-the-notebook.md)).
  Never write a value of `connection` (a path, a host, a project id, a table location, a
  credential) into a note: the tree is read by every skill and shown in the HTML.
- Never put into `known` what you did not read in the catalog, the domain knowledge or a
  journal. The notes are not checked against the record, so a guess written there reads as a fact.
- A candidate needs no note. Write an `ask` only when a person, not the data, holds the
  answer. Do not invent a question to fill the field.
- `tree_io candidate` replaces the three notes of the node and keeps an answer that was
  already heard. It rejects a changed `ask` once an answer is recorded, because the answer
  answers the old question: leave such a node as it is.
- If the command exits non-zero, show stderr. Nothing was written.

Present the candidates:

```
── Next candidates ──
{node_id}  {question}
  寄与: {contribution}
  人に聞く問い: {ask}
  その答えで変わる判断: {changes_if}
  分かっていること: {known}
  聞いてきた答え: {answer}（{answered_by}、{answered_at}）
```

Leave out a line whose note is empty.

### Step T7: Record what the analyst heard and decided (KEEP gate)

This is a KEEP gate. Ask the analyst two things and wait for their answer.

**1. What they heard.** Ask whether they bring an answer to any `ask`, from this round or
an earlier one. For each answer, take the answer in the analyst's words, who answered, and
the date:

```bash
echo '{"answer": "金曜の夕方に確保した本は、月曜の朝にまとめて通知している",
  "answered_by": "予約担当の図書館員",
  "answered_at": "2026-11-20"}' | tree_io hear --theme LIB --node LIB-Q03
```

- Never fill `answered_by` or `answered_at` yourself, and never guess today's date for
  them. If the analyst leaves one out, ask for it; `tree_io` rejects an answer without both.
- The node must already have an `ask` (Step T6). Recording again replaces the answer.
- The answer stays on the candidate. It cannot be cited in a current answer until it is in
  a journal: when a design is made on that node, `/analysis-design` copies it into the
  design's journal as a `hearing` event.

**2. The decision.** Show the nodes the investigation is at: the `node_ids` of
`tree_io position --theme {theme_id}`, every node the last decision names. They are the
current nodes of the table below. Then ask which of the four the analyst
chooses. For the first three, ask which node or nodes come next and why. The analyst may
choose several nodes to hand over together: `/analysis-framing` 4d, "Several nodes in one
decision", says which nodes go together and how the decision holds them:

| `kind` | What the analyst chooses | `node_id` |
|---|---|---|
| `deepen` | 深める — keep investigating a current node or a node below it | a current node, or a node below one |
| `return` | 親に戻る — leave the current nodes for a parent or another branch | a node that is neither a current node nor below one |
| `close` | 区切る — stop here for now | a current node |
| — | 主題そのものを見直す — what was found shows that the root question itself, or its aim, asks the wrong thing | none |

```bash
echo '{"kind": "return", "node_id": "LIB-Q03",
  "reason": "数え方は定まった。次は通知が期限に間に合っているかを確かめる",
  "cites": ["LIB-H01-E01"]}' | tree_io decide --theme LIB
```

- Never choose the kind, the node or the reason yourself. Keep the reason in the analyst's
  words. You may lay out what each choice would lead to; the choice is the analyst's.
- `cites` holds the journal events the reason rests on (ADR-0058). When the reason rests on
  a result of the analysis or on an answer a person gave, find the journal event that
  records it among the journals read in Step T1 and put its id in `cites`. An event of any
  design linked to a node of the tree can be cited, not only one on the next node: the
  result of one node is often the reason to go to another.
- When the reason rests on no journal event (a deadline, a priority, a choice of where to
  begin), send the decision without `cites`. Never add a cite the reason does not rest on:
  a cite that only looks like backing misleads the reader more than none.
- Decisions are append-only: one that is written cannot be changed or removed. Before you
  send it, read the decision back to the analyst (kind, node, reason) in one line, and under
  it each cited event as "根拠にした分析結果: {content}" (a `hearing` event as "根拠にした、
  人に聞いた答え: {content}"). The analyst confirms that these are what the reason rests
  on, and may take one out or name another.
- Never send a `round`. `tree_io` sets it to the last reflection round, the one whose
  answers the analyst saw.
- `tree_io decide` checks a decision that has `cites` before it writes. Exit code 3:
  `violations` on stdout is not empty and `tree_io` wrote nothing. Show each violation to
  the analyst and ask again; send the decision once more only with their answer.

  | Violation `kind` | What to ask the analyst |
  |---|---|
  | `number-not-cited` | A number in the reason is in none of the cited events; the violation's `fix` says so. Ask whether another event records it (then cite that one too, a value to compare with such as "1を超える" included), or whether they say the reason again the way the record wrote the number, or without it. An id of a node, of a linked design or of its event, and the N of "N回目の振り返り" up to the current round, are not counted; a date and any other id are: ask for the reason without it |
  | `missing-event` | The cited id is not in the journal of its design. Cite the event you actually read, and read it back again |
  | `unlinked-design` | The cited event belongs to a design that is linked to no node of the tree. Ask whether the design belongs on a node (`/analysis-framing {theme_id}` links it), or take the cite out with the analyst's word |

- Never reword the reason yourself to pass the check, and never drop the `cites` to pass
  the check: a reason without cites is not checked, so that would hide the number instead
  of fixing it.
- Exit code 1: nothing was written. stderr says which rule the kind and the node broke
  (for example a `deepen` that leaves the current node), or that a cite is not an event id:
  show it and ask again. When stderr says a cited event id appears twice in its journal, or
  a journal cannot be read, asking again cannot help: report the message to the analyst and stop.
- If the tree has no decision yet, there is no current node: say "最初に調べる論点がまだ
  決まっていない。/analysis-framing {theme_id} で決めよう" and write no decision here.
- The analyst may leave the decision open. Then write nothing and say that the tree keeps
  its last decision.

主題そのものを見直す is not a `kind`, and no decision is written for it: a decision names
the node to investigate next, and this choice names none. When the analyst chooses
主題そのものを見直す, go to `/analysis-framing {theme_id}` and run only its 4c, "The root
question or the aim", which shows the old and the new 主題 side by side and asks whether
to record the change as a revision of the 主題 (主題を見直す). From there, do not go on to 4d or 5b of that skill: 4d asks for the
next node, and this gate asks it. Never run `tree_io revise-root` from here, and never draft
the new 主題 before the analyst has said what is wrong with the current one. After the
revision, run `tree_io render --theme {theme_id}` and show its `path`, so that the page
shows the new 主題 (4c does not render it; 5c does, and it is skipped), then come back to
this gate and ask the decision again, now for the three kinds: which
node comes next under the new 主題, and why. If the analyst then leaves the revision undone, the gate still stands:
ask which of the three they choose, or leave the decision open.

After a `hear` or a `decide`, run `tree_io render --theme {theme_id}` again and show its
`path`. Then suggest what to do next:

- After `deepen` or `return`: "次の論点の Framing Brief を出すなら /analysis-framing {theme_id}"
- After `close`: "区切った。再開するときは /analysis-framing {theme_id}"
- "主題か到達点を変えるなら /analysis-framing {theme_id}"
- "分析設計の結論を出すなら /analysis-reflection {design_id}"
