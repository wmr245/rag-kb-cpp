from typing import List, Optional

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
    text: str
    heading: Optional[str] = None
    sectionPath: Optional[str] = None
    chunkType: Optional[str] = None
    sourceType: Optional[str] = None
    citation: Citation


class QueryResponse(BaseModel):
    question: str
    answer: str
    refused: bool = False
    refusalReason: Optional[str] = None
    evidenceScore: Optional[float] = None
    items: List[RetrievedItem]
    citations: List[Citation] = Field(default_factory=list)
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
