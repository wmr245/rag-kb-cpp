# 2026-03-24 Cloud Rerank Rollout

## Goal

This round was about finishing the cloud rerank feature as a real project capability instead of a design note.

Targets:

- connect DashScope `qwen3-rerank` into the live retrieval chain
- keep local rerank as fallback instead of replacing the current pipeline
- make rerank visible in `queryDebug`, `decisionSummary`, cache signatures, and eval compare
- verify real gains with data instead of stopping at “the API call works”

## What Was Shipped

Files involved:

- `python-ai/app/core/config.py`
- `python-ai/app/services/rerank_service.py`
- `python-ai/app/services/retrieval_service.py`
- `python-ai/app/routers/internal.py`
- `python-ai/app/models/schemas.py`
- `python-ai/app/services/cache_service.py`
- `scripts/run_eval.py`
- `docker-compose.yml`
- `.env.example`
- `eval/suites/rerank.json`

Implemented shape:

- local retrieval and local rerank still run first
- only the top rerank candidates are sent to DashScope
- final order uses blended local score plus rerank score
- if cloud rerank fails, the system falls back to local ranking
- eval and compare can now distinguish rerank-driven changes from planner or retrieval changes

## Validation Summary

### 1. General regression suites

Observed results:

- `small`: `10/10`
- `query`: `8/8`
- `medium`: `17/17`

Meaning:

- cloud rerank is connected and stable
- no regression was introduced on the current general suites
- these suites were already strong enough that pass-rate gains were not visible there

### 2. Dedicated rerank suite

A dedicated suite was added to test top1 ranking under semantically close distractors.

Expanded suite results:

- no rerank: `5/8`
- with rerank: `7/8`
- header subset: `2/5 -> 4/5`

This matters because it shows actual measurable benefit, not just successful API connectivity.

## Problems Encountered And Solutions

### 1. `.env` was updated but the container did not receive rerank settings

Symptom:

- the service looked configured locally
- but live requests behaved as if rerank was still disabled

Root cause:

- `docker-compose.yml` did not pass the `RERANK_*` variables into `ai-service`

Solution:

- add the rerank env pass-through under `ai-service`
- recreate the container after config changes instead of only editing `.env`
- verify with container env inspection before trusting eval output

Takeaway:

- for Dockerized services, changing `.env` is not enough unless compose actually forwards the variables and the container is recreated

### 2. The generic design shape was not enough for DashScope

Symptom:

- a generic rerank design is easy to describe, but vendor details decide whether the real request succeeds

Root cause:

- DashScope uses its own rerank endpoint and response shape
- the implementation had to match the official request body and `output.results` response structure

Solution:

- align the client to `https://dashscope.aliyuncs.com/compatible-api/v1/reranks`
- send `model / query / documents / top_n`
- parse the official result list and keep a strict fallback path on mismatch

Takeaway:

- “OpenAI-compatible enough” does not mean every auxiliary endpoint is interchangeable; rerank should be treated as vendor-specific until proven otherwise

### 3. General eval suites could not prove the benefit

Symptom:

- rerank was clearly active in debug output
- but `query` and `medium` showed `0 improvement`

Root cause:

- the existing suites were already near-saturated for the current retrieval stack
- they were not targeted at rerank-style top1 ranking mistakes

Solution:

- add a dedicated `rerank` suite
- judge top1 directly with `topItemAny`
- create semantically close distractor cases instead of only answer-keyword cases

Takeaway:

- if a capability affects ranking quality, the eval must directly test ranking quality; otherwise the gain can stay invisible

### 4. One hard case still did not flip

Symptom:

- `rerank-header-freshness-field` still preferred `Cache Hit Header`
- the desired answer was `Data Version Field`

Interpretation:

- cloud rerank helped, but the retrieval queries still over-weighted lexical cues around `x-cache`
- this remaining miss is more about query-side bias than about the rerank client itself

Actionable conclusion:

- do not keep tuning rerank blindly
- the next round should improve query handling, retrieval queries, and hard-case observability

## Current Judgment

Cloud rerank is now “done enough” as a shipped feature:

- integrated into the live chain
- configurable by env
- safe under fallback
- measurable in eval
- already showing real gains on targeted cases

The next step is not more vendor plumbing. The next step is to reduce the remaining hard retrieval misses that rerank alone cannot fix.
