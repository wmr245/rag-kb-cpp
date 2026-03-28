# 2026-03-22 Routing And Rerank Improvements

## Goal

This round focused on making document routing feel more like a real product capability instead of a debug-only helper.

Main goals:

- add soft deduplication for uploads to avoid repeated ingest and embedding work
- strengthen document-level rerank for automatic routing
- add score thresholds, relative score floors, and lightweight domain constraints
- reduce tail noise when users query without `docScope`

## Why This Work Was Needed

### 1. Repeated uploads kept increasing cost and noise

Observed issue:

- smoke tests and eval runs upload the same documents many times
- without deduplication, the database accumulates semantically identical documents
- this increases embedding cost, indexing cost, and routing noise

Purpose:

- reduce repeated ingest cost
- keep automatic routing cleaner when `docScope` is empty
- make eval results more stable across repeated runs

### 2. Document routing was already useful, but tail candidates were still noisy

Observed issue:

- document routing could already place the correct document near the top
- however, weakly related historical documents still appeared in the tail of top candidates
- this was especially visible with old smoke-test documents

Purpose:

- make default queries narrow down to the most plausible document first
- upgrade routing from simple ranking to ranking plus filtering
- prepare a cleaner base for future query rewrite and agent work

## What Was Changed

### 1. Soft upload deduplication

Files:

- `python-ai/app/services/document_service.py`
- `python-ai/app/db/postgres.py`
- `db/init/001_init.sql`
- `python-ai/app/routers/internal.py`

Method:

- added `content_hash` to `docs`
- added an `(owner, content_hash)` index
- compute SHA-256 during upload
- if the same owner already has a `ready` document with the same hash, reuse it
- return a new task id with immediate `success` and upload status `duplicate`
- only truly new content enters async ingest

Why this approach:

- this is a safe soft-dedup design instead of a hard rejection
- different owners can still keep the same content independently
- it is more product-friendly and better for repeated testing workflows

### 2. Stronger document-level rerank

File:

- `python-ai/app/services/retrieval_service.py`

Method:

- kept the existing vector plus keyword document recall
- improved document rerank scoring with:
  - vector score
  - keyword score
  - title overlap
  - summary overlap
  - keyword coverage
  - route-text coverage
  - query phrase hits
  - query-intent bias
- kept document-level semantic deduplication so repeated uploads do not occupy multiple routed slots

Why this approach:

- document routing should answer which document is worth searching inside, not just which one looks vaguely similar
- title, summary, keywords, and intent alignment matter more than raw embedding similarity alone

### 3. Threshold filtering and domain constraints

Files:

- `python-ai/app/services/retrieval_service.py`
- `python-ai/app/models/schemas.py`

Method:

- added intent-aware minimum score thresholds
- added a relative floor based on the leading routed document
- filtered weak single-source candidates that were too far below the leader
- added lightweight domain alignment for categories like `ops`, `product`, and `definition`
- added `reason` to `routedDocs`, such as `vector+domain+procedural`

Why this approach:

- earlier routing mainly solved whether the correct document could reach the top
- this round solved why weakly related documents were still surviving in the tail
- thresholds plus domain constraints make automatic routing much more product-like

## Validation Results

### 1. Upload deduplication

Observed runtime result:

- first upload: `docId=86`, `status=queued`
- second upload with the same content: `docId=86`, `status=duplicate`

Result:

- repeated uploads no longer trigger repeated ingest
- the feature works in the live flow, not just in theory

### 2. Regression status

Latest `small` suite result:

- report: `eval/reports/small-20260322-152815.json`
- `passed=8/8`
- `routing=2/2`

Result:

- upload deduplication and routing tightening did not break retrieval, answers, or citations

### 3. Routing noise reduction

Observed routing cases:

- `small-route-auto-summary`
  - `resolvedDocScope=[84]`
  - only `Orion Product Overview` was kept
  - `reason=vector+domain+definition`
- `small-route-auto-procedure`
  - `resolvedDocScope=[85]`
  - only `Orion Ops Runbook` was kept
  - `reason=vector+domain+procedural`

Result:

- automatic routing now usually narrows to a single best document instead of carrying a long tail
- default no-scope querying is much cleaner than before

## Improvement Impact

### Retrieval experience

- users do not need to understand `docId` for ordinary queries
- the system is now better at selecting the most plausible document before chunk search
- this is much closer to a product-style knowledge assistant experience

### Resource efficiency

- repeated uploads no longer repeat embedding work
- repeated eval runs pollute the knowledge base less
- future larger eval suites will not amplify duplicate content endlessly

### Engineering explainability

- `routedDocs.reason` now explains why a document survived routing
- this helps future tuning, debugging, query rewrite, and agent orchestration

## Remaining Gaps

- routing reasons are useful, but query intent is still coarse
- questions like "what is ..." can still over-trigger definition-style logic
- the current domain constraint is still a lightweight heuristic, not a dedicated reranker model

## Recommendation For The Next Step

Based on `guidance/2026-03-21-next-prompt.md` and `guidance/2026-03-22-rag-capability-benchmark.md`, the next best step is query handling, not more rerank work.

Recommended order:

1. improve query intent classification
2. add query rewrite and query decomposition for ambiguous or structured questions
3. add eval cases that compare original query versus rewritten query
4. only consider a stronger dedicated reranker if complex questions are still limited by ranking quality after query improvements

Conclusion:

- next, prioritize query processing
- stronger rerank can come later if query-side improvements stop producing meaningful gains
