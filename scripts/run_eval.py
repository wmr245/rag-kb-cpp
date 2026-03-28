#!/usr/bin/env python3
import argparse
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

from smoke_test import build_multipart_body


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUITE_DIR = ROOT / 'eval' / 'suites'
DEFAULT_REPORT_DIR = ROOT / 'eval' / 'reports'
DEFAULT_BASELINE_DIR = ROOT / 'eval' / 'baselines'


def http_json(method: str, url: str, timeout_sec: int, data: bytes | None = None, headers: dict | None = None):
    request = urllib.request.Request(url=url, data=data, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)

    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            payload = response.read().decode('utf-8')
            return response.status, json.loads(payload), dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'HTTP {exc.code} for {url}: {payload}') from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f'Request failed for {url}: {exc}') from exc


def wait_for_task(base_url: str, task_id: str, timeout_sec: int, interval_sec: float, request_timeout_sec: int) -> dict:
    deadline = time.time() + timeout_sec
    task_url = f"{base_url}/tasks/{task_id}"

    while time.time() < deadline:
        _, payload, _ = http_json('GET', task_url, timeout_sec=request_timeout_sec)
        status = payload.get('status')
        progress = payload.get('progress')
        print(f"[task] status={status} progress={progress}")

        if status == 'success':
            return payload
        if status == 'failed':
            raise RuntimeError(f"ingest failed: {payload.get('error')}")

        time.sleep(interval_sec)

    raise TimeoutError(f'task {task_id} did not finish within {timeout_sec}s')


def load_suite(suite_name: str) -> Dict[str, Any]:
    suite_path = DEFAULT_SUITE_DIR / f'{suite_name}.json'
    if not suite_path.exists():
        raise FileNotFoundError(f'suite not found: {suite_path}')
    return json.loads(suite_path.read_text(encoding='utf-8-sig'))


def load_report(report_path: str | Path) -> Dict[str, Any]:
    path = Path(report_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f'report not found: {path}')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def _normalize_match_text(text: str) -> str:
    normalized = ' '.join((text or '').lower().split())
    for token in [' ', '，', ',', '。', '.', '：', ':', '；', ';', '？', '?', '！', '!', '、', '（', '）', '(', ')']:
        normalized = normalized.replace(token, '')
    return normalized


def contains_all(text: str, phrases: Iterable[str]) -> bool:
    normalized = _normalize_match_text(text)
    return all(_normalize_match_text(phrase) in normalized for phrase in phrases)


def contains_any(text: str, phrases: Iterable[str]) -> bool:
    normalized = _normalize_match_text(text)
    return any(_normalize_match_text(phrase) in normalized for phrase in phrases)


def match_fields(candidate: Dict[str, Any], matcher: Dict[str, Any]) -> bool:
    for key, expected in matcher.items():
        actual = candidate.get(key)
        if actual is None:
            return False
        if str(expected).lower() not in str(actual).lower():
            return False
    return True


def any_match(candidates: List[Dict[str, Any]], matchers: List[Dict[str, Any]]) -> bool:
    if not matchers:
        return True
    return any(match_fields(candidate, matcher) for candidate in candidates for matcher in matchers)


def item_candidate(item: Dict[str, Any]) -> Dict[str, Any]:
    citation = item.get('citation') or {}
    return {
        'title': citation.get('title', ''),
        'heading': item.get('heading', ''),
        'sectionPath': item.get('sectionPath', ''),
        'chunkType': item.get('chunkType', ''),
        'sourceType': item.get('sourceType', ''),
        'score': item.get('score'),
        'localScore': item.get('localScore'),
        'rerankScore': item.get('rerankScore'),
        'blendedScore': item.get('blendedScore'),
        'text': item.get('text', ''),
    }


def citation_candidate(citation: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'title': citation.get('title', ''),
        'snippet': citation.get('snippet', ''),
    }


def _extract_active_intents(intent: Dict[str, Any]) -> List[str]:
    return [key for key, enabled in (intent or {}).items() if enabled]


def _decision_summary_lines(decision_summary: Dict[str, Any]) -> List[str]:
    if not decision_summary:
        return []

    lines: List[str] = []
    headline = decision_summary.get('headline')
    if headline:
        lines.append(str(headline))

    for section_name in ['planner', 'routing', 'retrieval', 'answerability', 'citation']:
        section = decision_summary.get(section_name) or {}
        summary = section.get('summary')
        if summary:
            lines.append(f"{section_name}: {summary}")
    return lines


def evaluate_case(case: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    expectations = case.get('expectations') or {}
    answer = payload.get('answer', '')
    items = payload.get('items') or []
    citations = payload.get('citations') or []
    query_debug = payload.get('queryDebug') or {}
    decision_summary = query_debug.get('decisionSummary') or {}

    answer_all_ok = contains_all(answer, expectations.get('answerContainsAll', []))
    answer_any_required = expectations.get('answerContainsAny', [])
    answer_any_ok = True if not answer_any_required else contains_any(answer, answer_any_required)

    item_candidates = [item_candidate(item) for item in items]
    citation_candidates = [citation_candidate(citation) for citation in citations]

    retrieval_ok = any_match(item_candidates, expectations.get('retrievalAny', []))
    top_item_ok = any_match(item_candidates[:1], expectations.get('topItemAny', []))
    citation_ok = any_match(citation_candidates, expectations.get('citationAny', []))

    intent = query_debug.get('intent') or {}
    required_intents = expectations.get('intentContainsAll', [])
    forbidden_intents = expectations.get('intentContainsNone', [])
    intent_all_ok = all(bool(intent.get(name)) for name in required_intents)
    intent_none_ok = all(not bool(intent.get(name)) for name in forbidden_intents)

    expect_refused = expectations.get('expectRefused')
    refusal_ok = True if expect_refused is None else bool(payload.get('refused')) == bool(expect_refused)

    expected_citation_count = expectations.get('citationCount')
    citation_count_ok = True if expected_citation_count is None else len(citations) == int(expected_citation_count)

    passed = answer_all_ok and answer_any_ok and retrieval_ok and top_item_ok and citation_ok and intent_all_ok and intent_none_ok and refusal_ok and citation_count_ok
    return {
        'passed': passed,
        'answerAllOk': answer_all_ok,
        'answerAnyOk': answer_any_ok,
        'retrievalOk': retrieval_ok,
        'topItemOk': top_item_ok,
        'citationOk': citation_ok,
        'intentAllOk': intent_all_ok,
        'intentNoneOk': intent_none_ok,
        'refusalOk': refusal_ok,
        'citationCountOk': citation_count_ok,
        'hasRefusalExpectation': expect_refused is not None,
        'latencyMs': payload.get('latencyMs'),
        'answer': answer,
        'refused': bool(payload.get('refused')),
        'refusalReason': payload.get('refusalReason'),
        'evidenceScore': payload.get('evidenceScore'),
        'topItems': item_candidates[:3],
        'citations': citation_candidates,
        'resolvedDocScope': payload.get('resolvedDocScope', []),
        'routedDocs': payload.get('routedDocs', []),
        'queryDebug': {
            'plannerVersion': query_debug.get('plannerVersion'),
            'normalizedQuestion': query_debug.get('normalizedQuestion'),
            'focusQuestion': query_debug.get('focusQuestion'),
            'decomposition': query_debug.get('decomposition', []),
            'intent': query_debug.get('intent', {}),
            'routeQueries': query_debug.get('routeQueries', []),
            'retrievalQueries': query_debug.get('retrievalQueries', []),
            'routeRuns': query_debug.get('routeRuns', []),
            'retrievalRuns': query_debug.get('retrievalRuns', []),
            'attributionHints': query_debug.get('attributionHints', []),
            'queryVectorCount': query_debug.get('queryVectorCount', 0),
            'rerank': query_debug.get('rerank'),
            'timingsMs': query_debug.get('timingsMs', {}),
            'decisionSummary': decision_summary,
        },
        'decisionSummary': decision_summary,
        'decisionSummaryText': _decision_summary_lines(decision_summary),
    }


def upload_documents(base_url: str, documents: List[Dict[str, Any]], timeout: int, poll_interval: float, request_timeout_sec: int) -> Dict[str, Dict[str, Any]]:
    uploaded: Dict[str, Dict[str, Any]] = {}
    run_owner_suffix = uuid.uuid4().hex[:8]

    for doc in documents:
        file_path = ROOT / doc['path']
        if not file_path.exists():
            raise FileNotFoundError(f'document not found: {file_path}')

        boundary = f'----rageval{uuid.uuid4().hex}'
        body = build_multipart_body(
            file_path=file_path,
            title=doc['title'],
            owner=f"{doc['owner']}-{run_owner_suffix}",
            boundary=boundary,
        )
        headers = {'Content-Type': f'multipart/form-data; boundary={boundary}'}
        _, upload_payload, _ = http_json('POST', f'{base_url}/docs/upload', timeout_sec=request_timeout_sec, data=body, headers=headers)
        task_id = upload_payload['taskId']
        doc_id = upload_payload['docId']
        wait_for_task(base_url, task_id, timeout, poll_interval, request_timeout_sec)

        uploaded[doc['key']] = {
            'docId': doc_id,
            'taskId': task_id,
            'title': doc['title'],
            'path': doc['path'],
        }
        print(f"[upload] key={doc['key']} docId={doc_id} title={doc['title']}")

    return uploaded


def run_case(base_url: str, case: Dict[str, Any], uploaded: Dict[str, Dict[str, Any]], default_scope: List[int], request_timeout_sec: int) -> Dict[str, Any]:
    scope_keys = case.get('docScope') or []
    use_default_scope = case.get('useDefaultScope', True)
    if scope_keys:
        doc_scope = [uploaded[key]['docId'] for key in scope_keys]
    elif use_default_scope:
        doc_scope = list(default_scope)
    else:
        doc_scope = []

    query_body = json.dumps(
        {
            'question': case['question'],
            'topK': case.get('topK', 3),
            'docScope': doc_scope,
        },
        ensure_ascii=False,
    ).encode('utf-8')
    _, payload, response_headers = http_json(
        'POST',
        f'{base_url}/rag/query',
        timeout_sec=request_timeout_sec,
        data=query_body,
        headers={'Content-Type': 'application/json'},
    )

    evaluation = evaluate_case(case, payload)
    evaluation['xCache'] = response_headers.get('x-cache', '')
    evaluation['xTraceId'] = response_headers.get('x-trace-id', '')
    evaluation['docScope'] = doc_scope
    return evaluation


def summarize_tag_stats(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {'total': 0, 'passed': 0})
    for result in results:
        for tag in result.get('tags', []):
            stats[tag]['total'] += 1
            if result['passed']:
                stats[tag]['passed'] += 1
    return dict(sorted(stats.items()))


def summarize_debug_stats(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    planner_versions: Dict[str, int] = defaultdict(int)
    intent_counts: Dict[str, int] = defaultdict(int)
    routing_modes: Dict[str, int] = defaultdict(int)
    refusal_reasons: Dict[str, int] = defaultdict(int)
    decomposition_cases = 0
    auto_routed_cases = 0
    refused_cases = 0
    cases_with_decision_summary = 0
    rerank_enabled_cases = 0
    rerank_applied_cases = 0
    rerank_fallback_cases = 0
    rerank_reordered_cases = 0
    attribution_hint_cases = 0
    rerank_providers: Dict[str, int] = defaultdict(int)

    for result in results:
        query_debug = result.get('queryDebug') or {}
        version = query_debug.get('plannerVersion') or 'unknown'
        planner_versions[version] += 1

        for intent_name in _extract_active_intents(query_debug.get('intent', {})):
            intent_counts[intent_name] += 1

        if query_debug.get('decomposition'):
            decomposition_cases += 1
        if result.get('routedDocs'):
            auto_routed_cases += 1
            routing_modes['auto'] += 1
        elif result.get('docScope'):
            routing_modes['explicit_scope'] += 1
        else:
            routing_modes['global_search'] += 1

        if result.get('refused'):
            refused_cases += 1
            refusal_reasons[result.get('refusalReason') or 'unknown'] += 1

        if result.get('decisionSummary'):
            cases_with_decision_summary += 1

        rerank = query_debug.get('rerank') or {}
        if rerank.get('enabled'):
            rerank_enabled_cases += 1
            provider = rerank.get('provider') or 'generic'
            rerank_providers[provider] += 1
        if int(rerank.get('appliedCount') or 0) > 0:
            rerank_applied_cases += 1
        if rerank.get('fallback'):
            rerank_fallback_cases += 1
        if rerank.get('orderingChanged'):
            rerank_reordered_cases += 1
        if query_debug.get('attributionHints'):
            attribution_hint_cases += 1

    return {
        'plannerVersions': dict(sorted(planner_versions.items())),
        'intentCounts': dict(sorted(intent_counts.items())),
        'routingModes': dict(sorted(routing_modes.items())),
        'refusalReasons': dict(sorted(refusal_reasons.items())),
        'casesWithDecomposition': decomposition_cases,
        'casesWithAutoRouting': auto_routed_cases,
        'refusedCases': refused_cases,
        'casesWithDecisionSummary': cases_with_decision_summary,
        'casesWithRerankEnabled': rerank_enabled_cases,
        'casesWithRerankApplied': rerank_applied_cases,
        'casesWithRerankFallback': rerank_fallback_cases,
        'casesWithRerankReorderedTopItems': rerank_reordered_cases,
        'casesWithAttributionHints': attribution_hint_cases,
        'rerankProviders': dict(sorted(rerank_providers.items())),
    }


def default_report_path(suite_id: str) -> Path:
    DEFAULT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime('%Y%m%d-%H%M%S')
    return DEFAULT_REPORT_DIR / f'{suite_id}-{timestamp}.json'


def baseline_report_path(suite_id: str) -> Path:
    DEFAULT_BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_BASELINE_DIR / f'{suite_id}.json'


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _result_map(report: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {result['id']: result for result in report.get('results', [])}


def resolve_compare_target(compare_to: str | None, compare_to_baseline: bool, suite_id: str) -> Path | None:
    if compare_to and compare_to_baseline:
        raise ValueError('use either --compare-to or --compare-to-baseline, not both')
    if compare_to:
        return Path(compare_to).expanduser().resolve()
    if compare_to_baseline:
        path = baseline_report_path(suite_id)
        if not path.exists():
            raise FileNotFoundError(f'baseline report not found: {path}')
        return path
    return None


def _preview_list(values: List[str], limit: int = 3) -> str:
    cleaned = [str(value) for value in values if value]
    if not cleaned:
        return 'none'
    return ' | '.join(cleaned[:limit])


def _top_item_labels(result: Dict[str, Any]) -> List[str]:
    labels: List[str] = []
    for item in (result.get('topItems') or [])[:3]:
        title = item.get('title') or ''
        anchor = item.get('heading') or item.get('sectionPath') or item.get('chunkType') or 'chunk'
        labels.append(f"{title}/{anchor}")
    return labels


def _routed_doc_labels(result: Dict[str, Any]) -> List[str]:
    labels: List[str] = []
    for row in (result.get('routedDocs') or [])[:3]:
        title = row.get('title') or ''
        reason = row.get('reason') or ''
        labels.append(f"{title}{(':' + reason) if reason else ''}")
    return labels


def _route_run_labels(result: Dict[str, Any]) -> List[str]:
    labels: List[str] = []
    for run in (result.get('queryDebug') or {}).get('routeRuns', [])[:2]:
        query = run.get('query') or ''
        docs = []
        for row in (run.get('topDocs') or [])[:2]:
            docs.append(f"{row.get('title') or ''}:{row.get('reason') or ''}".rstrip(':'))
        labels.append(f"{query}=>{_preview_list(docs, 2)}")
    return labels


def _retrieval_run_labels(result: Dict[str, Any]) -> List[str]:
    labels: List[str] = []
    for run in (result.get('queryDebug') or {}).get('retrievalRuns', [])[:2]:
        query = run.get('query') or ''
        local_items = []
        for row in (run.get('localTopItems') or [])[:1]:
            local_items.append(f"{row.get('title') or ''}/{row.get('heading') or row.get('sectionPath') or 'chunk'}")
        final_items = []
        for row in (run.get('finalTopItems') or [])[:1]:
            final_items.append(f"{row.get('title') or ''}/{row.get('heading') or row.get('sectionPath') or 'chunk'}")
        labels.append(f"{query}=>local:{_preview_list(local_items, 1)}=>final:{_preview_list(final_items, 1)}")
    return labels


def _citation_labels(result: Dict[str, Any]) -> List[str]:
    labels: List[str] = []
    for citation in (result.get('citations') or [])[:3]:
        title = citation.get('title') or ''
        snippet = citation.get('snippet') or ''
        snippet = snippet[:48].strip()
        labels.append(f"{title}{(':' + snippet) if snippet else ''}")
    return labels


def _append_reason(details: Dict[str, List[str]], area: str, message: str) -> None:
    bucket = details.setdefault(area, [])
    if message not in bucket:
        bucket.append(message)


def _analyze_case_difference(current: Dict[str, Any], baseline: Dict[str, Any]) -> Dict[str, Any]:
    details: Dict[str, List[str]] = {}

    cur_debug = current.get('queryDebug') or {}
    base_debug = baseline.get('queryDebug') or {}

    cur_intents = sorted(_extract_active_intents(cur_debug.get('intent', {})))
    base_intents = sorted(_extract_active_intents(base_debug.get('intent', {})))
    if cur_intents != base_intents:
        _append_reason(details, 'planner', f"intent {base_intents or ['general']} -> {cur_intents or ['general']}")

    cur_focus = cur_debug.get('focusQuestion') or ''
    base_focus = base_debug.get('focusQuestion') or ''
    if cur_focus != base_focus:
        _append_reason(details, 'planner', f"focus {_preview_list([base_focus], 1)} -> {_preview_list([cur_focus], 1)}")

    cur_decomp = cur_debug.get('decomposition') or []
    base_decomp = base_debug.get('decomposition') or []
    if cur_decomp != base_decomp:
        _append_reason(details, 'planner', f"decomposition {_preview_list(base_decomp)} -> {_preview_list(cur_decomp)}")

    cur_route_queries = cur_debug.get('routeQueries') or []
    base_route_queries = base_debug.get('routeQueries') or []
    if cur_route_queries != base_route_queries:
        _append_reason(details, 'planner', f"routeQueries {_preview_list(base_route_queries, 2)} -> {_preview_list(cur_route_queries, 2)}")

    cur_retrieval_queries = cur_debug.get('retrievalQueries') or []
    base_retrieval_queries = base_debug.get('retrievalQueries') or []
    if cur_retrieval_queries != base_retrieval_queries:
        _append_reason(details, 'planner', f"retrievalQueries {_preview_list(base_retrieval_queries, 2)} -> {_preview_list(cur_retrieval_queries, 2)}")

    cur_rerank = cur_debug.get('rerank') or {}
    base_rerank = base_debug.get('rerank') or {}
    if bool(cur_rerank.get('enabled')) != bool(base_rerank.get('enabled')):
        _append_reason(details, 'rerank', f"enabled {bool(base_rerank.get('enabled'))} -> {bool(cur_rerank.get('enabled'))}")
    if (cur_rerank.get('provider') or '') != (base_rerank.get('provider') or ''):
        _append_reason(details, 'rerank', f"provider {_preview_list([base_rerank.get('provider') or 'none'], 1)} -> {_preview_list([cur_rerank.get('provider') or 'none'], 1)}")
    if (cur_rerank.get('model') or '') != (base_rerank.get('model') or ''):
        _append_reason(details, 'rerank', f"model {_preview_list([base_rerank.get('model') or 'none'], 1)} -> {_preview_list([cur_rerank.get('model') or 'none'], 1)}")
    if bool(cur_rerank.get('fallback')) != bool(base_rerank.get('fallback')):
        _append_reason(details, 'rerank', f"fallback {bool(base_rerank.get('fallback'))} -> {bool(cur_rerank.get('fallback'))}")
    if int(cur_rerank.get('appliedCount') or 0) != int(base_rerank.get('appliedCount') or 0):
        _append_reason(details, 'rerank', f"appliedCount {int(base_rerank.get('appliedCount') or 0)} -> {int(cur_rerank.get('appliedCount') or 0)}")

    cur_routed = _routed_doc_labels(current)
    base_routed = _routed_doc_labels(baseline)
    if cur_routed != base_routed:
        _append_reason(details, 'routing', f"routedDocs {_preview_list(base_routed)} -> {_preview_list(cur_routed)}")

    cur_route_runs = _route_run_labels(current)
    base_route_runs = _route_run_labels(baseline)
    if cur_route_runs != base_route_runs:
        _append_reason(details, 'routing', f"routeRuns {_preview_list(base_route_runs, 2)} -> {_preview_list(cur_route_runs, 2)}")

    cur_retrieval_ok = bool(current.get('retrievalOk'))
    base_retrieval_ok = bool(baseline.get('retrievalOk'))
    if cur_retrieval_ok != base_retrieval_ok:
        _append_reason(details, 'retrieval', f"retrievalOk {base_retrieval_ok} -> {cur_retrieval_ok}")

    cur_items = _top_item_labels(current)
    base_items = _top_item_labels(baseline)
    if cur_items != base_items:
        _append_reason(details, 'retrieval', f"topItems {_preview_list(base_items)} -> {_preview_list(cur_items)}")

    cur_retrieval_runs = _retrieval_run_labels(current)
    base_retrieval_runs = _retrieval_run_labels(baseline)
    if cur_retrieval_runs != base_retrieval_runs:
        _append_reason(details, 'retrieval', f"retrievalRuns {_preview_list(base_retrieval_runs, 2)} -> {_preview_list(cur_retrieval_runs, 2)}")

    cur_refused = bool(current.get('refused'))
    base_refused = bool(baseline.get('refused'))
    if cur_refused != base_refused:
        _append_reason(details, 'answerability', f"refused {base_refused} -> {cur_refused}")

    cur_reason = current.get('refusalReason') or ''
    base_reason = baseline.get('refusalReason') or ''
    if cur_reason != base_reason:
        _append_reason(details, 'answerability', f"refusalReason {_preview_list([base_reason], 1)} -> {_preview_list([cur_reason], 1)}")

    cur_evidence = current.get('evidenceScore')
    base_evidence = baseline.get('evidenceScore')
    if cur_evidence is not None or base_evidence is not None:
        cur_value = float(cur_evidence or 0.0)
        base_value = float(base_evidence or 0.0)
        if abs(cur_value - base_value) >= 0.03:
            _append_reason(details, 'answerability', f"evidenceScore {base_value:.3f} -> {cur_value:.3f}")

    cur_refusal_ok = bool(current.get('refusalOk', True))
    base_refusal_ok = bool(baseline.get('refusalOk', True))
    if cur_refusal_ok != base_refusal_ok:
        _append_reason(details, 'answerability', f"refusalOk {base_refusal_ok} -> {cur_refusal_ok}")

    cur_top_item_ok = bool(current.get('topItemOk'))
    base_top_item_ok = bool(baseline.get('topItemOk'))
    if cur_top_item_ok != base_top_item_ok:
        _append_reason(details, 'retrieval', f"topItemOk {base_top_item_ok} -> {cur_top_item_ok}")

    cur_citation_ok = bool(current.get('citationOk'))
    base_citation_ok = bool(baseline.get('citationOk'))
    if cur_citation_ok != base_citation_ok:
        _append_reason(details, 'citation', f"citationOk {base_citation_ok} -> {cur_citation_ok}")

    cur_citations = _citation_labels(current)
    base_citations = _citation_labels(baseline)
    if cur_citations != base_citations:
        _append_reason(details, 'citation', f"citations {_preview_list(base_citations)} -> {_preview_list(cur_citations)}")

    if not details:
        _append_reason(details, 'result', 'pass/fail changed without a more specific observable delta')

    areas = list(details.keys())
    summary_parts = [f"{area}: {messages[0]}" for area, messages in details.items()]
    return {
        'areas': areas,
        'summary': ' ; '.join(summary_parts[:3]),
        'details': details,
    }


def _reason_bucket_counts(cases: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for case in cases:
        for area in case.get('reasonAreas', []):
            counts[area] += 1
    return dict(sorted(counts.items()))


def promote_baseline(report_path: Path, suite_id: str) -> Path:
    target = baseline_report_path(suite_id)
    shutil.copyfile(report_path, target)
    return target


def build_comparison(current: Dict[str, Any], baseline: Dict[str, Any]) -> Dict[str, Any]:
    current_suite = current.get('suiteId')
    baseline_suite = baseline.get('suiteId')
    if current_suite != baseline_suite:
        raise ValueError(f'suite mismatch: current={current_suite} baseline={baseline_suite}')

    current_results = _result_map(current)
    baseline_results = _result_map(baseline)
    all_case_ids = sorted(set(current_results) | set(baseline_results))

    regressions = []
    improvements = []
    unchanged = []

    for case_id in all_case_ids:
        cur = current_results.get(case_id)
        base = baseline_results.get(case_id)
        if cur is None or base is None:
            changed = {
                'id': case_id,
                'status': 'added' if base is None else 'removed',
                'currentPassed': None if cur is None else bool(cur.get('passed')),
                'baselinePassed': None if base is None else bool(base.get('passed')),
            }
            if base is None:
                improvements.append(changed)
            else:
                regressions.append(changed)
            continue

        cur_passed = bool(cur.get('passed'))
        base_passed = bool(base.get('passed'))
        delta = _safe_int(cur.get('latencyMs')) - _safe_int(base.get('latencyMs'))
        reason_analysis = _analyze_case_difference(cur, base)
        changed = {
            'id': case_id,
            'question': cur.get('question') or base.get('question'),
            'currentPassed': cur_passed,
            'baselinePassed': base_passed,
            'currentLatencyMs': _safe_int(cur.get('latencyMs')),
            'baselineLatencyMs': _safe_int(base.get('latencyMs')),
            'latencyDeltaMs': delta,
            'currentChecks': {
                'answerAllOk': bool(cur.get('answerAllOk')),
                'answerAnyOk': bool(cur.get('answerAnyOk')),
                'retrievalOk': bool(cur.get('retrievalOk')),
                'topItemOk': bool(cur.get('topItemOk')),
                'citationOk': bool(cur.get('citationOk')),
                'intentAllOk': bool(cur.get('intentAllOk', True)),
                'intentNoneOk': bool(cur.get('intentNoneOk', True)),
                'refusalOk': bool(cur.get('refusalOk', True)),
            },
            'baselineChecks': {
                'answerAllOk': bool(base.get('answerAllOk')),
                'answerAnyOk': bool(base.get('answerAnyOk')),
                'retrievalOk': bool(base.get('retrievalOk')),
                'topItemOk': bool(base.get('topItemOk')),
                'citationOk': bool(base.get('citationOk')),
                'intentAllOk': bool(base.get('intentAllOk', True)),
                'intentNoneOk': bool(base.get('intentNoneOk', True)),
                'refusalOk': bool(base.get('refusalOk', True)),
            },
            'reasonAreas': reason_analysis['areas'],
            'reasonSummary': reason_analysis['summary'],
            'reasonDetails': reason_analysis['details'],
        }

        if base_passed and not cur_passed:
            regressions.append({'status': 'pass_to_fail', **changed})
        elif (not base_passed) and cur_passed:
            improvements.append({'status': 'fail_to_pass', **changed})
        elif delta != 0:
            unchanged.append({'status': 'latency_change', **changed})
        else:
            unchanged.append({'status': 'same', **changed})

    current_totals = current.get('totals', {})
    baseline_totals = baseline.get('totals', {})
    metrics = ['passed', 'answerAll', 'answerAny', 'retrieval', 'citation', 'refusalPassed']
    totals_delta = {
        metric: _safe_int(current_totals.get(metric)) - _safe_int(baseline_totals.get(metric))
        for metric in metrics
    }

    all_tags = sorted(set(current.get('tagStats', {})) | set(baseline.get('tagStats', {})))
    tag_delta = {}
    for tag in all_tags:
        cur = current.get('tagStats', {}).get(tag, {'total': 0, 'passed': 0})
        base = baseline.get('tagStats', {}).get(tag, {'total': 0, 'passed': 0})
        tag_delta[tag] = {
            'current': {'passed': _safe_int(cur.get('passed')), 'total': _safe_int(cur.get('total'))},
            'baseline': {'passed': _safe_int(base.get('passed')), 'total': _safe_int(base.get('total'))},
            'passedDelta': _safe_int(cur.get('passed')) - _safe_int(base.get('passed')),
            'totalDelta': _safe_int(cur.get('total')) - _safe_int(base.get('total')),
        }

    changed_cases = [case for case in unchanged if case['status'] == 'latency_change']

    return {
        'suiteId': current_suite,
        'baselineGeneratedAt': baseline.get('generatedAt'),
        'currentGeneratedAt': current.get('generatedAt'),
        'baselinePath': str(Path(baseline.get('_reportPath', ''))),
        'currentPath': str(Path(current.get('_reportPath', ''))),
        'totalsDelta': totals_delta,
        'regressionCount': len(regressions),
        'improvementCount': len(improvements),
        'regressions': regressions,
        'improvements': improvements,
        'changedCases': changed_cases,
        'tagDelta': tag_delta,
        'regressionReasonBuckets': _reason_bucket_counts(regressions),
        'improvementReasonBuckets': _reason_bucket_counts(improvements),
        'changedReasonBuckets': _reason_bucket_counts(changed_cases),
    }


def format_comparison_lines(comparison: Dict[str, Any]) -> List[str]:
    lines = []
    totals_delta = comparison['totalsDelta']
    lines.append('[compare] totals ' + ' '.join(f"{metric}={delta:+d}" for metric, delta in totals_delta.items()))
    lines.append(f"[compare] regressions={comparison['regressionCount']} improvements={comparison['improvementCount']} changed={len(comparison['changedCases'])}")

    if comparison['regressionReasonBuckets']:
        lines.append('[compare] regressionReasons ' + json.dumps(comparison['regressionReasonBuckets'], ensure_ascii=False))
    if comparison['improvementReasonBuckets']:
        lines.append('[compare] improvementReasons ' + json.dumps(comparison['improvementReasonBuckets'], ensure_ascii=False))

    if comparison['regressions']:
        lines.append('[compare] regressions:')
        for case in comparison['regressions'][:10]:
            lines.append(
                f"  - {case['id']} status={case['status']} baseline={case.get('baselinePassed')} current={case.get('currentPassed')} "
                f"latencyDeltaMs={case.get('latencyDeltaMs', 0):+d} areas={','.join(case.get('reasonAreas', [])) or 'none'}"
            )
            if case.get('reasonSummary'):
                lines.append(f"    reason: {case['reasonSummary']}")

    if comparison['improvements']:
        lines.append('[compare] improvements:')
        for case in comparison['improvements'][:10]:
            lines.append(
                f"  - {case['id']} status={case['status']} baseline={case.get('baselinePassed')} current={case.get('currentPassed')} "
                f"latencyDeltaMs={case.get('latencyDeltaMs', 0):+d} areas={','.join(case.get('reasonAreas', [])) or 'none'}"
            )
            if case.get('reasonSummary'):
                lines.append(f"    reason: {case['reasonSummary']}")

    if comparison['changedReasonBuckets']:
        lines.append('[compare] changeReasons ' + json.dumps(comparison['changedReasonBuckets'], ensure_ascii=False))

    interesting_tags = [(tag, delta) for tag, delta in comparison['tagDelta'].items() if delta['passedDelta'] != 0 or delta['totalDelta'] != 0]
    if interesting_tags:
        lines.append('[compare] tags:')
        for tag, delta in interesting_tags:
            lines.append(f"  - {tag}: passedDelta={delta['passedDelta']:+d} totalDelta={delta['totalDelta']:+d} baseline={delta['baseline']['passed']}/{delta['baseline']['total']} current={delta['current']['passed']}/{delta['current']['total']}")

    return lines


def print_comparison(comparison: Dict[str, Any]) -> None:
    for line in format_comparison_lines(comparison):
        print(line)


def write_report(report: Dict[str, Any], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description='Run layered RAG evaluation suites')
    parser.add_argument('--base-url', default='http://localhost:8080')
    parser.add_argument('--suite', default='small', choices=['small', 'medium', 'large', 'longlite', 'xlarge', 'query', 'rerank'])
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--poll-interval', type=float, default=2.0)
    parser.add_argument('--report-out', help='optional path for JSON report output')
    parser.add_argument('--request-timeout', type=int, default=60, help='per-request timeout in seconds')
    parser.add_argument('--max-cases', type=int, default=0, help='only run the first N cases, 0 means all')
    parser.add_argument('--compare-to', help='optional baseline report path for compare mode')
    parser.add_argument('--compare-to-baseline', action='store_true', help='compare against eval/baselines/<suite>.json')
    parser.add_argument('--fail-on-regression', action='store_true', help='return non-zero when compare mode finds regressions')
    parser.add_argument('--promote-baseline', action='store_true', help='promote the current report to eval/baselines/<suite>.json after a clean run')
    args = parser.parse_args()

    suite = load_suite(args.suite)
    cases = suite['cases'][: args.max_cases] if args.max_cases > 0 else suite['cases']
    base_url = args.base_url.rstrip('/')

    print(f"[suite] id={suite['suiteId']} docs={len(suite['documents'])} cases={len(cases)}")
    print(f"[suite] description={suite['description']}")

    uploaded = upload_documents(
        base_url=base_url,
        documents=suite['documents'],
        timeout=args.timeout,
        poll_interval=args.poll_interval,
        request_timeout_sec=args.request_timeout,
    )
    default_scope = [uploaded[doc['key']]['docId'] for doc in suite['documents']]

    results: List[Dict[str, Any]] = []
    answer_all_pass = 0
    answer_any_pass = 0
    retrieval_pass = 0
    citation_pass = 0
    refusal_total_checks = 0
    refusal_pass = 0

    for index, case in enumerate(cases, start=1):
        evaluation = run_case(base_url, case, uploaded, default_scope, args.request_timeout)
        status = 'PASS' if evaluation['passed'] else 'FAIL'
        print(
            f"[case {index:02d}] {status} id={case['id']} latencyMs={evaluation['latencyMs']} "
            f"answerAll={evaluation['answerAllOk']} answerAny={evaluation['answerAnyOk']} "
            f"retrieval={evaluation['retrievalOk']} citation={evaluation['citationOk']}"
        )
        if not evaluation['passed']:
            print(f"  question: {case['question']}")
            print(f"  answer: {evaluation['answer']}")
            print(f"  refused: {evaluation['refused']} reason={evaluation['refusalReason']} evidenceScore={evaluation['evidenceScore']}")
            print(f"  topItems: {json.dumps(evaluation['topItems'], ensure_ascii=False)}")
            print(f"  citations: {json.dumps(evaluation['citations'], ensure_ascii=False)}")
            print(f"  routedDocs: {json.dumps(evaluation['routedDocs'], ensure_ascii=False)}")
            print(f"  decisionSummary: {json.dumps(evaluation['decisionSummary'], ensure_ascii=False)}")
            print(f"  queryDebug: {json.dumps(evaluation['queryDebug'], ensure_ascii=False)}")

        answer_all_pass += int(evaluation['answerAllOk'])
        answer_any_pass += int(evaluation['answerAnyOk'])
        retrieval_pass += int(evaluation['retrievalOk'])
        citation_pass += int(evaluation['citationOk'])
        refusal_total_checks += int(evaluation['hasRefusalExpectation'])
        refusal_pass += int(evaluation['refusalOk']) if evaluation['hasRefusalExpectation'] else 0

        results.append(
            {
                'id': case['id'],
                'question': case['question'],
                'tags': case.get('tags', []),
                **evaluation,
            }
        )

    total_cases = len(results)
    passed_cases = sum(1 for result in results if result['passed'])
    tag_stats = summarize_tag_stats(results)
    debug_stats = summarize_debug_stats(results)

    print(f"[summary] passed={passed_cases}/{total_cases}")
    print(f"[summary] answerAll={answer_all_pass}/{total_cases} answerAny={answer_any_pass}/{total_cases} retrieval={retrieval_pass}/{total_cases} citation={citation_pass}/{total_cases}")
    if refusal_total_checks:
        print(f"[summary] refusal={refusal_pass}/{refusal_total_checks}")
    print(
        f"[summary] debug plannerVersions={json.dumps(debug_stats['plannerVersions'], ensure_ascii=False)} "
        f"intents={json.dumps(debug_stats['intentCounts'], ensure_ascii=False)} "
        f"routingModes={json.dumps(debug_stats['routingModes'], ensure_ascii=False)} "
        f"decompositionCases={debug_stats['casesWithDecomposition']} "
        f"autoRoutingCases={debug_stats['casesWithAutoRouting']} "
        f"refusedCases={debug_stats['refusedCases']} "
        f"decisionSummaryCases={debug_stats['casesWithDecisionSummary']}"
    )
    if tag_stats:
        print('[summary] tags:')
        for tag, stat in tag_stats.items():
            print(f"  - {tag}: {stat['passed']}/{stat['total']}")

    report = {
        'suiteId': suite['suiteId'],
        'description': suite['description'],
        'baseUrl': base_url,
        'generatedAt': time.strftime('%Y-%m-%d %H:%M:%S'),
        'documents': uploaded,
        'totals': {
            'cases': total_cases,
            'passed': passed_cases,
            'answerAll': answer_all_pass,
            'answerAny': answer_any_pass,
            'retrieval': retrieval_pass,
            'citation': citation_pass,
            'refusalChecks': refusal_total_checks,
            'refusalPassed': refusal_pass,
        },
        'tagStats': tag_stats,
        'debugSummary': debug_stats,
        'results': results,
    }

    report_path = Path(args.report_out).expanduser().resolve() if args.report_out else default_report_path(suite['suiteId'])
    report['_reportPath'] = str(report_path)

    compare_target = resolve_compare_target(args.compare_to, args.compare_to_baseline, suite['suiteId'])
    if compare_target:
        baseline_report = load_report(compare_target)
        baseline_report['_reportPath'] = str(compare_target)
        comparison = build_comparison(report, baseline_report)
        report['comparison'] = comparison
        print_comparison(comparison)

    write_report(report, report_path)
    print(f'[report] {report_path}')

    if args.promote_baseline:
        regression_count = report.get('comparison', {}).get('regressionCount', 0)
        if passed_cases == total_cases and regression_count == 0:
            promoted_path = promote_baseline(report_path, suite['suiteId'])
            print(f'[baseline] promoted {promoted_path}')
        else:
            print(f'[baseline] skipped due to failed cases or regressions (passed={passed_cases}/{total_cases}, regressions={regression_count})')

    exit_code = 0 if passed_cases == total_cases else 1
    if args.fail_on_regression and report.get('comparison', {}).get('regressionCount', 0) > 0:
        exit_code = 1
    return exit_code


if __name__ == '__main__':
    sys.exit(main())

