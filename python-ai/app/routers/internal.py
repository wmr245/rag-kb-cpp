import json
import os
import time
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder

from app.core.config import QUERY_CACHE_TTL_SEC
from app.core.logging_config import logger
from app.models.schemas import (
    IngestRequest,
    InternalUploadRequest,
    InternalUploadResponse,
    QueryRequest,
    QueryResponse,
    TaskStatusResponse,
)
from app.services.cache_service import build_query_cache_key, get_kb_cache_version
from app.services.document_service import create_doc_and_task, load_task
from app.services.embedding_service import embed_query
from app.services.ingest_service import run_ingest_job
from app.services.llm_service import generate_answer
from app.services.retrieval_service import search_chunks
from app.utils.trace import get_trace_id

router = APIRouter()


@router.post("/internal/ingest")
def internal_ingest(req: IngestRequest, request: Request):
    trace_id = get_trace_id(request)

    try:
        return run_ingest_job(
            task_id=req.taskId,
            doc_id=req.docId,
            source_path=req.sourcePath,
            title=req.title,
            trace_id=trace_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/internal/query", response_model=QueryResponse)
async def internal_query(req: QueryRequest, request: Request, response: Response):
    trace_id = get_trace_id(request)
    total_started_at = time.perf_counter()

    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question must not be empty")

    top_k = max(1, min(req.topK, 10))
    doc_scope = sorted(set(req.docScope or []))

    logger.info(
        "internal_query start trace_id=%s question_len=%s top_k=%s doc_scope=%s",
        trace_id,
        len(question),
        top_k,
        doc_scope,
    )

    redis_cli = getattr(request.app.state, "redis", None)
    kb_version = await get_kb_cache_version(redis_cli)

    cache_key = build_query_cache_key(
        question=question,
        doc_scope=doc_scope,
        top_k=top_k,
        embed_model="text-embedding-v2",
        gen_model=os.getenv("CHAT_MODEL", "current-llm"),
        kb_version=kb_version,
    )

    if redis_cli is not None:
        try:
            cached = await redis_cli.get(cache_key)
            if cached:
                resp_body = json.loads(cached)
                resp_body["latencyMs"] = max(
                    1,
                    int((time.perf_counter() - total_started_at) * 1000),
                )

                response.headers["x-cache"] = "hit"
                response.headers["x-kb-version"] = str(kb_version)

                logger.info(
                    "internal_query cache_hit trace_id=%s kb_version=%s key_suffix=%s latency_ms=%s",
                    trace_id,
                    kb_version,
                    cache_key[-12:],
                    resp_body["latencyMs"],
                )

                return QueryResponse(**resp_body)
        except Exception as e:
            logger.warning(
                "internal_query cache_read_failed trace_id=%s error=%s",
                trace_id,
                str(e),
            )

    try:
        embed_started_at = time.perf_counter()
        question_embedding = embed_query(question)
        embed_ms = int((time.perf_counter() - embed_started_at) * 1000)

        retrieve_started_at = time.perf_counter()
        items = search_chunks(question_embedding, doc_scope, top_k)
        retrieve_ms = int((time.perf_counter() - retrieve_started_at) * 1000)

        generate_started_at = time.perf_counter()
        answer = generate_answer(question, items)
        generate_ms = int((time.perf_counter() - generate_started_at) * 1000)

        total_ms = int((time.perf_counter() - total_started_at) * 1000)

        response_obj = QueryResponse(
            question=question,
            answer=answer,
            items=items,
            latencyMs=total_ms,
        )

        response_data = jsonable_encoder(response_obj)

        logger.info(
            "internal_query success trace_id=%s result_count=%s embed_ms=%s retrieve_ms=%s generate_ms=%s total_ms=%s",
            trace_id,
            len(items),
            embed_ms,
            retrieve_ms,
            generate_ms,
            total_ms,
        )

        if redis_cli is not None:
            try:
                await redis_cli.setex(
                    cache_key,
                    QUERY_CACHE_TTL_SEC,
                    json.dumps(response_data, ensure_ascii=False),
                )
                logger.info(
                    "internal_query cache_set trace_id=%s kb_version=%s key_suffix=%s ttl_sec=%s",
                    trace_id,
                    kb_version,
                    cache_key[-12:],
                    QUERY_CACHE_TTL_SEC,
                )
            except Exception as e:
                logger.warning(
                    "internal_query cache_write_failed trace_id=%s error=%s",
                    trace_id,
                    str(e),
                )

        response.headers["x-cache"] = "miss"
        response.headers["x-kb-version"] = str(kb_version)
        return response_obj

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("internal_query failed trace_id=%s error=%s", trace_id, str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/internal/docs/upload", response_model=InternalUploadResponse)
def internal_docs_upload(
    req: InternalUploadRequest,
    request: Request,
    background_tasks: BackgroundTasks,
):
    trace_id = get_trace_id(request)

    source_path = Path(req.sourcePath)
    if not source_path.exists():
        raise HTTPException(status_code=400, detail=f"sourcePath not found: {req.sourcePath}")

    if source_path.suffix.lower() not in [".md", ".txt"]:
        raise HTTPException(status_code=400, detail="only .md and .txt are supported for now")

    doc_id, task_id = create_doc_and_task(
        title=req.title,
        source_path=req.sourcePath,
        owner=req.owner,
    )

    background_tasks.add_task(
        run_ingest_job,
        task_id,
        doc_id,
        req.sourcePath,
        req.title,
        trace_id,
    )

    logger.info(
        "internal_docs_upload queued trace_id=%s task_id=%s doc_id=%s source_path=%s title=%s owner=%s",
        trace_id,
        task_id,
        doc_id,
        req.sourcePath,
        req.title,
        req.owner,
    )

    return InternalUploadResponse(
        docId=doc_id,
        taskId=task_id,
        status="queued",
    )


@router.get("/internal/tasks/{task_id}", response_model=TaskStatusResponse)
def internal_task_status(task_id: str, request: Request):
    trace_id = get_trace_id(request)

    row = load_task(task_id)
    if not row:
        raise HTTPException(status_code=404, detail="task not found")

    logger.info(
        "internal_task_status trace_id=%s task_id=%s status=%s progress=%s",
        trace_id,
        row[0],
        row[2],
        row[3],
    )

    return TaskStatusResponse(
        taskId=str(row[0]),
        docId=int(row[1]),
        status=row[2],
        progress=int(row[3]),
        error=row[4],
    )
