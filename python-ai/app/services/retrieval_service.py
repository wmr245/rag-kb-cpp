from typing import List

from app.core.logging_config import logger
from app.db.postgres import get_conn
from app.models.schemas import Citation, RetrievedItem
from app.services.embedding_service import vector_to_pg


def search_chunks(
    question_embedding: List[float],
    doc_scope: List[int],
    top_k: int,
) -> List[RetrievedItem]:
    vector_literal = vector_to_pg(question_embedding)

    logger.info(
        "search_chunks start top_k=%s doc_scope_count=%s",
        top_k,
        len(doc_scope),
    )

    sql_with_scope = """
        SELECT
            c.id,
            c.doc_id,
            c.chunk_index,
            c.text,
            c.page,
            d.title,
            1 - (c.embedding <=> %s::vector) AS score
        FROM chunks c
        JOIN docs d ON d.id = c.doc_id
        WHERE c.embedding IS NOT NULL
          AND d.status = 'ready'
          AND c.doc_id = ANY(%s::bigint[])
        ORDER BY c.embedding <=> %s::vector
        LIMIT %s
    """

    sql_all_docs = """
        SELECT
            c.id,
            c.doc_id,
            c.chunk_index,
            c.text,
            c.page,
            d.title,
            1 - (c.embedding <=> %s::vector) AS score
        FROM chunks c
        JOIN docs d ON d.id = c.doc_id
        WHERE c.embedding IS NOT NULL
          AND d.status = 'ready'
        ORDER BY c.embedding <=> %s::vector
        LIMIT %s
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            if doc_scope:
                cur.execute(
                    sql_with_scope,
                    (vector_literal, doc_scope, vector_literal, top_k),
                )
            else:
                cur.execute(
                    sql_all_docs,
                    (vector_literal, vector_literal, top_k),
                )
            rows = cur.fetchall()

    items: List[RetrievedItem] = []
    for row in rows:
        chunk_id, doc_id, chunk_index, text, page, title, score = row
        items.append(
            RetrievedItem(
                docId=int(doc_id),
                chunkId=int(chunk_id),
                chunkIndex=int(chunk_index),
                score=round(float(score), 6),
                text=text,
                citation=Citation(
                    title=title,
                    page=page,
                ),
            )
        )

    logger.info("search_chunks done result_count=%s", len(items))
    return items
