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
    return json.loads(suite_path.read_text(encoding='utf-8'))


def load_report(report_path: str | Path) -> Dict[str, Any]:
    path = Path(report_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f'report not found: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def contains_all(text: str, phrases: Iterable[str]) -> bool:
    normalized = (text or '').lower()
    return all((phrase or '').lower() in normalized for phrase in phrases)


def contains_any(text: str, phrases: Iterable[str]) -> bool:
    normalized = (text or '').lower()
    return any((phrase or '').lower() in normalized for phrase in phrases)


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
        'text': item.get('text', ''),
    }


def citation_candidate(citation: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'title': citation.get('title', ''),
        'snippet': citation.get('snippet', ''),
    }


def evaluate_case(case: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    expectations = case.get('expectations') or {}
    answer = payload.get('answer', '')
    items = payload.get('items') or []
    citations = payload.get('citations') or []

    answer_all_ok = contains_all(answer, expectations.get('answerContainsAll', []))
    answer_any_required = expectations.get('answerContainsAny', [])
    answer_any_ok = True if not answer_any_required else contains_any(answer, answer_any_required)

    item_candidates = [item_candidate(item) for item in items]
    citation_candidates = [citation_candidate(citation) for citation in citations]

    retrieval_ok = any_match(item_candidates, expectations.get('retrievalAny', []))
    citation_ok = any_match(citation_candidates, expectations.get('citationAny', []))

    passed = answer_all_ok and answer_any_ok and retrieval_ok and citation_ok
    return {
        'passed': passed,
        'answerAllOk': answer_all_ok,
        'answerAnyOk': answer_any_ok,
        'retrievalOk': retrieval_ok,
        'citationOk': citation_ok,
        'latencyMs': payload.get('latencyMs'),
        'answer': answer,
        'topItems': item_candidates[:3],
        'citations': citation_candidates,
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
    doc_scope = [uploaded[key]['docId'] for key in scope_keys] if scope_keys else list(default_scope)
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
                'citationOk': bool(cur.get('citationOk')),
            },
            'baselineChecks': {
                'answerAllOk': bool(base.get('answerAllOk')),
                'answerAnyOk': bool(base.get('answerAnyOk')),
                'retrievalOk': bool(base.get('retrievalOk')),
                'citationOk': bool(base.get('citationOk')),
            },
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
    metrics = ['passed', 'answerAll', 'answerAny', 'retrieval', 'citation']
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
        'changedCases': [case for case in unchanged if case['status'] == 'latency_change'],
        'tagDelta': tag_delta,
    }


def format_comparison_lines(comparison: Dict[str, Any]) -> List[str]:
    lines = []
    totals_delta = comparison['totalsDelta']
    lines.append('[compare] totals ' + ' '.join(f"{metric}={delta:+d}" for metric, delta in totals_delta.items()))
    lines.append(f"[compare] regressions={comparison['regressionCount']} improvements={comparison['improvementCount']} changed={len(comparison['changedCases'])}")

    if comparison['regressions']:
        lines.append('[compare] regressions:')
        for case in comparison['regressions'][:10]:
            lines.append(f"  - {case['id']} status={case['status']} baseline={case.get('baselinePassed')} current={case.get('currentPassed')} latencyDeltaMs={case.get('latencyDeltaMs', 0):+d}")

    if comparison['improvements']:
        lines.append('[compare] improvements:')
        for case in comparison['improvements'][:10]:
            lines.append(f"  - {case['id']} status={case['status']} baseline={case.get('baselinePassed')} current={case.get('currentPassed')} latencyDeltaMs={case.get('latencyDeltaMs', 0):+d}")

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
    parser.add_argument('--suite', default='small', choices=['small', 'medium', 'large', 'longlite', 'xlarge'])
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
            print(f"  topItems: {json.dumps(evaluation['topItems'], ensure_ascii=False)}")
            print(f"  citations: {json.dumps(evaluation['citations'], ensure_ascii=False)}")

        answer_all_pass += int(evaluation['answerAllOk'])
        answer_any_pass += int(evaluation['answerAnyOk'])
        retrieval_pass += int(evaluation['retrievalOk'])
        citation_pass += int(evaluation['citationOk'])

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

    print(f"[summary] passed={passed_cases}/{total_cases}")
    print(f"[summary] answerAll={answer_all_pass}/{total_cases} answerAny={answer_any_pass}/{total_cases} retrieval={retrieval_pass}/{total_cases} citation={citation_pass}/{total_cases}")
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
        },
        'tagStats': tag_stats,
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
