# 2026-03-22 Query Planning Improvements

## Goal

This round focused on turning query handling from a loose set of heuristics into a more structured query-planning layer.

Main goals:
- fix paraphrase failures in the `small` suite
- reduce intent conflicts between `summary`, `definition`, and `procedural`
- move from single rewrite to focus extraction plus multi-query fusion
- make the next-step judgment more grounded before entering Agent work

## Why This Work Was Needed

### 1. Query failures were no longer mainly retrieval-base failures

Observed issue:
- document routing was already in place
- routing deduplication and score thresholds were already working
- but the new paraphrase cases still failed

This meant the main bottleneck had shifted from routing to query understanding.

### 2. Some failures were caused by engineering issues, not model weakness

Observed issue:
- two newly added paraphrase cases in `eval/suites/small.json` had corrupted text and appeared as `????`
- query planner changes also exposed unrelated interface contract bugs in `internal.py`
- one task polling path still assumed `load_task()` returned an object instead of a tuple

Purpose:
- separate real retrieval-quality issues from broken test assets and runtime bugs
- restore a trustworthy eval signal before tuning query logic further

### 3. Intent conflict was dragging retrieval in the wrong direction

Observed issue:
- questions like `Orion 的核心能力是什么？` were being interpreted as both `summary` and `definition`
- because of `是什么`, retrieval was sometimes pulled toward `术语定义`
- procedural questions like `启动服务第二步要敲什么命令？` could also be over-classified as definition-like questions

Purpose:
- stop shallow keyword matches from overpowering the real query purpose
- make the planner prefer task intent over surface wording

## What Was Changed

### 1. Repaired broken runtime and eval assets

Files:
- `python-ai/app/routers/internal.py`
- `eval/suites/small.json`

Method:
- removed an accidental extra `trace_id` argument from upload flow
- fixed task polling response handling so tuple results are unpacked correctly
- cast `taskId` to string before building `TaskStatusResponse`
- repaired the corrupted paraphrase cases in `small.json`

Why this approach:
- eval cannot guide optimization if the suite itself is corrupted
- query tuning should only start after the runtime path is trustworthy

### 2. Rebuilt query handling into a planner

File:
- `python-ai/app/services/query_service.py`

Method:
- kept `originalQuestion` and `normalizedQuestion`
- added structured planner outputs:
  - `focusQuestion`
  - `routeQueries`
  - `retrievalQueries`
  - `intent`
  - `decomposition`
- generated multiple query variants instead of betting on a single rewrite
- used the focus query alongside the original query for retrieval fusion

Why this approach:
- production systems usually do not rely on one rewritten query
- keeping multiple candidate queries lowers the risk of rewriting the user intent incorrectly

### 3. Tightened intent resolution

File:
- `python-ai/app/services/query_service.py`

Method:
- added summary-focus terms like `核心能力`, `主要功能`, `功能`, `能力`
- when a query clearly looks like summary or procedural intent, suppress definition-style bias
- added focused handling for:
  - `Orion 主要能干嘛？` -> `Orion 核心能力`
  - `启动服务第二步要敲什么命令？` -> `服务启动步骤 第2步 命令`
  - temporal / threshold / metadata-definition style questions

Why this approach:
- this is more robust than endlessly appending synonyms
- the key improvement is intent disambiguation plus focus extraction, not just larger term lists

### 4. Used multi-query fusion in the query flow

File:
- `python-ai/app/routers/internal.py`

Method:
- route and retrieval now embed multiple planner-generated queries
- route candidates are merged across query variants
- retrieved chunks are also merged across query variants
- answer generation still uses the original user question for final response and citation alignment

Why this approach:
- query understanding should influence retrieval breadth
- answer generation should still stay grounded in the original user wording

## Validation Results

### 1. Before the final fix

Observed result:
- `small` temporarily dropped to `6/10`
- failures exposed three concrete issues:
  - corrupted eval cases
  - runtime task-status contract bugs
  - summary / definition intent conflicts

This was useful because it clarified that the problem was specific and fixable, not a broad regression of the whole RAG system.

### 2. After the targeted fixes

Latest result:
- report: `eval/reports/small-20260322-162140.json`
- `passed=10/10`
- `query=2/2`
- `routing=3/3`
- `summary=3/3`

Result:
- both new paraphrase cases now pass
- the original query cases still remain green
- query handling improved without breaking citations or refusal logic

## Improvement Impact

### Retrieval quality

- summary-style questions are less likely to be dragged into definition sections
- procedural paraphrases are more likely to land on the correct runbook section
- query failures now look more like true coverage gaps instead of planner confusion

### Engineering quality

- eval signal is trustworthy again
- planner outputs are structured and easier to reason about
- the system is closer to a maintainable query-understanding layer rather than scattered heuristics

### Product readiness

- user-style wording works better without needing explicit `docScope`
- this makes the default experience feel more like a real assistant and less like a debug interface

## Remaining Problems

- query coverage is still small; `small` is green, but broader paraphrase and multi-intent coverage is still thin
- planner decisions are only visible through logs, not yet through richer eval diagnostics
- the current planner is heuristic and deterministic, not a learned reranker or contextual retriever
- repeated eval uploads still grow the database over time even though content dedup already reduces some waste

## Recommendation For The Next Step

The next best step is not to jump straight to a stronger reranker.

Recommended order:
1. expand query eval coverage
2. add more systematic query rewrite / decomposition cases
3. improve observability for planner, routing, and retrieval decisions
4. only after that, decide whether a dedicated reranker or contextual retrieval is worth the extra complexity

Conclusion:
- query handling is now on the right track
- the next bottleneck is coverage and observability, not raw routing capability
- a controlled single Agent becomes reasonable only after this layer is a bit more mature
