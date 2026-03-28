import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

from app.core.config import (
    LOCAL_RERANK_SCORE_WEIGHT,
    RERANK_ENABLED,
    RERANK_MODEL,
    RERANK_PROVIDER,
    RERANK_SCORE_WEIGHT,
    RERANK_TOP_N,
)
from app.core.logging_config import logger
from app.db.postgres import get_conn
from app.models.schemas import Citation, RetrievedItem, RoutedDoc
from app.services.embedding_service import vector_to_pg
from app.services.rerank_service import RerankServiceError, rerank_candidates


def _make_compact_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _contains_query_term(text: str, term: str) -> bool:
    haystack = (text or "").lower()
    needle = (term or "").strip().lower()
    if not needle:
        return False

    if re.search(r"[a-z0-9]", needle):
        pattern = r"(?<![a-z0-9_])" + re.escape(needle).replace(r"\ ", r"\s+") + r"(?![a-z0-9_])"
        return re.search(pattern, haystack, flags=re.IGNORECASE) is not None

    return needle in haystack


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


def _looks_like_heading_chunk(text: str) -> bool:
    return bool(_extract_heading(text))


def _mentions_structured_section_lookup(question: str) -> bool:
    keywords = [
        "heading",
        "title",
        "section",
        "part",
        "标题",
        "小节",
        "章节",
        "部分",
    ]
    return any(_contains_query_term(question, keyword) for keyword in keywords)


def _classify_query_intent(question: str) -> Dict[str, bool]:
    q = (question or "").strip().lower()
    summary = any(
        _contains_query_term(q, keyword)
        for keyword in ["summary", "summarize", "overview", "main", "主要", "总结", "概述", "讲了什么"]
    )
    definition = any(
        _contains_query_term(q, keyword)
        for keyword in ["what is", "是什么", "定义", "含义", "指什么", "介绍一下"]
    )
    procedural = any(
        _contains_query_term(q, keyword)
        for keyword in ["step", "steps", "how", "how to", "流程", "步骤", "怎么", "如何"]
    )
    structured = _mentions_structured_section_lookup(question)
    return {
        "summary": summary,
        "definition": definition,
        "procedural": procedural,
        "structured": structured,
    }


def _resolve_query_intent(question: str, query_intent: Optional[Dict[str, bool]]) -> Dict[str, bool]:
    if query_intent:
        signal_keys = ["summary", "definition", "procedural", "structured", "temporal", "threshold"]
        if any(bool(query_intent.get(key)) for key in signal_keys):
            return query_intent
    return _classify_query_intent(question)


def _cn_num_to_int(raw: str) -> Optional[int]:
    raw = (raw or "").strip()
    if not raw:
        return None

    if raw.isdigit():
        return int(raw)

    direct = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    if raw in direct:
        return direct[raw]

    if raw.startswith("十") and len(raw) == 2:
        tail = direct.get(raw[1])
        if tail is not None:
            return 10 + tail

    if raw.endswith("十") and len(raw) == 2:
        head = direct.get(raw[0])
        if head is not None:
            return head * 10

    if len(raw) == 2 and raw[0] in direct and raw[1] in direct and raw[0] != "十":
        if raw[1] == "十":
            return direct[raw[0]] * 10

    return None


def _en_ordinal_to_int(raw: str) -> Optional[int]:
    raw = (raw or "").strip().lower()
    if not raw:
        return None

    mapping = {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
        "sixth": 6,
        "seventh": 7,
        "eighth": 8,
        "ninth": 9,
        "tenth": 10,
    }
    if raw in mapping:
        return mapping[raw]

    m = re.match(r"^(\d+)(st|nd|rd|th)$", raw)
    if m:
        return int(m.group(1))

    return None


def _extract_section_ordinal(question: str) -> Optional[int]:
    q = (question or "").strip()

    cn_match = re.search(
        r"第\s*([一二三四五六七八九十两\d]+)\s*个?\s*(?:heading|标题|title|section|章节|小节|部分)",
        q,
        flags=re.IGNORECASE,
    )
    if cn_match:
        value = _cn_num_to_int(cn_match.group(1))
        if value is not None:
            return value

    cn_match_loose = re.search(
        r"第\s*([一二三四五六七八九十两\d]+)\s*(?:个)?\s*(?:heading|标题|title|section|章节|小节|部分)",
        q,
        flags=re.IGNORECASE,
    )
    if cn_match_loose:
        value = _cn_num_to_int(cn_match_loose.group(1))
        if value is not None:
            return value

    en_match = re.search(
        r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d+(?:st|nd|rd|th))\s+(?:heading|title|section|part)\b",
        q,
        flags=re.IGNORECASE,
    )
    if en_match:
        value = _en_ordinal_to_int(en_match.group(1))
        if value is not None:
            return value

    return None


def _strip_answer_markup(text: str) -> str:
    normalized = (text or "").replace("**", " ").replace("__", " ")
    normalized = re.sub(r"`([^`]*)`", r"\1", normalized)
    normalized = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", normalized)
    return _make_compact_text(normalized)



def _make_snippet(anchor_text: str, text: str, limit: int = 180) -> str:
    clean = _strip_answer_markup(text)
    if not clean:
        return ""

    if len(clean) <= limit:
        return clean

    try:
        terms = sorted(set(_extract_terms(_strip_answer_markup(anchor_text))), key=len, reverse=True)
    except Exception:
        terms = []

    clean_lower = clean.lower()
    anchor = -1

    for term in terms:
        term = (term or "").strip().lower()
        if len(term) < 2:
            continue
        pos = clean_lower.find(term)
        if pos != -1:
            anchor = pos
            break

    if anchor == -1:
        return clean[:limit].rstrip() + "..."

    start = max(0, anchor - limit // 3)
    end = min(len(clean), start + limit)

    if end - start < limit:
        start = max(0, end - limit)

    snippet = clean[start:end].strip()

    if start > 0:
        snippet = "..." + snippet
    if end < len(clean):
        snippet = snippet.rstrip() + "..."

    return snippet



def _looks_like_source_stub_text(text: str) -> bool:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return True

    body_lines = lines[:]
    if re.match(r"^\[heading\]\s*", body_lines[0], flags=re.IGNORECASE) or re.match(r"^#{1,6}\s+", body_lines[0]):
        body_lines = body_lines[1:]

    body = _strip_answer_markup(" ".join(body_lines))
    if not body:
        return True

    if body.lower().startswith("source:") and len(body) <= 180:
        return True
    return False



def _looks_like_source_stub_item(item: RetrievedItem) -> bool:
    return _looks_like_source_stub_text(item.text)



def _item_support_metrics(question: str, item: RetrievedItem) -> Dict[str, float | bool]:
    title = item.citation.title or ""
    heading = item.heading or _extract_heading(item.text)
    section_path = item.sectionPath or ""
    content = " ".join(part for part in [title, heading, section_path, item.text] if part)

    query_overlap = max(
        _keyword_overlap_score(question, content),
        _phrase_hit_score(question, title, content),
        _metadata_phrase_hit_score(question, heading, section_path),
    )

    stub = _looks_like_source_stub_item(item)
    support = 0.68 * max(float(item.score or 0.0), 0.0) + 0.32 * query_overlap
    if not stub:
        support += 0.03
    if heading and _keyword_overlap_score(question, heading) >= 0.5:
        support += 0.03

    return {
        "support": round(max(support, 0.0), 6),
        "query_overlap": round(query_overlap, 6),
        "stub": stub,
    }



def assess_answerability(question: str, items: List[RetrievedItem]) -> Dict[str, object]:
    if not items:
        return {
            "shouldRefuse": True,
            "reason": "no_retrieval",
            "evidenceScore": 0.0,
        }

    query_intent = _classify_query_intent(question)
    metrics = [_item_support_metrics(question, item) for item in items[:5]]
    top = metrics[0]
    substantive_count = sum(1 for row in metrics if not bool(row["stub"]))
    support_count = sum(
        1
        for row in metrics
        if float(row["support"]) >= 0.22 or float(row["query_overlap"]) >= 0.24
    )

    evidence_score = float(top["support"]) + 0.04 * max(0, min(2, support_count - 1))
    evidence_score = round(min(evidence_score, 1.0), 6)

    if substantive_count == 0:
        return {
            "shouldRefuse": True,
            "reason": "no_substantive_evidence",
            "evidenceScore": evidence_score,
        }

    support_threshold = 0.23 if (query_intent["structured"] or query_intent["definition"]) else 0.19
    overlap_threshold = 0.18 if (query_intent["structured"] or query_intent["definition"]) else 0.12

    should_refuse = (
        float(top["support"]) < support_threshold
        and float(top["query_overlap"]) < overlap_threshold
        and support_count == 0
    )

    return {
        "shouldRefuse": should_refuse,
        "reason": "low_retrieval_confidence" if should_refuse else "",
        "evidenceScore": evidence_score,
    }


def _citation_alignment_score(question: str, answer: str, item: RetrievedItem) -> float:
    title = item.citation.title or ""
    heading = item.heading or _extract_heading(item.text)
    section_path = item.sectionPath or ""
    answer_anchor = _strip_answer_markup(" ".join(part for part in [question, answer] if part))
    content = " ".join(part for part in [title, heading, section_path, item.text] if part)

    score = (
        0.45 * max(float(item.score or 0.0), 0.0)
        + 0.23 * _keyword_overlap_score(answer_anchor or question, content)
        + 0.12 * _keyword_overlap_score(question, content)
        + 0.10 * _metadata_phrase_hit_score(answer_anchor or question, heading, section_path)
        + 0.05 * _phrase_hit_score(answer_anchor or question, title, content)
    )

    if not _looks_like_source_stub_item(item):
        score += 0.04
    else:
        score -= 0.12

    if len(_strip_answer_markup(item.text)) >= 140:
        score += 0.03

    return round(max(score, 0.0), 6)



def build_answer_citations(
    question: str,
    items: List[RetrievedItem],
    answer: str = "",
    max_citations: int = 3,
) -> List[Citation]:
    if not items:
        return []

    grouped: Dict[Tuple[str, int], Dict[str, object]] = {}
    non_stub_keys = {
        ((item.citation.title or "").strip(), int(item.citation.page or 1))
        for item in items
        if item.citation and not _looks_like_source_stub_item(item)
    }

    sorted_items = sorted(
        items,
        key=lambda x: (_citation_alignment_score(question, answer, x), float(x.score or 0.0), -int(x.chunkIndex or 0)),
        reverse=True,
    )

    anchor_text = _strip_answer_markup(" ".join(part for part in [question, answer] if part)) or question

    for item in sorted_items:
        citation = item.citation
        if not citation:
            continue

        title = (citation.title or "").strip()
        page = int(citation.page or 1)
        key = (title, page)

        if _looks_like_source_stub_item(item) and key in non_stub_keys:
            continue

        snippet = _make_snippet(anchor_text, item.text)
        alignment_score = _citation_alignment_score(question, answer, item)

        current = grouped.get(key)
        if current is None:
            grouped[key] = {
                "title": title,
                "page": page,
                "snippet": snippet,
                "score": alignment_score,
            }
            continue

        if alignment_score > float(current["score"]):
            current["score"] = alignment_score
            if snippet:
                current["snippet"] = snippet

        current_snippet = str(current.get("snippet") or "").strip()
        if snippet and len(current_snippet) < 60 and len(snippet) > len(current_snippet):
            current["snippet"] = snippet

    merged = sorted(grouped.values(), key=lambda x: float(x["score"]), reverse=True)

    result: List[Citation] = []
    for row in merged[:max_citations]:
        result.append(
            Citation(
                title=str(row["title"]),
                page=int(row["page"]),
                snippet=str(row["snippet"]),
            )
        )

    return result


def _extract_terms(text: str) -> List[str]:
    text = (text or "").lower()

    ascii_terms = re.findall(r"[a-z0-9_]+", text)

    cjk_sequences = re.findall(r"[一-鿿]+", text)
    cjk_terms: List[str] = []
    for seq in cjk_sequences:
        seq = seq.strip()
        if not seq:
            continue
        if len(seq) == 1:
            cjk_terms.append(seq)
        else:
            cjk_terms.extend(seq[i : i + 2] for i in range(len(seq) - 1))
            cjk_terms.append(seq)

    return ascii_terms + cjk_terms


def _keyword_search_terms(question: str, limit: int = 8) -> List[str]:
    question = _make_compact_text(question)
    if not question:
        return []

    stop_terms = {
        "什么",
        "一下",
        "一个",
        "这个",
        "那个",
        "文档",
        "内容",
        "主要",
        "一下子",
        "介绍一下",
        "是什么",
        "讲了什么",
    }

    terms: List[str] = []
    if len(question) <= 48:
        terms.append(question)

    for seq in re.findall(r"[一-鿿]{2,}", question):
        if seq not in stop_terms:
            terms.append(seq)

    for term in _extract_terms(question):
        normalized = term.strip().lower()
        if len(normalized) >= 2 and normalized not in stop_terms:
            terms.append(term)

    for term in re.findall(r"[a-z0-9_]+", question.lower()):
        if len(term) >= 2:
            terms.append(term)

    deduped: List[str] = []
    seen = set()
    for term in terms:
        normalized = term.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(term.strip())
        if len(deduped) >= limit:
            break

    return deduped


def _keyword_overlap_score(question: str, text: str) -> float:
    q_terms = _extract_terms(question)
    t_terms = _extract_terms(text)

    if not q_terms or not t_terms:
        return 0.0

    q_counter = Counter(q_terms)
    t_counter = Counter(t_terms)

    overlap = sum(min(v, t_counter.get(k, 0)) for k, v in q_counter.items())
    total = sum(q_counter.values()) or 1
    return overlap / total


def _phrase_hit_score(question: str, title: str, text: str) -> float:
    q = (question or "").strip().lower()
    if not q:
        return 0.0

    title_l = (title or "").lower()
    text_l = (text or "").lower()

    score = 0.0
    if q and q in title_l:
        score += 1.0
    if q and q in text_l:
        score += 0.6

    return min(score, 1.0)


def _metadata_phrase_hit_score(question: str, heading: str, section_path: str) -> float:
    q = (question or "").strip().lower()
    heading_l = (heading or "").strip().lower()
    section_l = (section_path or "").strip().lower()
    if not q:
        return 0.0

    score = 0.0
    if heading_l:
        if q in heading_l:
            score += 1.0
        elif heading_l in q and len(heading_l) >= 2:
            score += 0.8

    if section_l:
        if q in section_l:
            score += 0.8
        elif section_l in q and len(section_l) >= 4:
            score += 0.4

    return min(score, 1.0)


def _section_path_overlap_score(question: str, section_path: str) -> float:
    clean = (section_path or "").replace(">", " ").strip()
    if not clean:
        return 0.0
    return _keyword_overlap_score(question, clean)


def _looks_like_definition_chunk(text: str, heading: str) -> bool:
    body = text or ""
    heading = heading or ""
    patterns = ["定义", "是指", "指的是", "是用于", "是用来", "是完成"]
    if any(pattern in heading for pattern in ["定义", "概念", "介绍"]):
        return True
    return any(pattern in body for pattern in patterns)


def _looks_like_step_chunk(text: str, heading: str) -> bool:
    heading = heading or ""
    text = text or ""
    if any(keyword in heading for keyword in ["步骤", "流程", "过程", "Step", "Process"]):
        return True
    if re.search(r"(^|\n)\s*(?:\d+[\.)]|[-*+])\s+", text):
        return True
    return False


def _chunk_type_bias(
    chunk_type: str,
    source_type: str,
    query_intent: Dict[str, bool],
    text: str,
    heading: str,
    chunk_index: int,
) -> float:
    chunk_type = (chunk_type or "").strip().lower()
    source_type = (source_type or "").strip().lower()

    bias = 0.0

    if query_intent["structured"]:
        if chunk_type == "section":
            bias += 0.10
        if source_type == "md":
            bias += 0.03

    if query_intent["summary"]:
        if chunk_type in {"section", "paragraph"}:
            bias += 0.04
        if chunk_index <= 1:
            bias += 0.02

    if query_intent["definition"] and _looks_like_definition_chunk(text, heading):
        bias += 0.08

    if query_intent["procedural"] and _looks_like_step_chunk(text, heading):
        bias += 0.08

    return bias


def _rerank_score(
    question: str,
    title: str,
    text: str,
    context_text: str,
    heading: str,
    section_path: str,
    chunk_type: str,
    source_type: str,
    vector_score: float,
    keyword_score: float,
    retrieval_hits: int,
    chunk_index: int,
    query_intent: Dict[str, bool],
) -> float:
    resolved_heading = heading or _extract_heading(text)

    kw = max(_keyword_overlap_score(question, text), _keyword_overlap_score(question, context_text))
    title_kw = _keyword_overlap_score(question, title)
    heading_kw = _keyword_overlap_score(question, resolved_heading) if resolved_heading else 0.0
    section_kw = _section_path_overlap_score(question, section_path)
    phrase = max(_phrase_hit_score(question, title, text), _phrase_hit_score(question, title, context_text))
    metadata_phrase = _metadata_phrase_hit_score(question, resolved_heading, section_path)

    final_score = (
        0.42 * max(vector_score, 0.0)
        + 0.12 * max(keyword_score, 0.0)
        + 0.14 * kw
        + 0.05 * title_kw
        + 0.07 * heading_kw
        + 0.06 * section_kw
        + 0.04 * phrase
        + 0.04 * metadata_phrase
    )

    if retrieval_hits >= 2:
        final_score += 0.05
    elif keyword_score >= 0.35:
        final_score += 0.02

    final_score += _chunk_type_bias(
        chunk_type=chunk_type,
        source_type=source_type,
        query_intent=query_intent,
        text=text,
        heading=resolved_heading,
        chunk_index=chunk_index,
    )

    ordinal = _extract_section_ordinal(question)
    structured_lookup = query_intent["structured"]

    if structured_lookup and resolved_heading:
        final_score += 0.05

    if ordinal is not None and _looks_like_heading_chunk(text):
        distance = abs(chunk_index - (ordinal - 1))
        if distance == 0:
            final_score += 0.40
        elif distance == 1:
            final_score += 0.05
        else:
            final_score -= 0.08

    return round(max(final_score, 0.0), 6)


def _blend_scores(local_score: float, rerank_score: float) -> float:
    local_weight = max(LOCAL_RERANK_SCORE_WEIGHT, 0.0)
    rerank_weight = max(RERANK_SCORE_WEIGHT, 0.0)
    total_weight = local_weight + rerank_weight
    if total_weight <= 0:
        return round(max(local_score, 0.0), 6)

    blended = ((local_score * local_weight) + (rerank_score * rerank_weight)) / total_weight
    return round(max(blended, 0.0), 6)


def _item_debug_preview(row: Dict[str, object]) -> Dict[str, object]:
    local_score = float(row.get("local_score", row.get("final_score") or 0.0) or 0.0)
    blended_score = float(row.get("blended_score", row.get("final_score") or 0.0) or 0.0)
    rerank_score = row.get("rerank_score")
    return {
        "chunkId": int(row.get("chunk_id") or 0),
        "title": str(row.get("title") or ""),
        "heading": str(row.get("heading") or "") or None,
        "sectionPath": str(row.get("section_path") or "") or None,
        "chunkType": str(row.get("chunk_type") or "") or None,
        "sourceType": str(row.get("source_type") or "") or None,
        "localScore": round(local_score, 6),
        "rerankScore": None if rerank_score is None else float(rerank_score),
        "blendedScore": round(blended_score, 6),
    }


def _base_rerank_debug() -> Dict[str, object]:
    return {
        "enabled": bool(RERANK_ENABLED),
        "provider": RERANK_PROVIDER or None,
        "model": RERANK_MODEL or None,
        "callCount": 0,
        "requestedTopN": max(1, int(RERANK_TOP_N)),
        "candidateCount": 0,
        "appliedCount": 0,
        "fallback": False,
        "fallbackReason": None,
        "latencyMs": 0,
        "resolvedIntent": {},
        "localTopItems": [],
        "finalTopItems": [],
        "orderingChanged": False,
    }


def _vector_sql(has_scope: bool) -> str:
    scope_clause = "AND c.doc_id = ANY(%s::bigint[])" if has_scope else ""
    return f"""
        SELECT
            c.id,
            c.doc_id,
            c.chunk_index,
            c.text,
            c.page,
            c.heading,
            c.section_path,
            c.chunk_type,
            c.source_type,
            c.context_text,
            d.title,
            1 - (c.embedding <=> %s::vector) AS score
        FROM chunks c
        JOIN docs d ON d.id = c.doc_id
        WHERE c.embedding IS NOT NULL
          AND d.status = 'ready'
          {scope_clause}
        ORDER BY c.embedding <=> %s::vector
        LIMIT %s
    """


def _fetch_vector_rows(
    vector_literal: str,
    doc_scope: List[int],
    candidate_k: int,
) -> List[Tuple]:
    sql = _vector_sql(bool(doc_scope))
    params: List[object] = [vector_literal]
    if doc_scope:
        params.append(doc_scope)
    params.extend([vector_literal, candidate_k])

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchall()


def _keyword_similarity_expr() -> str:
    return """
        (
            0.24 * similarity(COALESCE(c.heading, ''), %s)
            + 0.18 * similarity(COALESCE(c.section_path, ''), %s)
            + 0.14 * similarity(COALESCE(d.title, ''), %s)
            + 0.24 * similarity(COALESCE(c.context_text, c.text, ''), %s)
            + 0.08 * similarity(COALESCE(c.text, ''), %s)
        )
    """


def _fetch_keyword_rows(
    question: str,
    doc_scope: List[int],
    candidate_k: int,
    query_intent: Dict[str, bool],
) -> List[Tuple]:
    search_terms = _keyword_search_terms(question)
    similarity_expr = _keyword_similarity_expr()

    where_parts: List[str] = []
    where_params: List[object] = []
    for term in search_terms:
        pattern = f"%{term}%"
        for field in [
            "COALESCE(c.heading, '')",
            "COALESCE(c.section_path, '')",
            "COALESCE(d.title, '')",
            "COALESCE(c.context_text, c.text, '')",
            "COALESCE(c.text, '')",
        ]:
            where_parts.append(f"{field} ILIKE %s")
            where_params.append(pattern)

    similarity_threshold = 0.06 if (query_intent["structured"] or query_intent["definition"]) else 0.10

    keyword_filter = f"({similarity_expr} > %s)"
    keyword_filter_params: List[object] = [question, question, question, question, question, similarity_threshold]

    if where_parts:
        keyword_filter = f"(({' OR '.join(where_parts)}) OR {similarity_expr} > %s)"
        keyword_filter_params = where_params + [question, question, question, question, question, similarity_threshold]

    sql = f"""
        SELECT
            c.id,
            c.doc_id,
            c.chunk_index,
            c.text,
            c.page,
            c.heading,
            c.section_path,
            c.chunk_type,
            c.source_type,
            c.context_text,
            d.title,
            {similarity_expr} AS score
        FROM chunks c
        JOIN docs d ON d.id = c.doc_id
        WHERE d.status = 'ready'
          {'AND c.doc_id = ANY(%s::bigint[])' if doc_scope else ''}
          AND {keyword_filter}
        ORDER BY score DESC, c.chunk_index ASC
        LIMIT %s
    """

    exec_params: List[object] = [question, question, question, question, question]
    if doc_scope:
        exec_params.append(doc_scope)
    exec_params.extend(keyword_filter_params)
    exec_params.append(candidate_k)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(exec_params))
            return cur.fetchall()


def _merge_candidate_rows(vector_rows: List[Tuple], keyword_rows: List[Tuple]) -> List[Dict[str, object]]:
    merged: Dict[int, Dict[str, object]] = {}

    def upsert(row: Tuple, source: str) -> None:
        (
            chunk_id,
            doc_id,
            chunk_index,
            text,
            page,
            heading,
            section_path,
            chunk_type,
            source_type,
            context_text,
            title,
            score,
        ) = row

        key = int(chunk_id)
        current = merged.get(key)
        if current is None:
            merged[key] = {
                "chunk_id": key,
                "doc_id": int(doc_id),
                "chunk_index": int(chunk_index),
                "text": text or "",
                "page": page,
                "heading": (heading or "").strip(),
                "section_path": (section_path or "").strip(),
                "chunk_type": (chunk_type or "").strip(),
                "source_type": (source_type or "").strip(),
                "context_text": (context_text or "").strip(),
                "title": title or "",
                "vector_score": 0.0,
                "keyword_score": 0.0,
                "retrieval_hits": 0,
            }
            current = merged[key]

        numeric_score = round(float(score or 0.0), 6)
        if source == "vector":
            current["vector_score"] = max(float(current["vector_score"]), numeric_score)
        else:
            current["keyword_score"] = max(float(current["keyword_score"]), numeric_score)

        current["retrieval_hits"] = int(current["retrieval_hits"]) | (1 if source == "vector" else 2)

        if not current["heading"]:
            current["heading"] = (heading or "").strip()
        if not current["section_path"]:
            current["section_path"] = (section_path or "").strip()
        if not current["chunk_type"]:
            current["chunk_type"] = (chunk_type or "").strip()
        if not current["source_type"]:
            current["source_type"] = (source_type or "").strip()
        if not current["context_text"]:
            current["context_text"] = (context_text or "").strip()

    for row in vector_rows:
        upsert(row, "vector")

    for row in keyword_rows:
        upsert(row, "keyword")

    normalized: List[Dict[str, object]] = []
    for row in merged.values():
        retrieval_hits = int(row["retrieval_hits"])
        normalized.append(
            {
                **row,
                "retrieval_hits": (1 if retrieval_hits & 1 else 0) + (1 if retrieval_hits & 2 else 0),
            }
        )

    return normalized



def _doc_vector_sql() -> str:
    return """
        SELECT
            d.id,
            d.title,
            d.source_type,
            d.doc_summary,
            d.doc_keywords,
            d.route_text,
            1 - (d.route_embedding <=> %s::vector) AS score
        FROM docs d
        WHERE d.status = 'ready'
          AND d.route_embedding IS NOT NULL
        ORDER BY d.route_embedding <=> %s::vector
        LIMIT %s
    """



def _fetch_doc_vector_rows(vector_literal: str, candidate_k: int) -> List[Tuple]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(_doc_vector_sql(), (vector_literal, vector_literal, candidate_k))
            return cur.fetchall()



def _doc_keyword_similarity_expr() -> str:
    return """
        (
            0.30 * similarity(COALESCE(d.title, ''), %s)
            + 0.24 * similarity(COALESCE(d.doc_summary, ''), %s)
            + 0.18 * similarity(COALESCE(d.doc_keywords, ''), %s)
            + 0.18 * similarity(COALESCE(d.route_text, ''), %s)
        )
    """



def _fetch_doc_keyword_rows(
    question: str,
    candidate_k: int,
    query_intent: Dict[str, bool],
) -> List[Tuple]:
    search_terms = _keyword_search_terms(question)
    similarity_expr = _doc_keyword_similarity_expr()

    where_parts: List[str] = []
    where_params: List[object] = []
    for term in search_terms:
        pattern = f"%{term}%"
        for field in [
            "COALESCE(d.title, '')",
            "COALESCE(d.doc_summary, '')",
            "COALESCE(d.doc_keywords, '')",
            "COALESCE(d.route_text, '')",
        ]:
            where_parts.append(f"{field} ILIKE %s")
            where_params.append(pattern)

    similarity_threshold = 0.05 if (query_intent["structured"] or query_intent["definition"]) else 0.08

    keyword_filter = f"({similarity_expr} > %s)"
    keyword_filter_params: List[object] = [question, question, question, question, similarity_threshold]

    if where_parts:
        keyword_filter = f"(({' OR '.join(where_parts)}) OR {similarity_expr} > %s)"
        keyword_filter_params = where_params + [question, question, question, question, similarity_threshold]

    sql = f"""
        SELECT
            d.id,
            d.title,
            d.source_type,
            d.doc_summary,
            d.doc_keywords,
            d.route_text,
            {similarity_expr} AS score
        FROM docs d
        WHERE d.status = 'ready'
          AND {keyword_filter}
        ORDER BY score DESC, d.id ASC
        LIMIT %s
    """

    exec_params: List[object] = [question, question, question, question]
    exec_params.extend(keyword_filter_params)
    exec_params.append(candidate_k)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(exec_params))
            return cur.fetchall()



def _merge_doc_candidate_rows(vector_rows: List[Tuple], keyword_rows: List[Tuple]) -> List[Dict[str, object]]:
    merged: Dict[int, Dict[str, object]] = {}

    def upsert(row: Tuple, source: str) -> None:
        doc_id, title, source_type, doc_summary, doc_keywords, route_text, score = row

        key = int(doc_id)
        current = merged.get(key)
        if current is None:
            merged[key] = {
                "doc_id": key,
                "title": title or "",
                "source_type": (source_type or "").strip(),
                "doc_summary": (doc_summary or "").strip(),
                "doc_keywords": (doc_keywords or "").strip(),
                "route_text": (route_text or "").strip(),
                "vector_score": 0.0,
                "keyword_score": 0.0,
                "retrieval_hits": 0,
            }
            current = merged[key]

        numeric_score = round(float(score or 0.0), 6)
        if source == "vector":
            current["vector_score"] = max(float(current["vector_score"]), numeric_score)
        else:
            current["keyword_score"] = max(float(current["keyword_score"]), numeric_score)

        current["retrieval_hits"] = int(current["retrieval_hits"]) | (1 if source == "vector" else 2)

    for row in vector_rows:
        upsert(row, "vector")

    for row in keyword_rows:
        upsert(row, "keyword")

    normalized: List[Dict[str, object]] = []
    for row in merged.values():
        retrieval_hits = int(row["retrieval_hits"])
        normalized.append(
            {
                **row,
                "retrieval_hits": (1 if retrieval_hits & 1 else 0) + (1 if retrieval_hits & 2 else 0),
            }
        )

    return normalized





def _term_coverage_score(question: str, text: str, limit: int = 8) -> float:
    haystack = (text or "").lower()
    terms = []
    seen = set()
    for term in _keyword_search_terms(question, limit=limit):
        normalized = (term or "").strip().lower()
        if len(normalized) < 2 or normalized in seen:
            continue
        seen.add(normalized)
        terms.append(normalized)

    if not terms:
        return 0.0

    hits = sum(1 for term in terms if term in haystack)
    return hits / len(terms)



def _exact_phrase_bonus(question: str, text: str) -> float:
    q = _make_compact_text(question).lower()
    t = _make_compact_text(text).lower()
    if not q or not t:
        return 0.0
    if q in t:
        return 1.0
    return 0.0


def _normalized_ascii_terms(text: str) -> List[str]:
    return [term for term in re.findall(r"[a-z0-9_]+", (text or "").lower()) if len(term) >= 3]


def _infer_doc_domain_tokens(title: str, summary: str, keywords: str, route_text: str) -> set[str]:
    material = " ".join([title or "", summary or "", keywords or "", route_text or ""]).lower()
    tokens = set(_normalized_ascii_terms(material))

    if any(term in material for term in ["??", "??", "??", "??", "??", "??"]):
        tokens.add("ops")
    if any(term in material for term in ["??", "??", "??", "??", "??"]):
        tokens.add("product")
    if any(term in material for term in ["??", "??", "metadata", "??"]):
        tokens.add("definition")

    return tokens


def _infer_query_domain_tokens(question: str, query_intent: Dict[str, bool]) -> set[str]:
    q = (question or "").lower()
    tokens = set(_normalized_ascii_terms(q))

    if query_intent["procedural"] or any(term in q for term in ["??", "??", "??", "??", "??", "??"]):
        tokens.add("ops")
    if query_intent["summary"] or any(term in q for term in ["??", "??", "??", "??", "??", "??"]):
        tokens.add("product")
    if query_intent["definition"] or any(term in q for term in ["??", "??", "metadata", "??"]):
        tokens.add("definition")

    return tokens


def _domain_alignment_score(question: str, row: Dict[str, object], query_intent: Dict[str, bool]) -> float:
    query_tokens = _infer_query_domain_tokens(question, query_intent)
    if not query_tokens:
        return 0.0

    doc_tokens = _infer_doc_domain_tokens(
        title=str(row.get("title") or ""),
        summary=str(row.get("doc_summary") or ""),
        keywords=str(row.get("doc_keywords") or ""),
        route_text=str(row.get("route_text") or ""),
    )

    if not doc_tokens:
        return 0.0

    overlap = len(query_tokens & doc_tokens)
    if overlap == 0:
        return -0.08

    coverage = overlap / max(1, len(query_tokens))
    return round(0.12 * coverage, 6)


def _route_min_score_threshold(query_intent: Dict[str, bool]) -> float:
    if query_intent["structured"]:
        return 0.12
    if query_intent["procedural"]:
        return 0.16
    if query_intent["definition"]:
        return 0.15
    if query_intent["summary"]:
        return 0.14
    return 0.17


def _route_relative_floor(query_intent: Dict[str, bool]) -> float:
    if query_intent["procedural"]:
        return 0.42
    if query_intent["structured"] or query_intent["definition"]:
        return 0.38
    return 0.35


def _route_reason(
    row: Dict[str, object],
    query_intent: Dict[str, bool],
    domain_alignment: float,
) -> str:
    reasons: List[str] = []
    if float(row.get("vector_score") or 0.0) >= 0.30:
        reasons.append("vector")
    if float(row.get("keyword_score") or 0.0) >= 0.12:
        reasons.append("keyword")
    if domain_alignment > 0:
        reasons.append("domain")
    if query_intent["procedural"]:
        reasons.append("procedural")
    elif query_intent["definition"]:
        reasons.append("definition")
    elif query_intent["summary"]:
        reasons.append("summary")
    elif query_intent["structured"]:
        reasons.append("structured")

    deduped: List[str] = []
    seen = set()
    for reason in reasons:
        if reason in seen:
            continue
        seen.add(reason)
        deduped.append(reason)
    return "+".join(deduped) if deduped else "fallback"

def _doc_route_score(
    question: str,
    title: str,
    doc_summary: str,
    doc_keywords: str,
    route_text: str,
    source_type: str,
    vector_score: float,
    keyword_score: float,
    retrieval_hits: int,
    query_intent: Dict[str, bool],
) -> float:
    title_kw = _keyword_overlap_score(question, title)
    summary_kw = _keyword_overlap_score(question, doc_summary)
    keywords_kw = _keyword_overlap_score(question, (doc_keywords or "").replace(",", " "))
    route_kw = _keyword_overlap_score(question, route_text)
    phrase = _phrase_hit_score(question, title, route_text or doc_summary)

    title_coverage = _term_coverage_score(question, title)
    keyword_coverage = _term_coverage_score(question, doc_keywords)
    summary_coverage = _term_coverage_score(question, doc_summary)
    exact_title_bonus = _exact_phrase_bonus(question, title)
    exact_keyword_bonus = _exact_phrase_bonus(question, doc_keywords)

    final_score = (
        0.34 * max(vector_score, 0.0)
        + 0.18 * max(keyword_score, 0.0)
        + 0.12 * title_kw
        + 0.10 * summary_kw
        + 0.08 * keywords_kw
        + 0.06 * route_kw
        + 0.05 * phrase
        + 0.10 * title_coverage
        + 0.07 * keyword_coverage
        + 0.05 * summary_coverage
    )

    if retrieval_hits >= 2:
        final_score += 0.06
    elif keyword_score >= 0.28:
        final_score += 0.02

    if exact_title_bonus > 0:
        final_score += 0.08
    if exact_keyword_bonus > 0:
        final_score += 0.05

    if query_intent["structured"] and source_type == "md":
        final_score += 0.03
    if query_intent["procedural"] and source_type == "md":
        final_score += 0.03
    if query_intent["definition"] and (title_coverage >= 0.34 or keyword_coverage >= 0.34 or summary_kw >= 0.18):
        final_score += 0.04
    if query_intent["summary"] and summary_coverage >= 0.34:
        final_score += 0.03

    weak_title_and_keyword = title_coverage == 0.0 and keyword_coverage == 0.0
    if weak_title_and_keyword and summary_kw < 0.08 and route_kw < 0.08:
        final_score -= 0.05
    if source_type == "txt" and weak_title_and_keyword and retrieval_hits < 2:
        final_score -= 0.03

    return round(max(final_score, 0.0), 6)





def _doc_dedupe_key(row: Dict[str, object]) -> str:
    title = _make_compact_text(str(row.get("title") or "")).lower()
    source_type = _make_compact_text(str(row.get("source_type") or "")).lower()
    summary = _make_compact_text(str(row.get("doc_summary") or "")).lower()
    route_text = _make_compact_text(str(row.get("route_text") or "")).lower()
    keywords = _make_compact_text(str(row.get("doc_keywords") or "")).lower()

    semantic_anchor = summary or route_text[:240] or keywords
    semantic_anchor = semantic_anchor[:320]
    return f"{source_type}|{title}|{semantic_anchor}"



def _dedupe_doc_route_rows(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    deduped: List[Dict[str, object]] = []
    seen = set()

    for row in rows:
        key = _doc_dedupe_key(row)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    return deduped

def route_documents(
    question: str,
    question_embedding: List[float],
    top_n: int = 4,
    query_intent: Optional[Dict[str, bool]] = None,
) -> List[RoutedDoc]:
    vector_literal = vector_to_pg(question_embedding)
    query_intent = _resolve_query_intent(question, query_intent)

    vector_candidate_k = min(max(top_n * 4, 8), 20)
    keyword_candidate_k = min(max(top_n * 5, 10), 24)

    vector_rows = _fetch_doc_vector_rows(vector_literal=vector_literal, candidate_k=vector_candidate_k)
    keyword_rows = _fetch_doc_keyword_rows(
        question=question,
        candidate_k=keyword_candidate_k,
        query_intent=query_intent,
    )

    merged_rows = _merge_doc_candidate_rows(vector_rows, keyword_rows)

    rescored_rows = []
    for row in merged_rows:
        base_score = _doc_route_score(
            question=question,
            title=str(row["title"] or ""),
            doc_summary=str(row["doc_summary"] or ""),
            doc_keywords=str(row["doc_keywords"] or ""),
            route_text=str(row["route_text"] or ""),
            source_type=str(row["source_type"] or ""),
            vector_score=float(row["vector_score"] or 0.0),
            keyword_score=float(row["keyword_score"] or 0.0),
            retrieval_hits=int(row["retrieval_hits"] or 0),
            query_intent=query_intent,
        )
        domain_alignment = _domain_alignment_score(question=question, row=row, query_intent=query_intent)
        final_score = round(max(base_score + domain_alignment, 0.0), 6)
        rescored_rows.append(
            {
                **row,
                "base_score": base_score,
                "domain_alignment": domain_alignment,
                "final_score": final_score,
                "reason": _route_reason(row=row, query_intent=query_intent, domain_alignment=domain_alignment),
            }
        )

    rescored_rows.sort(
        key=lambda x: (x["final_score"], x["vector_score"], x["keyword_score"]),
        reverse=True,
    )

    deduped_rows = _dedupe_doc_route_rows(rescored_rows)
    if not deduped_rows:
        return []

    absolute_floor = _route_min_score_threshold(query_intent)
    leading_score = float(deduped_rows[0]["final_score"] or 0.0)
    relative_floor = round(leading_score * _route_relative_floor(query_intent), 6)
    score_floor = max(absolute_floor, relative_floor)

    filtered_rows = []
    for index, row in enumerate(deduped_rows):
        score = float(row["final_score"] or 0.0)
        retrieval_hits = int(row["retrieval_hits"] or 0)
        weak_single_hit = retrieval_hits < 2 and score < score_floor + 0.04
        if index == 0:
            filtered_rows.append(row)
            continue
        if score < score_floor:
            continue
        if weak_single_hit:
            continue
        filtered_rows.append(row)

    final_rows = filtered_rows[:top_n]
    routed_docs = [
        RoutedDoc(
            docId=int(row["doc_id"]),
            title=str(row["title"]),
            score=float(row["final_score"]),
            summary=str(row["doc_summary"]) or None,
            keywords=str(row["doc_keywords"]) or None,
            sourceType=str(row["source_type"]) or None,
            reason=str(row["reason"]) or None,
        )
        for row in final_rows
    ]

    logger.info(
        "route_documents question_len=%s vector_candidates=%s keyword_candidates=%s merged_candidates=%s deduped_candidates=%s filtered_candidates=%s score_floor=%.4f result_count=%s top_preview=%s",
        len(question),
        len(vector_rows),
        len(keyword_rows),
        len(merged_rows),
        len(deduped_rows),
        len(final_rows),
        score_floor,
        len(routed_docs),
        [
            {
                "doc_id": row["doc_id"],
                "title": row["title"],
                "source_type": row["source_type"],
                "vector_score": row["vector_score"],
                "keyword_score": row["keyword_score"],
                "base_score": row["base_score"],
                "domain_alignment": row["domain_alignment"],
                "final_score": row["final_score"],
                "reason": row["reason"],
            }
            for row in final_rows
        ],
    )

    return routed_docs

def search_chunks(
    question: str,
    question_embedding: List[float],
    doc_scope: List[int],
    top_k: int,
    query_intent: Optional[Dict[str, bool]] = None,
) -> Tuple[List[RetrievedItem], Dict[str, object]]:
    vector_literal = vector_to_pg(question_embedding)
    query_intent = _resolve_query_intent(question, query_intent)
    rerank_debug = _base_rerank_debug()

    vector_candidate_multiplier = 6 if (query_intent["structured"] or query_intent["procedural"]) else 4
    vector_candidate_cap = 80 if query_intent["structured"] else 60
    vector_candidate_k = min(max(top_k * vector_candidate_multiplier, 12), vector_candidate_cap)

    keyword_candidate_multiplier = 6 if (query_intent["structured"] or query_intent["definition"]) else 4
    keyword_candidate_cap = 90 if query_intent["structured"] else 70
    keyword_candidate_k = min(max(top_k * keyword_candidate_multiplier, 12), keyword_candidate_cap)

    logger.info(
        "search_chunks start top_k=%s vector_candidate_k=%s keyword_candidate_k=%s doc_scope_count=%s query_intent=%s",
        top_k,
        vector_candidate_k,
        keyword_candidate_k,
        len(doc_scope),
        query_intent,
    )

    vector_rows = _fetch_vector_rows(
        vector_literal=vector_literal,
        doc_scope=doc_scope,
        candidate_k=vector_candidate_k,
    )
    keyword_rows = _fetch_keyword_rows(
        question=question,
        doc_scope=doc_scope,
        candidate_k=keyword_candidate_k,
        query_intent=query_intent,
    )

    merged_rows = _merge_candidate_rows(vector_rows, keyword_rows)

    rescored_rows = []
    for row in merged_rows:
        resolved_heading = str(row["heading"] or "").strip() or _extract_heading(str(row["text"] or ""))
        clean_section_path = str(row["section_path"] or "").strip()
        clean_chunk_type = str(row["chunk_type"] or "").strip()
        clean_source_type = str(row["source_type"] or "").strip()

        final_score = _rerank_score(
            question=question,
            title=str(row["title"] or ""),
            text=str(row["text"] or ""),
            heading=resolved_heading,
            section_path=clean_section_path,
            chunk_type=clean_chunk_type,
            source_type=clean_source_type,
            context_text=str(row.get("context_text") or ""),
            vector_score=float(row["vector_score"] or 0.0),
            keyword_score=float(row["keyword_score"] or 0.0),
            retrieval_hits=int(row["retrieval_hits"] or 0),
            chunk_index=int(row["chunk_index"]),
            query_intent=query_intent,
        )
        rescored_rows.append(
            {
                **row,
                "heading": resolved_heading,
                "section_path": clean_section_path,
                "chunk_type": clean_chunk_type,
                "source_type": clean_source_type,
                "final_score": final_score,
            }
        )

    rescored_rows.sort(
        key=lambda x: (x["final_score"], x["vector_score"], x["keyword_score"]),
        reverse=True,
    )

    local_top_rows = rescored_rows[:top_k]
    rerank_debug["resolvedIntent"] = dict(query_intent)
    rerank_debug["localTopItems"] = [_item_debug_preview(row) for row in local_top_rows]

    final_rows = list(local_top_rows)
    if RERANK_ENABLED and rescored_rows:
        rerank_debug["callCount"] = 1
        rerank_pool_size = min(len(rescored_rows), max(top_k, int(RERANK_TOP_N)))
        rerank_debug["requestedTopN"] = rerank_pool_size
        rerank_debug["candidateCount"] = rerank_pool_size

        rerank_rows = rescored_rows[:rerank_pool_size]
        rerank_documents = [
            str(row.get("context_text") or row.get("text") or "").strip()
            for row in rerank_rows
        ]

        try:
            rerank_scores, rerank_latency_ms = rerank_candidates(
                query=question,
                documents=rerank_documents,
                top_n=rerank_pool_size,
            )
            rerank_debug["latencyMs"] = rerank_latency_ms
            rerank_debug["appliedCount"] = len(rerank_scores)

            blended_rows = []
            for index, row in enumerate(rerank_rows):
                local_score = float(row["final_score"] or 0.0)
                rerank_score = float(rerank_scores[index])
                blended_rows.append(
                    {
                        **row,
                        "local_score": round(local_score, 6),
                        "rerank_score": rerank_score,
                        "blended_score": _blend_scores(local_score, rerank_score),
                    }
                )

            blended_rows.sort(
                key=lambda x: (
                    x["blended_score"],
                    x["local_score"],
                    x["vector_score"],
                    x["keyword_score"],
                ),
                reverse=True,
            )
            final_rows = blended_rows[:top_k]
        except RerankServiceError as exc:
            rerank_debug["fallback"] = True
            rerank_debug["fallbackReason"] = str(exc)
            logger.warning("search_chunks rerank fallback reason=%s", str(exc))
        except Exception as exc:
            rerank_debug["fallback"] = True
            rerank_debug["fallbackReason"] = str(exc)
            logger.exception("search_chunks rerank unexpected_error=%s", str(exc))

    rerank_debug["finalTopItems"] = [_item_debug_preview(row) for row in final_rows]
    rerank_debug["orderingChanged"] = [
        int(row.get("chunk_id") or 0) for row in local_top_rows
    ] != [
        int(row.get("chunk_id") or 0) for row in final_rows
    ]

    items: List[RetrievedItem] = []
    for row in final_rows:
        local_score = float(row.get("local_score", row["final_score"]) or 0.0)
        rerank_score = row.get("rerank_score")
        blended_score = float(row.get("blended_score", row["final_score"]) or 0.0)
        items.append(
            RetrievedItem(
                docId=int(row["doc_id"]),
                chunkId=int(row["chunk_id"]),
                chunkIndex=int(row["chunk_index"]),
                score=blended_score,
                localScore=round(local_score, 6),
                rerankScore=None if rerank_score is None else float(rerank_score),
                blendedScore=round(blended_score, 6),
                text=str(row["text"]),
                heading=str(row["heading"]) or None,
                sectionPath=str(row["section_path"]) or None,
                chunkType=str(row["chunk_type"]) or None,
                sourceType=str(row["source_type"]) or None,
                citation=Citation(
                    title=str(row["title"]),
                    page=int(row["page"] or 1),
                    snippet=_make_snippet(question, str(row["text"])),
                ),
            )
        )

    logger.info(
        "search_chunks done vector_candidates=%s keyword_candidates=%s merged_candidates=%s result_count=%s rerank_enabled=%s rerank_applied=%s rerank_fallback=%s top_preview=%s",
        len(vector_rows),
        len(keyword_rows),
        len(merged_rows),
        len(items),
        rerank_debug["enabled"],
        rerank_debug["appliedCount"],
        rerank_debug["fallback"],
        [
            {
                "chunk_id": row["chunk_id"],
                "chunk_index": row["chunk_index"],
                "heading": row["heading"],
                "section_path": row["section_path"],
                "chunk_type": row["chunk_type"],
                "source_type": row["source_type"],
                "vector_score": row["vector_score"],
                "keyword_score": row["keyword_score"],
                "retrieval_hits": row["retrieval_hits"],
                "final_score": row["final_score"],
                "local_score": row.get("local_score", row["final_score"]),
                "rerank_score": row.get("rerank_score"),
                "blended_score": row.get("blended_score", row["final_score"]),
            }
            for row in final_rows
        ],
    )
    return items, rerank_debug



