# 2026-03-24 Query Hard-Case Closure

## Goal

This round was not about adding a brand-new capability. It was about closing the remaining hard cases after cloud rerank was already integrated.

Targets:

- remove the remaining query-to-retrieval drift in rerank-specific hard cases
- make the retrieval path easier to diagnose when a case still fails
- decide whether this part of the project is now stable enough to stop tuning

## What Changed

Files involved:

- `python-ai/app/services/query_service.py`
- `python-ai/app/services/retrieval_service.py`
- `python-ai/app/routers/internal.py`
- `python-ai/app/models/schemas.py`
- `scripts/run_eval.py`
- `eval/suites/rerank.json`

Main changes:

- fix English substring intent false-positives, especially cases where `how` was accidentally matched inside unrelated words such as `showing`
- add stronger API intent recognition for English `field` / `fields`
- add a focused query hint for freshness/version field questions so retrieval does not keep drifting toward `x-cache`
- preserve planner intent when calling route/retrieval functions instead of letting later stages infer their own weaker intent
- expose per-query route and retrieval debug snapshots so failures can be attributed more directly
- extend the rerank suite so it checks both top1 correctness and intent guardrails

## Problems Encountered And Solutions

### 1. Query intent was being polluted by substring matches

Symptom:

- some English questions were classified as `procedural` even though they were clearly API or field-selection questions
- this pushed retrieval queries toward `ops/runbook` style hints

Root cause:

- the intent detector was using raw substring matching
- `how` could be matched inside unrelated words such as `showing`

Solution:

- replace the loose matching with word-boundary-aware matching for ASCII terms
- keep CJK matching behavior simple and direct

Takeaway:

- intent matching for English should respect token boundaries; otherwise one small lexical accident can distort the entire retrieval plan

### 2. Cloud rerank exposed that the real problem was query-side drift, not just final ordering

Symptom:

- the rerank client was healthy
- but one remaining hard case still preferred `Cache Hit Header` over `Data Version Field`

Root cause:

- one retrieval query still over-weighted cache-oriented lexical cues
- rerank improved some branches, but a weaker retrieval branch could still dominate the merged result

Solution:

- add a more explicit focus for freshness/version field questions
- keep the focus narrow enough that it does not incorrectly override trace-header questions
- validate the rule by iterating on the same hard-case suite instead of guessing

Takeaway:

- if rerank is already working but one hard case remains, the next thing to inspect is usually the query plan or retrieval query design, not the vendor API client

### 3. Existing debug fields were still not enough for fast hard-case diagnosis

Symptom:

- the response already exposed `queryDebug.rerank` and `decisionSummary`
- but it was still slow to see which retrieval query produced which local top item and which final top item

Solution:

- add `queryDebug.routeRuns`
- add `queryDebug.retrievalRuns`
- add `queryDebug.attributionHints`
- include `localTopItems`, `finalTopItems`, and `orderingChanged` in rerank debug

Takeaway:

- for hard-case tuning, “the chain worked” is not enough; each query branch needs its own compact retrieval snapshot

## Validation Result

Final result for the dedicated rerank hard-case suite:

- report: `eval/reports/rerank-hardcase-20260324-v3.json`
- total: `8/8`
- `header` subset: `5/5`
- `trace` subset: `2/2`
- `freshness` subset: `3/3`

Meaning:

- the remaining hard cases from the previous round were closed
- the new observability fields were sufficient to guide the last tuning pass
- this part of the repository can now reasonably be treated as “good enough for closure” instead of an open rerank tuning thread

## Current Judgment

At this point:

- cloud rerank is integrated and stable
- query-to-retrieval hard cases for the dedicated rerank suite are closed
- observability is materially better than before
- further tuning is optional, not required for this milestone

If the project continues later, the next work should be a new scope, not more polishing on the same rerank hard cases.
