import re
import time
from typing import Optional

import httpx

from app.core.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from app.core.logging_config import logger
from app.models.schemas import RetrievedItem

REFUSAL_ANSWER = "根据当前检索到的内容，我还不能可靠回答这个问题。"


def _make_compact_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def build_refusal_answer(reason: str = "") -> str:
    reason_map = {
        "no_retrieval": "请换一个更具体的问题，或缩小到更明确的文档范围。",
        "no_substantive_evidence": "当前命中的内容主要是标题或来源信息，缺少足够的正文证据。",
        "low_retrieval_confidence": "当前命中的内容和问题关联度不够高，继续作答风险较大。",
        "model_insufficient_evidence": "现有上下文不足以支撑稳定答案。",
    }
    suffix = reason_map.get(reason, "请换一个更具体的问题，或缩小到更明确的文档范围。")
    return f"{REFUSAL_ANSWER} {suffix}".strip()


def is_refusal_answer(answer: str) -> bool:
    normalized = _make_compact_text(answer).lower()
    if not normalized:
        return True

    phrases = [
        REFUSAL_ANSWER.lower(),
        "不能可靠回答",
        "证据不足",
        "上下文不足",
        "未明确说明",
        "insufficient context",
        "not enough context",
        "insufficient evidence",
    ]
    return any(phrase in normalized for phrase in phrases)


def _extract_heading(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return ""

    first = lines[0]

    m = re.match(r"^\[heading\]\s*(.+)$", first, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    m = re.match(r"^#{1,6}\s+(.+)$", first)
    if m:
        return m.group(1).strip()

    return ""


def _is_structural_ordinal_question(question: str) -> bool:
    q = (question or "").strip()

    has_structure_word = any(
        token in q.lower()
        for token in ["heading", "title", "section", "part"]
    ) or any(
        token in q
        for token in ["标题", "小节", "章节", "部分"]
    )

    has_ordinal = bool(
        re.search(
            r"第\s*[一二两三四五六七八九十\d]+\s*(?:个)?|"
            r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\b|"
            r"\b\d+(?:st|nd|rd|th)\b",
            q,
            flags=re.IGNORECASE,
        )
    )

    return has_structure_word and has_ordinal


def _looks_like_source_stub(text: str) -> bool:
    clean = _make_compact_text(text)
    if not clean:
        return True

    line_count = len([line for line in (text or "").splitlines() if line.strip()])
    if "source:" in clean.lower() and len(clean) <= 180:
        return True
    if line_count <= 2 and len(clean) <= 120:
        return True
    return False


def _build_context_text(items: list[RetrievedItem]) -> str:
    contexts = []

    for idx, item in enumerate(items, start=1):
        heading = _extract_heading(item.text)

        header_parts = [
            f"[Source {idx}]",
            f"retrieved_rank={idx}",
            f"chunk_index={item.chunkIndex}",
            f"title={item.citation.title}",
            f"page={item.citation.page}",
        ]

        if heading:
            header_parts.append(f"heading={heading}")
        if item.sectionPath:
            header_parts.append(f"section_path={item.sectionPath}")
        if item.chunkType:
            header_parts.append(f"chunk_type={item.chunkType}")

        header = ", ".join(header_parts)
        contexts.append(f"{header}\n{item.text}")

    return "\n\n".join(contexts)


def _build_prompt(question: str, items: list[RetrievedItem], evidence_score: Optional[float]) -> str:
    context_text = _build_context_text(items)
    structural = _is_structural_ordinal_question(question)

    common_rules = """
You are a RAG question answering assistant.
Answer the user's question using only the provided context.
If the evidence is insufficient, inconsistent, or only contains source headers / metadata without substantive body text, respond exactly in Chinese with:
根据当前检索到的内容，我还不能可靠回答这个问题。
Do not guess, generalize, or fill gaps from prior knowledge.
Prefer the most specific chunk whose body explicitly states the answer.
Keep the answer concise and factual.
The retrieved sources are already sorted by retrieval rank, with Source 1 being the strongest evidence.
""".strip()

    structural_rules = """
This is a structural order question about sections/headings/parts.
Important rules:
1. Respect document order strictly.
2. chunk_index is zero-based document order:
   - chunk_index=0 means the first section
   - chunk_index=1 means the second section
3. Do not swap the first and second sections.
4. Prefer the highest-ranked source that matches the requested order.
5. When answering "what does the Nth heading/part talk about", first identify the heading/title, then summarize its body.
6. If the sources do not support the requested order clearly, refuse instead of guessing.
""".strip()

    caution_rules = ""
    if evidence_score is not None and evidence_score < 0.26:
        caution_rules = "Current retrieval confidence is weak. Be extra conservative and refuse unless the wording is explicit in the evidence."

    prompt_parts = [common_rules]
    if structural:
        prompt_parts.append(structural_rules)
    if caution_rules:
        prompt_parts.append(caution_rules)

    prompt_parts.append(
        f"""
User question:
{question}

Context:
{context_text}
""".strip()
    )

    return "\n\n".join(prompt_parts)


def generate_answer(question: str, items: list[RetrievedItem], evidence_score: Optional[float] = None) -> str:
    if not LLM_API_KEY:
        raise ValueError("LLM_API_KEY is not configured")

    if not items:
        return build_refusal_answer("no_retrieval")

    prompt = _build_prompt(question, items, evidence_score)

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
                "content": "You answer questions only from retrieved context. Never contradict the ranked evidence or fabricate missing facts.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.1,
    }

    logger.info(
        "generate_answer start model=%s item_count=%s structural_ordinal=%s evidence_score=%s",
        LLM_MODEL,
        len(items),
        _is_structural_ordinal_question(question),
        evidence_score,
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
