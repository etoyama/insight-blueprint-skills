# /analysis-reflection — Theme Reflection

The reflection across the designs of a theme, from Step 0 of
[the /analysis-reflection SKILL.md](../SKILL.md).

## Theme Reflection

Writes the current answer of each node of the theme's question tree, then shows the next
candidates and records the decision the analyst takes. An answer is a list
of statements, and each statement cites the journal events it rests on. The analyst sees
an answer only after the tree check has passed (ADR-0025). A statement of the root's answer
may be the analyst's view, in the analyst's own words (ADR-0068).

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

The draft of the root and of a node with nodes below it does not yet cite an event of a
design linked only to a node below it that its current answer does not cite, other than a
`contradicts` event the rules below make it cite. A statement kept from the current answer
keeps its cites. A new result from below enters an answer above only after the analyst
confirmed it in Step T3 (ADR-0069). The root's draft is finished there, after the
analyst's view.

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
  (a `contradicts` event cited outside a `weakening`) or where `tree_io answer` or
  `tree_check` reports a violation of it. Change only that part, and name the rule or the
  violation in Step T5. Reading old results again in other words is not a reason to change
  a statement.
- A claim of the current answer that no new result bears on and that seems to say more
  than the events it cites is sent as the current answer has it, and asked about in Step
  T3: the analyst decides whether to keep, weaken or drop it (ADR-0069). Never weaken or
  drop it on your own. A claim a new result bears on is rewritten for that result as above,
  and is not asked about.
- When the 主題の版 has gone up since a node's answer (`root_revision` is lower than the
  current one), rewrite that answer for the new 主題 where its question asks something new,
  and say so in Step T5. A statement the new 主題 does not change still keeps its words.
- A statement with `analyst_view` is sent character for character in every later round,
  with the mark, as the analyst wrote it (ADR-0068). Where a rule of this step, a new
  result or a new 主題 would change it, ask the analyst in Step T3, next to the view: show
  the sentence and say what would change it. It changes only when the analyst says how it
  now reads, and then it reads exactly as they say.

### Step T3: Write the answers through tree_io

#### Before writing: the analyst's view of the subject

The answer of the root starts from how the analyst sees the results (ADR-0068). Ask it
once, after the drafts of the nodes below the root and before the question of the next
section. Ask only about the root: never ask it about another node. When you come back to
this step from a violation or from Step T4, do not ask again. When no journal event of the
tree was recorded since the current answer of the root, do not ask: the round has no
result to see, and the root's draft is its kept statements.

```
この回に結果が出た分析（{N}つ）
  {design_id} {title}　あなたの結論: 「{content}」

主題「{question}」
いまの答え（{round}回目の振り返り）
  [これまでわかっていること] {text}
  [注意すべきこと] {text}
  [まだ決められないこと] {text}

「この回の結果は、主題の答えにどう効きますか。
 いまの答えを支える・いまの答えを変える・まだ言えない、のどれに近いかと、そう見る理由を、あなたの言葉で書いてください。
 分析をまたいだ見立てで構いません。根拠にする分析結果は、あなたの見立てを聞いた後に、こちらで探して勧めます。
 見立てを書かずに、エージェントの下書きから始めることもできます。」
```

- この回に結果が出た分析 lists every design whose journal got an event since the current
  answer of the root. あなたの結論 is the content of its `conclude` event; leave it out for
  a design that has none.
- いまの答え is the current answer of the root in `tree_io get`, as an earlier round wrote
  it, with （あなたの見立て） after the word of the kind of a statement with `analyst_view`.
  The analyst sees no statement of a draft here (ADR-0025).
- When the root has no answer yet, list every design whose journal holds an event, leave
  out いまの答え and the line that names the three directions, and open the question with
  「この回の結果から、主題についていま何が言えますか。あなたの言葉で書いてください。」
  instead of its first two lines.

Wait for the reply. What happens next depends on it:

- When the analyst writes a view, the view becomes one statement of the root's draft with
  `"analyst_view": true` and a `text` exactly as the analyst wrote it, line breaks included.
  Never reword, shorten, split or merge it, and never correct a number in it. You choose its
  `kind` and the analyst confirms the place in the next section. Its `cites` are the
  results the analyst confirms there.

  ```json
  {"kind": "claim", "text": "期限切れは分館より曜日で決まると見る", "cites": ["LIB-H04-E02", "LIB-H05-E03"], "analyst_view": true}
  ```

  Then draft the other statements of the root under the rules of Step T2, for what the
  view does not say: a limit on it, a question it leaves open.
- When the analyst starts from the draft, you write the draft of the root under the rules
  of Step T2 and no statement carries `analyst_view`.
- What the analyst writes beside the view (a question to you, an instruction) is not part
  of it. When you cannot tell where the view ends, ask.
- A view of an earlier round stays beside the new one, sent as Step T2 says, unless the
  analyst says the new one replaces it. The next section shows both, so the analyst can
  say so there.

#### Before writing: results no answer above rests on

Ask it once, after the reply to the view and before the first `tree_io answer` of this
reflection. When you come back to this step from a violation or from Step T4, do not ask
again.

**The list.** First apply the rules of Step T2 to the drafts: a `contradicts` event that
bears on a node is cited in its `weakening`, not offered. Write the drafts to a temporary
JSON file in the shape `tree_io answer` takes (below), without the statement of the view,
which has no `cites` yet. Leave out of the file a node whose draft has no statement yet,
as the root's often is in its first round: the command then lists every result below it.
Run:

```bash
tree_io changes --theme {theme_id} --with-answers < {file}
```

It writes nothing. On exit code 1 nothing is listed and the reason is on stderr: fix the
file when it names the payload, and otherwise report the message to the analyst and stop.
For the root and every node with nodes below it, `uncited_below` holds
every event cited by the answer of a node below it (its draft, or its current answer when
it gets none in this round) but not by its own draft. Never build the list by hand: the
command splits it the way `tree_io changes` and the page split it after writing. The
`statements` in its output are drafts that are not checked yet: never show them to the
analyst, who sees each event by its content (ADR-0025).

Each entry falls in one of three groups:

- `shown_before` is `false` and `last_cited_round` is `null`: a result new to the list in
  this round, which you recommend for the answer of that node or not.
- `shown_before` is `true`: a result shown in an earlier round that no answer took, which
  the question gives as a count, not by its content.
- `shown_before` is `false` and `last_cited_round` is a round: a result an earlier answer
  of the node rested on and the draft does not, shown with that round.

**What you recommend.** Recommend a new result when the answer of the node needs it: for
the root, when it bears out, limits or leaves open what the view says (what your draft
says, when the analyst started from the draft). A detail of a result you already
recommend, a result that speaks of something the node's question does not ask, and a
candidate for the next analysis are not recommended. Give each recommended result one line
of reason: the part of the view or of the answer it bears on, and whether it goes in as
これまでわかっていること, 注意すべきこと or まだ決められないこと. For each result you do not
recommend, say why not in a few words. The reason is said here only: never write it into a
statement, and the record keeps none (ADR-0069).

Raise a result shown before to the recommended ones only when a result of this round
changes what it means: a new result bears it out, speaks against it, or answers what it
left open. Its reason names the result of this round that changes it, and its line ends
with （前の回にも見せた）. Every other result shown before stays in the count.

**The question.** Skip the question and send the answers only when no node leaves an event
out, the analyst wrote no view, no statement with `analyst_view` needs asking about
(Step T2) and no claim seems to say more than its cites. Otherwise show one block for
each node that leaves an event out or has a claim that seems to say more than its
cites, the root first, and ask once for all of them. A block holds these parts in this
order, and a part with nothing in it is left out:

1. **The view** — in the block of the root only, when the analyst wrote one: the view as
   written, the `kind` you place it in, and the numbers of the results it will rest on.
   Under it, every statement with `analyst_view` of an earlier round, as written: it stays
   unless the analyst replaces it, and where Step T2 says to ask about it, say what would
   change it.
2. **Recommended** — the results you recommend, each with its reason on the next line.
3. **Not recommended** — the other results new to the list in this round, each with why not.
4. **Shown before** — the count of the results shown before that you did not raise.
5. **Dropped** — the results an earlier answer rested on and the draft does not.
6. **Overstated** — every claim of the node's current answer that seems to say more than
   the events it cites and that Step T2 keeps as it is: the sentence as written and what its
   cited events say. Only a claim of the current answer is listed, never the view of this
   round. A claim with `analyst_view` that seems to say more is listed here with
   （あなたの見立て）, not again under **The view**, and its line asks for the analyst's
   words. A claim the analyst kept in an earlier round is listed again while it still
   seems to say more: the record keeps no choice.
7. **The question** — one sentence for all blocks, after the last block.

```
── 主題「{question}」の答え ──
あなたの見立て（主題の答えに、あなたの言葉のまま書く）
  「{the view as written}」
  置く所: {これまでわかっていること | 注意すべきこと | まだ決められないこと}
  根拠: {the numbers of the results it rests on}{、いまの答えが根拠にしている分析結果 {N}件}
前の回までのあなたの見立て（そのまま残す。置き換えるときは言ってください）
  「{an earlier view as written}」{ — {what would change it}}

根拠に入れることを勧める分析結果（{N}件）
  1. {content}（{design_id}）
     — {reason}
  2. 人に聞いた答え: {content}（{design_id}）
     — {reason}
  3. {content}（{design_id}）（前の回にも見せた）
     — {reason}

勧めなかった、この回の分析結果（{N}件）
  4. {content}（{design_id}）— {why not}

前の回までに見せて、答えに入れなかった分析結果: {N}件（言ってもらえれば全部出す）

前は答えの根拠にしていて、今は外している分析結果
  5. {content}（{round}回目の振り返りの答えまで根拠にしていた）

根拠より強く言っているように見える、前の答えの文（{N}件）
  文1. 「{text}」 ← 根拠は{what its cited events say}
     残す・弱める・落とすから選べます（書かなければ残します）。
  文2. 「{text}」（あなたの見立て） ← 根拠は{what its cited events say}
     残す・弱める・落とすから選べます（書かなければ残します）。弱めるときは、文をあなたの言葉で書いてください。

── 論点「{question}」の答え ──
根拠に入れることを勧める分析結果: 2、4
根拠より強く言っているように見える、前の答えの文（{N}件）
  文3. 「{text}」 ← 根拠は{what its cited events say}
     残す・弱める・落とすから選べます（書かなければ残します）。

「勧めた{N}件を根拠に入れて、答えを書いてよいですか。
 外す番号、足す番号、見立ての言い直し、前の答えの文の扱いがあれば、あわせて書いてください。」
```

- Number the results through the whole question, each once: a result written out under the
  root is not written out again, and the block of another node names it by that number.
- A `hearing` event is listed as 人に聞いた答え, a `conclude` event as あなたの結論 and a
  `question` event as 問い, each before its content; any other event is 分析結果 and takes no
  word before it.
- `{N}` in the question is the number of results recommended in all blocks. When you
  recommend none, ask 「どの分析結果も根拠に入れずに、答えを書いてよいですか。」 instead of its
  first line.
- Say what the cited events say in a few words of their content (「冬の3か月の集計1つ」),
  never by their ids. When two or more statements are listed, mark them 文1, 文2, … through
  the whole question, so the analyst can name each; a single one takes no mark. Leave out
  、前の答えの文の扱い when no block has the part.

**After the reply.** The analyst decides. Wait for the answer, and send nothing before it:
once the answers are written, taking in another result needs another round.

- Taking the recommendation as it stands confirms it. The analyst may also take numbers
  out, add numbers from the results you did not recommend, and say the view again.
- When the analyst asks for them, list every one by its content, the results shown before
  included, under the numbers that follow, and wait again. It is the same question going
  on: add no second closing question of your own.
- Never cite a result from below that the analyst did not confirm, other than a
  `contradicts` event Step T2 cites in a `weakening`, in any statement of any node. When
  they confirm none, the answers are written without them.
- When the analyst says the view again, the statement takes the new words exactly.
- The statement of the view cites the confirmed results it rests on. For every other
  confirmed result, add or rewrite the statements of the draft that rest on it, under the
  rules of Step T2. Do not ask again for the nodes this changes.
- The view may also rest on an event the root's current answer already cites; the line
  根拠 of the view says how many. When the view would rest on no confirmed result and on
  no such event, it cannot be written: say so and ask which result it rests on.

For each statement of the part **Overstated**, the reply decides (ADR-0069):

- 残す: the statement is sent character for character, as Step T2 says.
- 落とす: the statement is left out of the draft. Its cites from below may then show in
  Step T5 under 前は答えの根拠にしていて、今は外している分析結果. When it is the last statement
  of the node, the answer cannot be written without it (`tree_io answer` takes one statement
  or more, and an answer is never withdrawn): say so in the same question and ask whether
  to keep or weaken it. Never say in Step T5 that it was dropped.
- 弱める: the statement takes the analyst's words, exactly, when they give them, with
  `"analyst_view": true`: the words are theirs, and a violation of them is asked as for a
  view (ADR-0068). When they do not, rewrite only that statement to say no more than its
  cited events, under the rules of Step T2, with the same `kind` and the same `cites`.
- A listed statement the reply says nothing of is kept: never weaken or drop it on your
  own.
- Never write a weakened sentence for a statement with `analyst_view` (ADR-0068). When the
  analyst chooses 弱める for a view without saying how it reads, ask for the words: it is
  the same question going on. The view then reads exactly as they say, with the mark.

A statement weakened or dropped here changes the answer. In Step T5, say so in `{reason}`
as 「前の答えの文を、あなたが選んだとおり弱めた」 or 「前の答えの文を、あなたが選んだとおり落とした」.

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
  each violation of a statement you wrote and send the whole call again.
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
analysis did not produce. When a statement you wrote still violates after one rewrite,
remove the statement from the draft and keep a note of its text and the violation for
Step T5. When every statement of a node is removed, send no answer for that node in this round.

A statement with `analyst_view` that violates is never rewritten and never removed by you
(ADR-0068). Show the analyst the violation and the sentence as they wrote it, and ask how
it should read: 「あなたの見立ての「{the number or the result}」が、根拠にした分析結果の
どれにも書かれていません。文をどう直しますか。根拠にする分析結果を足すこともできます。」
Send what the analyst says, exactly as they say it, with the mark. When they take the
sentence back, leave it out and list it under Removed statements in Step T5.

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
    [これまでわかっていること]（あなたの見立て）{text}  ← {cites}
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

── 前の回までに見せて、答えに入れなかった分析結果 ──
  - {node_id}: {N}件（言ってもらえれば全部出す）

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
  新しく根拠にした, `dropped` 根拠から外した, `reworded` 言っていることが変わった,
  `view_changed` 分析者の見立てにした・外した).
- Under the last three headings, take each entry of `uncited_below` under the node it is
  keyed by, and split them as Step T3 did. An entry whose `shown_before` is `true` is a
  count under 前の回までに見せて、答えに入れなかった分析結果, not a line of its own: it was
  shown in an earlier round, and the analyst can ask for all of them. The other entries are
  the results of this round the analyst did not confirm in Step T3: list each by the
  content of its event (a `hearing` event as 人に聞いた答え). Of these, an entry whose
  `last_cited_round` is `null` goes under まだ答えに入れていない分析結果; otherwise it goes
  under 前は答えの根拠にしていて、今は外している分析結果, with `last_cited_round` as `{round}`.
  Leave out a heading with nothing under it. The analyst sees them again here, before the
  decision. When a statement that rests on a result the analyst chose was removed in Step
  T3, say so next to it under Removed statements.
- A statement with `analyst_view` shows （あなたの見立て） after the word of its kind,
  whatever its kind, and its text as the analyst wrote it.
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
