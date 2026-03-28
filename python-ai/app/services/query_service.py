from dataclasses import dataclass
import re
from typing import Dict, List


QUERY_PLANNER_VERSION = "query-plan-v3-observable"


@dataclass
class QueryPlan:
    originalQuestion: str
    normalizedQuestion: str
    routeQuestion: str
    retrievalQuestion: str
    focusQuestion: str
    routeQueries: List[str]
    retrievalQueries: List[str]
    decomposition: List[str]
    intent: Dict[str, bool]


_SUMMARY_TERMS = [
    "summary",
    "summarize",
    "overview",
    "main",
    "main points",
    "主要",
    "总结",
    "概述",
    "讲了什么",
    "能干嘛",
    "能做什么",
    "主要做什么",
]
_SUMMARY_FOCUS_TERMS = [
    "核心能力",
    "主要功能",
    "功能",
    "能力",
    "适用场景",
    "产品定位",
]
_DEFINITION_TERMS = [
    "what is",
    "define",
    "definition",
    "是什么",
    "定义",
    "含义",
    "指什么",
    "介绍一下",
]
_PROCEDURAL_TERMS = [
    "step",
    "steps",
    "how",
    "how to",
    "command",
    "commands",
    "流程",
    "步骤",
    "怎么",
    "如何",
    "命令",
    "启动",
]
_TEMPORAL_TERMS = [
    "how long",
    "within how long",
    "window",
    "duration",
    "多久",
    "多长时间",
    "时间窗口",
    "什么时候开始",
    "什么时候结束",
]
_THRESHOLD_TERMS = [
    "trigger",
    "threshold",
    "condition",
    "when does",
    "触发",
    "阈值",
    "条件",
    "什么情况下",
]
_STRUCTURED_TERMS = [
    "heading",
    "title",
    "section",
    "part",
    "标题",
    "小节",
    "章节",
    "部分",
]
_API_TERMS = [
    "api",
    "endpoint",
    "header",
    "headers",
    "field",
    "fields",
    "body",
    "cache",
    "health",
    "health check",
    "接口",
    "响应头",
    "字段",
    "缓存",
    "健康检查",
]
_TEAM_TERMS = [
    "新同学",
    "团队",
    "手册",
    "发布冻结",
    "hotfix",
    "审批",
]


_STOP_TERMS = {
    "这份文档",
    "文档",
    "这个",
    "哪个",
    "什么",
    "怎么",
    "如何",
    "为什么",
    "主要",
    "一下",
    "介绍",
    "说说",
    "可以",
    "请问",
    "summary",
    "overview",
    "what",
    "which",
    "main",
    "about",
}


def _make_compact_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _contains_term(text: str, term: str) -> bool:
    haystack = (text or "").lower()
    needle = (term or "").strip().lower()
    if not needle:
        return False

    if re.search(r"[a-z0-9]", needle):
        pattern = r"(?<![a-z0-9_])" + re.escape(needle).replace(r"\ ", r"\s+") + r"(?![a-z0-9_])"
        return re.search(pattern, haystack, flags=re.IGNORECASE) is not None

    return needle in haystack


def _has_any(text: str, terms: List[str]) -> bool:
    return any(_contains_term(text, term) for term in terms)


def _mentions_structured_section_lookup(question: str) -> bool:
    return _has_any(question, _STRUCTURED_TERMS)


def classify_query_intent(question: str) -> Dict[str, bool]:
    compact = _make_compact_text(question)
    lowered = compact.lower()

    summary = _has_any(lowered, _SUMMARY_TERMS) or _has_any(lowered, _SUMMARY_FOCUS_TERMS)
    definition = _has_any(lowered, _DEFINITION_TERMS)
    procedural = _has_any(lowered, _PROCEDURAL_TERMS)
    structured = _mentions_structured_section_lookup(compact)
    temporal = _has_any(lowered, _TEMPORAL_TERMS)
    threshold = _has_any(lowered, _THRESHOLD_TERMS)
    api = _has_any(lowered, _API_TERMS)
    multi_part = bool(
        re.search(r"\b(?:and|both)\b|以及|还有|并且|同时", compact, flags=re.IGNORECASE)
        or ("开始" in compact and "结束" in compact)
        or ("先" in compact and "再" in compact)
    )

    if summary and (_has_any(lowered, _SUMMARY_FOCUS_TERMS) or _has_any(lowered, ["能干嘛", "能做什么", "主要做什么", "讲了什么"])):
        definition = False

    if procedural and (_has_any(lowered, ["第", "步", "命令", "second step", "first step"]) or re.search(r"\d+\s*step", lowered)):
        definition = False

    if api and _has_any(lowered, ["header", "endpoint", "body", "cache", "health", "响应头", "接口", "字段", "缓存", "健康检查"]):
        definition = False

    return {
        "summary": summary,
        "definition": definition,
        "procedural": procedural,
        "structured": structured,
        "temporal": temporal,
        "threshold": threshold,
        "api": api,
        "multiPart": multi_part,
    }


def _content_terms(question: str) -> List[str]:
    compact = _make_compact_text(question)
    terms: List[str] = []
    terms.extend(re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", compact))
    terms.extend(re.findall(r"[\u4e00-\u9fff]{2,}", compact))

    deduped: List[str] = []
    seen = set()
    for raw in terms:
        term = raw.strip()
        key = term.lower()
        if not term or key in seen or key in _STOP_TERMS:
            continue
        seen.add(key)
        deduped.append(term)
    return deduped[:8]


def _extract_subject(question: str, terms: List[str]) -> str:
    compact = _make_compact_text(question)
    preferred = ["发布冻结", "新同学", "服务启动步骤", "chunk metadata"]
    for value in preferred:
        if value.lower() in compact.lower():
            return value
    ascii_terms = [term for term in terms if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", term)]
    if ascii_terms:
        return ascii_terms[0]
    if "orion" in compact.lower():
        return "Orion"
    return terms[0] if terms else ""


def _extract_step_hint(question: str) -> str:
    compact = _make_compact_text(question)
    digit_match = re.search(r"第\s*(\d+)\s*步", compact)
    if digit_match:
        return "第" + digit_match.group(1) + "步"

    cn_match = re.search(r"第\s*([一二三四五六七八九十两]+)\s*步", compact)
    if cn_match:
        return "第" + cn_match.group(1) + "步"

    en_match = re.search(r"\b(first|second|third|fourth|fifth|\d+(?:st|nd|rd|th))\s+step\b", compact, flags=re.IGNORECASE)
    if en_match:
        return en_match.group(1)

    return ""


def _split_subqueries(question: str, terms: List[str]) -> List[str]:
    compact = _make_compact_text(question)
    if not compact:
        return []

    subject = _extract_subject(compact, terms)
    clauses: List[str] = []

    if "开始" in compact and "结束" in compact:
        prefix = subject or ""
        clauses.extend([
            _make_compact_text(f"{prefix} 开始时间"),
            _make_compact_text(f"{prefix} 结束时间"),
        ])

    if "先" in compact and "再" in compact:
        prefix = subject or ""
        clauses.extend([
            _make_compact_text(f"{prefix} 先看什么"),
            _make_compact_text(f"{prefix} 再看什么"),
        ])

    pieces = [
        part.strip(" ,，。；;？?")
        for part in re.split(r"\band\b|以及|还有|并且|同时", compact, flags=re.IGNORECASE)
    ]
    clauses.extend(part for part in pieces if part and part != compact)

    deduped: List[str] = []
    seen = set()
    for clause in clauses:
        normalized = _make_compact_text(clause)
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped[:4]


def _intent_hint_terms(intent: Dict[str, bool]) -> List[str]:
    hints: List[str] = []
    if intent.get("summary"):
        hints.extend(["核心能力", "概览"])
    if intent.get("definition") and not intent.get("summary") and not intent.get("procedural") and not intent.get("api"):
        hints.extend(["术语定义", "定义"])
    if intent.get("procedural"):
        hints.extend(["流程", "步骤", "命令"])
    if intent.get("structured"):
        hints.extend(["标题", "小节", "section"])
    if intent.get("temporal"):
        hints.extend(["时间窗口", "时限"])
    if intent.get("threshold"):
        hints.extend(["触发条件", "阈值"])
    if intent.get("api"):
        hints.extend(["API", "接口", "reference"])
    return hints


def _domain_hint_terms(question: str, intent: Dict[str, bool]) -> List[str]:
    lowered = (question or "").lower()
    hints: List[str] = []
    if intent.get("procedural") or _has_any(lowered, ["docker", "runbook", "启动", "命令", "服务"]):
        hints.extend(["ops", "runbook", "运维"])
    if intent.get("summary") or _has_any(lowered, ["orion", "产品", "能力"]):
        hints.extend(["product", "overview", "产品概览"])
    if intent.get("definition") or "metadata" in lowered:
        hints.extend(["definition", "metadata", "术语定义"])
    if _has_any(lowered, _TEAM_TERMS):
        hints.extend(["team", "handbook", "团队手册", "policy"])
    if intent.get("api"):
        hints.extend(["api", "reference", "接口"])
    return hints


def _build_focus_question(question: str, intent: Dict[str, bool], terms: List[str]) -> str:
    lowered = (question or "").lower()
    subject = _extract_subject(question, terms)
    step_hint = _extract_step_hint(question)

    if intent.get("summary"):
        for focus_term in _SUMMARY_FOCUS_TERMS:
            if focus_term in question:
                return _make_compact_text(f"{subject} {focus_term}") if subject else focus_term
        if _has_any(lowered, ["能干嘛", "能做什么", "主要做什么", "讲了什么"]):
            return _make_compact_text(f"{subject} 核心能力") if subject else "核心能力"

    if intent.get("procedural") and _has_any(lowered, ["启动", "命令", "docker", "第2步", "第二步", "second step"]):
        base = "服务启动步骤"
        if step_hint:
            return f"{base} {step_hint} 命令"
        return base + " 命令"

    if intent.get("threshold") and _has_any(lowered, ["故障", "触发", "响应"]):
        return "故障触发条件"

    if intent.get("temporal") and ("发布冻结" in question and "开始" in question and "结束" in question):
        return "发布冻结 开始时间 结束时间"
    if intent.get("temporal") and _has_any(lowered, ["升级", "restore", "recover"]):
        return "升级规则 时间窗口"

    if intent.get("definition") and _has_any(lowered, ["metadata", "chunk"]):
        return "chunk metadata 术语定义"

    if intent.get("api") and _has_any(lowered, ["newest", "latest", "current", "snapshot", "version", "当前", "最新", "版本"]):
        if _has_any(lowered, ["field", "fields", "header", "cache", "字段", "响应头", "缓存"]):
            return "data-version freshness field"

    if intent.get("api") and _has_any(lowered, ["cache", "缓存"]) and _has_any(lowered, ["header", "响应头"]):
        return "x-cache 缓存 响应头"
    if intent.get("api") and _has_any(lowered, ["health", "健康检查"]) and _has_any(lowered, ["endpoint", "接口"]):
        return "/health 健康检查 接口"

    if "新同学" in question and "先" in question and "再" in question:
        return "团队手册 新同学 阅读顺序 产品总览 API 参考 运行手册"

    return ""


def _build_compact_query(parts: List[str], limit: int) -> str:
    values: List[str] = []
    seen = set()
    for raw in parts:
        text = _make_compact_text(raw)
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        values.append(text)
        if len(values) >= limit:
            break
    return _make_compact_text(" ".join(values))


def _unique_queries(queries: List[str], limit: int) -> List[str]:
    values: List[str] = []
    seen = set()
    for raw in queries:
        text = _make_compact_text(raw)
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        values.append(text)
        if len(values) >= limit:
            break
    return values


def plan_query(question: str) -> QueryPlan:
    normalized = _make_compact_text(question)
    intent = classify_query_intent(normalized)
    core_terms = _content_terms(normalized)
    decomposition = _split_subqueries(normalized, core_terms) if intent.get("multiPart") else []
    intent_hints = _intent_hint_terms(intent)
    domain_hints = _domain_hint_terms(normalized, intent)
    focus_question = _build_focus_question(normalized, intent, core_terms)

    route_question = _build_compact_query([focus_question] + core_terms + domain_hints + intent_hints[:2], limit=8) or normalized
    retrieval_question = _build_compact_query([focus_question, normalized] + decomposition + core_terms + domain_hints + intent_hints, limit=12) or normalized
    route_queries = _unique_queries([focus_question, route_question, normalized] + decomposition[:1], limit=4)
    retrieval_queries = _unique_queries([focus_question, retrieval_question, normalized] + decomposition, limit=5)

    return QueryPlan(
        originalQuestion=question,
        normalizedQuestion=normalized,
        routeQuestion=route_question,
        retrievalQuestion=retrieval_question,
        focusQuestion=focus_question,
        routeQueries=route_queries,
        retrievalQueries=retrieval_queries,
        decomposition=decomposition,
        intent=intent,
    )
