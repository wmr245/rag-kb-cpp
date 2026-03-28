from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    taskId: str
    docId: int
    sourcePath: str
    title: str


class QueryRequest(BaseModel):
    question: str
    docScope: List[int] = Field(default_factory=list)
    topK: int = 3


class Citation(BaseModel):
    title: str
    page: Optional[int] = None
    snippet: Optional[str] = None


class RetrievedItem(BaseModel):
    docId: int
    chunkId: int
    chunkIndex: int
    score: float
    localScore: Optional[float] = None
    rerankScore: Optional[float] = None
    blendedScore: Optional[float] = None
    text: str
    heading: Optional[str] = None
    sectionPath: Optional[str] = None
    chunkType: Optional[str] = None
    sourceType: Optional[str] = None
    citation: Citation


class RoutedDoc(BaseModel):
    docId: int
    title: str
    score: float
    summary: Optional[str] = None
    keywords: Optional[str] = None
    sourceType: Optional[str] = None
    reason: Optional[str] = None


class DecisionSummarySection(BaseModel):
    summary: str
    highlights: List[str] = Field(default_factory=list)


class DecisionSummary(BaseModel):
    headline: str
    planner: DecisionSummarySection
    routing: DecisionSummarySection
    retrieval: DecisionSummarySection
    answerability: DecisionSummarySection
    citation: DecisionSummarySection


class RerankDebugInfo(BaseModel):
    enabled: bool = False
    provider: Optional[str] = None
    model: Optional[str] = None
    callCount: int = 0
    requestedTopN: int = 0
    candidateCount: int = 0
    appliedCount: int = 0
    fallback: bool = False
    fallbackReason: Optional[str] = None
    latencyMs: int = 0
    resolvedIntent: Dict[str, bool] = Field(default_factory=dict)
    localTopItems: List[Dict[str, object]] = Field(default_factory=list)
    finalTopItems: List[Dict[str, object]] = Field(default_factory=list)
    orderingChanged: bool = False


class QueryDebugInfo(BaseModel):
    plannerVersion: Optional[str] = None
    normalizedQuestion: Optional[str] = None
    focusQuestion: Optional[str] = None
    decomposition: List[str] = Field(default_factory=list)
    intent: Dict[str, bool] = Field(default_factory=dict)
    routeQueries: List[str] = Field(default_factory=list)
    retrievalQueries: List[str] = Field(default_factory=list)
    routeRuns: List[Dict[str, object]] = Field(default_factory=list)
    retrievalRuns: List[Dict[str, object]] = Field(default_factory=list)
    attributionHints: List[str] = Field(default_factory=list)
    queryVectorCount: int = 0
    timingsMs: Dict[str, int] = Field(default_factory=dict)
    rerank: Optional[RerankDebugInfo] = None
    decisionSummary: Optional[DecisionSummary] = None


class QueryResponse(BaseModel):
    question: str
    answer: str
    refused: bool = False
    refusalReason: Optional[str] = None
    evidenceScore: Optional[float] = None
    items: List[RetrievedItem]
    citations: List[Citation] = Field(default_factory=list)
    resolvedDocScope: List[int] = Field(default_factory=list)
    routedDocs: List[RoutedDoc] = Field(default_factory=list)
    queryDebug: Optional[QueryDebugInfo] = None
    latencyMs: int


class InternalUploadRequest(BaseModel):
    sourcePath: str
    title: str
    owner: str = "demo"


class InternalUploadResponse(BaseModel):
    docId: int
    taskId: str
    status: str


class TaskStatusResponse(BaseModel):
    taskId: str
    docId: int
    status: str
    progress: int
    error: str
