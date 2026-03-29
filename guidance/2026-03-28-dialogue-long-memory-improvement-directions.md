# 2026-03-28 Dialogue + Long Memory Improvement Directions

## Current Baseline

- The dialogue flow now prefers keeping the model's original reply, and only falls back when the generated reply is effectively empty or structurally broken.
- Character turns are split into `speech` and `narration`, with narration sanitized more lightly instead of replacing the whole turn.
- Long-term memory is currently stored in two places:
  - `game_memories`: episodic cross-session memory rows promoted from archived sessions
  - `game_memory_profiles`: per-character long-term profile rows for the current player scope (`default_player`)
- Long-memory retrieval already works, but every turn still pays for:
  - one embedding request for the incoming player message
  - one or more chat completions for dialogue generation
  - one or more chat completions for narration generation

## What The Latest Real Chain Test Showed

- A 10-turn real API chain now completes without falling back to the obvious generic line (`我在听……我们慢慢聊`) on normal turns.
- Archive promotion still works and writes deduped long-term memories into PostgreSQL.
- A fresh session can load long-memory profiles and recent long-memory items.
- Cross-session recall works, but recall can still select an older semantically similar memory row instead of the latest one.
- Dialogue quality is improved, but there are still cases where the model responds too briefly on emotionally important turns.

## Direction 1: Layered Memory Retrieval

### Core idea

Add a lightweight memory index layer in front of the current long-memory detail retrieval.

Instead of doing full episodic retrieval against all promoted memories for every turn, split long memory into:

1. `memory index`
   - small, cheap, coarse-grained
   - used to decide which memory clusters are worth opening
2. `memory details`
   - existing episodic memory rows
   - used only after index hit selection

### Why this helps

- Reduces retrieval cost per turn
- Makes recall more stable across similar repeated memories
- Gives the system a place to cluster or summarize related memories instead of repeatedly searching every raw episodic row
- Creates a more controllable bridge between long-term memory and prompt context

### Proposed shape

Add a new lightweight table, conceptually something like `game_memory_index`, with rows such as:

- `worldbook_id`
- `character_id`
- `player_scope`
- `topic_key`
- `topic_label`
- `memory_type`
- `location_id`
- `summary`
- `last_seen_at`
- `memory_count`
- `representative_memory_ids`
- optional lightweight embedding

Example clusters:

- `雨天借伞`
- `陪伴/守约`
- `天台误会`
- `图书馆共同整理书`

### Retrieval flow after layering

Per turn:

1. Look up profile + memory index first
2. Select 1 to 3 relevant clusters
3. Only then fetch detailed episodic memories inside those clusters
4. Inject:
   - one compact profile summary
   - one compact topic-level index summary
   - at most one or two detailed episodic memories

### Practical benefit

This should improve both:

- performance: less full-detail retrieval work per turn
- prompt quality: less duplication and less flooding of similar raw memories

## Direction 2: Make Memory More Hierarchical

Current long memory is basically:

- session working memory
- episodic long memory
- profile summary

The next stronger version should become:

1. `working memory`
   - current session, immediate recent turns, current scene state
2. `topic memory`
   - stable recurring threads like promises, misunderstandings, shared routines
3. `episodic memory`
   - specific scenes and concrete interactions
4. `relationship memory`
   - profile-level long-term impression

This hierarchy is better than only storing isolated memory rows, because roleplay recall usually wants:

- "what is the ongoing thread?"
- then "what concrete moment supports it?"

instead of only "search all old rows and take top-k."

## Direction 3: Prompt Iteration Should Shift From Rules To Inputs

The recent iterations showed an important lesson:

- over-strong local rules easily produce rigid or generic fallback behavior
- too many post-generation quality gates can erase good short replies

So the next prompt work should bias toward improving the model inputs rather than adding more hard local replacement logic.

### Better prompt directions

1. Make the prompt read more like a live conversation state, less like a policy sheet
   - fewer global writing commandments
   - stronger immediate context
   - clearer "what is happening right now"

2. Separate constraints by importance
   - hard constraints:
     - do not leak locked secrets
     - no meta planning
     - speech and narration stay separate
   - soft constraints:
     - keep it natural
     - keep it grounded
     - continue the exchange

3. Let dialogue style come more from conversation state than from character signature props
   - prioritize:
     - player message
     - current emotional pressure
     - current scene action
   - downweight:
     - habitual object imagery
     - fixed gesture identity

4. Use better context slots
   - `what the player just did`
   - `what the character is reacting to`
   - `what thread is currently open`
   - `what should not be said yet`

5. Teach continuation more naturally
   - ask for one forward-moving conversational beat
   - but do not demand fixed sentence counts
   - do not force a question every turn

### Prompt directions worth testing

- A/B test a shorter prompt against the current dense one
- Move from "many prohibitions" toward "one grounded style paragraph + structured context blocks"
- Let narration be optional and low-frequency in calm turns
- For low-pressure turns, allow very short direct replies without retry pressure

## Direction 4: Narration Should Be Derived From Interaction, Not Persona Props

The narration problem was not only wording quality. It was also source-of-truth quality.

Better narration generation should rely more on:

- the player's latest move
- the character's spoken line
- the immediate physical situation
- current tension / closeness shift

and rely less on:

- "this character likes books"
- "this character often stands in the library"
- fixed signature objects

### Suggested narration generation strategy

Instead of asking for rich narration every turn, ask for:

- zero narration when the turn is simple
- one short observable beat when needed

Good narration inputs:

- player utterance
- chosen dialogue line
- current scene location
- recent narration examples only for anti-echo

Bad narration inputs to overweight:

- many static persona descriptors
- many signature props
- accumulated decorative style notes

## Direction 5: Long-Memory Content Should Be Better Than Current Event Templates

Current promoted memory summaries still start from rule-made session memory lines like:

- `在library场景中，林汐围绕“雨天借伞”回应了玩家。`
- `玩家在library向林汐表达了陪伴或承诺。`

These are acceptable for retrieval, but not ideal as the foundation for long-term semantic memory.

### Better next step

Keep dual fields, but improve what goes into them:

- `retrievalSummary`
  - compact and searchable
  - consistent structure
- `displaySummary`
  - human-readable
  - emotional and relational
- future `indexSummary`
  - topic-level abstraction used by the proposed memory index layer

### Better promotion candidates

Instead of only promoting event templates, promotion can later use:

- relationship delta significance
- explicit promises / commitments
- apologies / reconciliations
- recurring scene threads
- secret disclosures

## Direction 6: Recall Ranking Should Prefer Fresh + Relevant Memories

The latest real-chain test showed recall still picked older similar rows in some cases.

The next retrieval pass should rank by more than semantic match:

- semantic relevance
- responder match
- location match
- recency
- topical cluster freshness
- already-used memory penalty

That means retrieval should shift from:

- "top-k similar memories"

to:

- "top relevant topic clusters, then freshest supporting memory inside each cluster"

## Direction 7: Performance Work Can Follow Memory Layering

Current turn latency is dominated by remote requests, but retrieval architecture still matters.

Layered memory can reduce work by:

- skipping full-detail episodic retrieval when no index topic is relevant
- reducing how much memory text gets injected into prompts
- reducing duplicate or near-duplicate recall

Other future performance steps:

- skip embedding retrieval for trivial greetings / extremely short turns
- avoid separate narration generation on low-pressure turns
- add cheaper "fast path" turn handling for simple conversational beats

## Recommended Implementation Order

1. Add memory-index design doc + schema draft
2. Refactor long-memory promotion so episodic rows can map into topic clusters
3. Change retrieval from `full episodic first` to `index first -> episodic second`
4. Simplify prompt structure around clearer live-context blocks
5. Make narration optional on low-pressure turns
6. Re-rank recall with freshness + cluster preference

## Open Questions

- Should topic clusters be fully rule-based first, or partially model-generated during archive?
- Should one player have a single global profile per character, or later allow profile branches by route / timeline?
- Should narration disappear entirely on some turns, or remain a visible style layer most of the time?
- Should long-memory promotion happen only on archive, or also on selected important live turns?
