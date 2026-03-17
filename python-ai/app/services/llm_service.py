import time

import httpx

from app.core.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from app.core.logging_config import logger
from app.models.schemas import RetrievedItem


def generate_answer(question: str, items: list[RetrievedItem]) -> str:
    if not LLM_API_KEY:
        raise ValueError("LLM_API_KEY is not configured")

    if not items:
        return "I could not find relevant context in the selected documents."

    contexts = []
    for idx, item in enumerate(items, start=1):
        contexts.append(
            f"[Source {idx}] title={item.citation.title}, page={item.citation.page}\n{item.text}"
        )

    context_text = "\n\n".join(contexts)

    prompt = f"""You are a RAG question answering assistant.
Answer the user's question using only the provided context.
If the context is insufficient, say so clearly.
Keep the answer concise and factual.

User question:
{question}

Context:
{context_text}
"""

    url = f"{LLM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You answer questions only from retrieved context.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.2,
    }

    logger.info(
        "generate_answer start model=%s item_count=%s",
        LLM_MODEL,
        len(items),
    )

    start_time = time.time()
    with httpx.Client(timeout=90.0) as client:
        resp = client.post(url, headers=headers, json=payload)
    elapsed_ms = int((time.time() - start_time) * 1000)

    logger.info(
        "generate_answer response status_code=%s elapsed_ms=%s",
        resp.status_code,
        elapsed_ms,
    )

    if resp.status_code != 200:
        logger.error("generate_answer failed body=%s", resp.text)
        raise ValueError(f"llm request failed: {resp.status_code} {resp.text}")

    body = resp.json()
    choices = body.get("choices", [])
    if not choices:
        raise ValueError("llm response missing choices")

    message = choices[0].get("message", {})
    content = message.get("content", "").strip()
    if not content:
        raise ValueError("llm response content is empty")

    return content
