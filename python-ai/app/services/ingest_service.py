from app.core.config import EMBEDDING_DIM
from app.core.logging_config import logger
from app.services.cache_service import bump_kb_version_sync
from app.services.document_service import (
    insert_chunks,
    update_doc_status,
    update_task_status,
)
from app.services.embedding_service import embed_texts
from app.services.file_service import read_chunks_with_meta


def run_ingest_job(
    task_id: str,
    doc_id: int,
    source_path: str,
    title: str,
    trace_id: str = "",
):
    logger.info(
        "run_ingest_job start trace_id=%s task_id=%s doc_id=%s source_path=%s title=%s",
        trace_id,
        task_id,
        doc_id,
        source_path,
        title,
    )

    try:
        update_task_status(task_id, "running", 10, "")
        update_doc_status(doc_id, "processing")

        chunks = read_chunks_with_meta(source_path, chunk_size=700, overlap=100)
        if not chunks:
            raise ValueError("document is empty after parsing")

        texts = [item["text"] for item in chunks]

        update_task_status(task_id, "running", 40, "")
        embeddings = embed_texts(texts)

        update_task_status(task_id, "running", 80, "")
        insert_chunks(doc_id, chunks, embeddings)

        update_task_status(task_id, "success", 100, "")
        update_doc_status(doc_id, "ready")

        logger.info(
            "run_ingest_job success trace_id=%s task_id=%s doc_id=%s chunk_count=%s embedding_dim=%s",
            trace_id,
            task_id,
            doc_id,
            len(chunks),
            EMBEDDING_DIM,
        )
        bump_kb_version_sync(trace_id=trace_id, doc_id=doc_id, task_id=task_id)
        return {
            "taskId": task_id,
            "docId": doc_id,
            "status": "success",
            "chunkCount": len(chunks),
            "embeddingDim": EMBEDDING_DIM,
        }

    except Exception as e:
        logger.exception(
            "run_ingest_job failed trace_id=%s task_id=%s doc_id=%s error=%s",
            trace_id,
            task_id,
            doc_id,
            str(e),
        )
        update_task_status(task_id, "failed", 100, str(e))
        update_doc_status(doc_id, "failed")
        raise
