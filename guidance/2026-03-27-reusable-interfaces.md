# Reusable Interface Boundaries

## Purpose

This document freezes the current repository's most reusable AI-service boundaries into a more formal interface view.

It is intended to guide follow-up work such as:

- extracting stable internal services
- splitting Java product services from Python AI services
- designing new game-oriented orchestration on top of the existing RAG stack
- avoiding accidental rewrites of already-stable capability

The goal is not to freeze every implementation detail. The goal is to freeze the service boundaries that are already stable enough to be treated as reusable contracts.

## Current Judgment

The following areas are considered stable enough to reuse as interfaces:

1. knowledge import
2. query planning
3. retrieval and evidence assembly
4. rerank provider integration
5. top-level RAG query execution

The following areas should not yet be treated as stable contracts:

1. heuristic internals inside query planning
2. exact score thresholds and blending weights
3. router-level orchestration details inside the current FastAPI handler
4. cache-key internals and invalidation details

## Interface Layering

Recommended long-term layering:

1. `KnowledgeImportService`
2. `QueryPlanner`
3. `RetrievalEngine`
4. `RerankProvider`
5. `RagQueryEngine`

These interfaces should sit above concrete implementation details and below any future product-specific orchestration such as game director logic, multi-step agent flows, or Java-based session services.

## 1. KnowledgeImportService

### Responsibility

Own the lifecycle from uploaded source to searchable knowledge assets.

This includes:

- accepting source metadata
- creating document and task records
- running ingestion
- contextualizing chunks
- generating embeddings
- updating searchable storage
- exposing task status

### Why It Is Stable

The current ingestion flow already has a clear lifecycle and explicit task boundaries.

Relevant implementation anchors:

- `python-ai/app/routers/internal.py`
- `python-ai/app/services/document_service.py`
- `python-ai/app/services/ingest_service.py`

### Suggested Interface

```ts
interface KnowledgeImportService {
  uploadSource(input: UploadSourceInput): Promise<UploadSourceResult>;
  startIngest(input: StartIngestInput): Promise<IngestTaskRef>;
  getTaskStatus(taskId: string): Promise<IngestTaskStatus>;
}
```

### Suggested Data Contracts

```ts
type UploadSourceInput = {
  sourcePath: string;
  title: string;
  owner?: string;
};

type UploadSourceResult = {
  docId: number;
  taskId: string;
  status: string;
};

type IngestTaskStatus = {
  taskId: string;
  docId: number;
  status: string;
  progress: number;
  error?: string;
};
```

### Reuse Guidance

This interface should be reused for future `worldbook`, character-card, event-pack, and story-pack imports.

The input type may later branch by content kind, but the lifecycle should stay the same.

## 2. QueryPlanner

### Responsibility

Convert one user question into a structured query plan that downstream retrieval can execute.

This includes:

- normalization
- intent classification
- focus extraction
- decomposition
- route-query fanout
- retrieval-query fanout

### Why It Is Stable

The repository now has a functioning query-planning stage with stable output shape and proven value across hard-case cleanup.

Relevant implementation anchor:

- `python-ai/app/services/query_service.py`

### Suggested Interface

```ts
interface QueryPlanner {
  plan(question: string): Promise<QueryPlan>;
}
```

### Suggested Data Contract

```ts
type QueryPlan = {
  plannerVersion: string;
  normalizedQuestion?: string;
  focusQuestion?: string;
  decomposition: string[];
  intent: Record<string, boolean>;
  routeQueries: string[];
  retrievalQueries: string[];
};
```

### Reuse Guidance

Freeze the `QueryPlan` output shape, not the internal heuristics.

Future work may improve intent rules, domain hints, decomposition quality, and focus selection, but the planner should continue to emit the same conceptual contract.

## 3. RetrievalEngine

### Responsibility

Turn a `QueryPlan` and optional scope into evidence candidates that can support answer generation.

This includes:

- routing candidate documents
- searching chunks
- applying rerank if enabled
- assessing answerability
- building citations

### Why It Is Stable

The repo now has a coherent retrieval pipeline with observable route runs, retrieval runs, rerank debug, answerability, and citation assembly.

Relevant implementation anchors:

- `python-ai/app/services/retrieval_service.py`
- `python-ai/app/routers/internal.py`

### Suggested Interface

```ts
interface RetrievalEngine {
  route(input: RouteInput): Promise<RouteResult>;
  retrieve(input: RetrieveInput): Promise<RetrieveResult>;
  assess(input: AssessInput): Promise<AnswerabilityResult>;
  buildCitations(items: RetrievedItem[]): Promise<Citation[]>;
}
```

### Suggested Data Contracts

```ts
type RouteInput = {
  question: string;
  routeQueries: string[];
  docScope?: number[];
  queryIntent?: Record<string, boolean>;
};

type RouteResult = {
  routedDocs: RoutedDoc[];
  routeRuns: RouteRunDebug[];
};

type RetrieveInput = {
  question: string;
  retrievalQueries: string[];
  routedDocs: RoutedDoc[];
  topK: number;
  queryIntent?: Record<string, boolean>;
};

type RetrieveResult = {
  items: RetrievedItem[];
  retrievalRuns: RetrievalRunDebug[];
  rerank?: RerankDebugInfo;
};

type AnswerabilityResult = {
  refused: boolean;
  refusalReason?: string;
  evidenceScore?: number;
};
```

### Reuse Guidance

Treat retrieval as an evidence service, not as a product-specific answering flow.

Future game or agent orchestration should call this layer to fetch grounded evidence, not re-implement routing or retrieval heuristics ad hoc.

## 4. RerankProvider

### Responsibility

Provide an isolated contract for cloud or local rerank capability.

This includes:

- provider-specific API calls
- score normalization
- fallback handling
- signature exposure for cache invalidation

### Why It Is Stable

The rerank path is now already isolated enough to switch providers without changing top-level retrieval orchestration.

Relevant implementation anchor:

- `python-ai/app/services/rerank_service.py`

### Suggested Interface

```ts
interface RerankProvider {
  rerank(query: string, documents: string[], topN: number): Promise<RerankResult>;
  cacheSignature(): string;
}
```

### Suggested Data Contract

```ts
type RerankResult = {
  scoresByIndex: Record<number, number>;
  latencyMs: number;
};
```

### Reuse Guidance

Freeze the provider-facing contract, not the provider implementation.

This allows future migration among DashScope, other cloud APIs, or local rerank backends without changing retrieval callers.

## 5. RagQueryEngine

### Responsibility

Expose the top-level grounded query capability as one stable service boundary.

This is the main reusable interface that higher-level product services should call.

### Why It Is Stable

The current `/internal/query` path already composes planning, routing, retrieval, rerank, answerability, citations, and debug output into one coherent response.

Relevant implementation anchors:

- `python-ai/app/routers/internal.py`
- `python-ai/app/models/schemas.py`

### Suggested Interface

```ts
interface RagQueryEngine {
  query(input: RagQueryInput): Promise<RagQueryResult>;
}
```

### Suggested Data Contracts

```ts
type RagQueryInput = {
  question: string;
  docScope?: number[];
  topK?: number;
};

type RagQueryResult = {
  question: string;
  answer: string;
  refused: boolean;
  refusalReason?: string;
  evidenceScore?: number;
  items: RetrievedItem[];
  citations: Citation[];
  resolvedDocScope: number[];
  routedDocs: RoutedDoc[];
  queryDebug?: QueryDebugInfo;
  latencyMs: number;
};
```

### Reuse Guidance

This is the preferred entry point for future Java product services or agentic orchestration.

If a future system only needs grounded retrieval-plus-answering, it should call `RagQueryEngine` directly rather than reaching into planner or retrieval internals.

If a future system needs multi-step control, it may call lower layers explicitly, but only with a strong reason.

## What Should Stay Internal For Now

The following should remain implementation details:

- internal score thresholds
- blending weights between local score and rerank score
- exact query-rewrite heuristics
- exact cache-key composition
- router-specific merge logic for candidate lists
- debug-summary wording

These are still evolving and should not be treated as external contracts.

## Suggested Ownership Split For Future Work

If the repo later splits responsibilities across languages or services, the recommended ownership is:

- Java:
  product backend, sessions, users, room state, persistence, admin APIs, WebSocket delivery
- Python:
  planner, retrieval, rerank, LLM orchestration, memory retrieval, grounded generation
- C++:
  existing stable assets, performance-sensitive components, local packaging, or gateway/runtime layers when justified

The key point is:

Product orchestration should sit above these reusable interfaces, not inside them.

## Recommended Next-Step Work

If follow-up work starts from this document, the best order is:

1. wrap the current `/internal/query` path behind an explicit `RagQueryEngine` service facade
2. wrap ingestion behind `KnowledgeImportService`
3. define stable request and response DTOs in one place
4. make future product logic call these interfaces instead of importing service internals directly
5. only after that, add game-specific orchestration such as `WorldbookService`, `CharacterCardService`, or `DirectorAgentService`

## Bottom Line

The repo already contains reusable capability.

The correct next step is not to rewrite the AI core, but to freeze and wrap the stable boundaries that already exist:

- import
- planning
- retrieval
- rerank
- top-level grounded query

Everything product-specific should build on top of those.
