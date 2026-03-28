import json
import time
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder

from app.core.config import EMBEDDING_MODEL, LLM_MODEL, QUERY_CACHE_TTL_SEC
from app.core.logging_config import logger
from app.models.schemas import (
    DecisionSummary,
    DecisionSummarySection,
    IngestRequest,
    InternalUploadRequest,
    InternalUploadResponse,
    QueryRequest,
    QueryResponse,
    RetrievedItem,
    RoutedDoc,
    TaskStatusResponse,
)
from app.services.cache_service import build_query_cache_key, get_kb_cache_version
from app.services.document_service import create_doc_and_task, load_task
from app.services.embedding_service import embed_query
from app.services.ingest_service import run_ingest_job
from app.services.llm_service import build_refusal_answer, generate_answer, is_refusal_answer
from app.services.query_service import QUERY_PLANNER_VERSION, plan_query
from app.services.rerank_service import rerank_cache_signature
from app.services.retrieval_service import assess_answerability, build_answer_citations, route_documents, search_chunks
from app.utils.trace import get_trace_id

router = APIRouter()


def _merge_routed_docs(candidate_lists: list[list[RoutedDoc]], top_n: int) -> list[RoutedDoc]:
    merged: dict[int, dict] = {}
    for docs in candidate_lists:
        for doc in docs:
            current = merged.get(doc.docId)
            if current is None:
                merged[doc.docId] = {
                    'doc': doc,
                    'hits': 1,
                    'reasons': [doc.reason] if doc.reason else [],
                }
                continue
            current['hits'] += 1
            if doc.score > current['doc'].score:
                current['doc'] = doc
            if doc.reason:
                current['reasons'].append(doc.reason)

    rows: list[RoutedDoc] = []
    for row in merged.values():
        doc = row['doc']
        bonus = 0.03 * max(0, row['hits'] - 1)
        reasons: list[str] = []
        seen = set()
        for raw in row['reasons']:
            for reason in str(raw).split('+'):
                reason = reason.strip()
                if not reason or reason in seen:
                    continue
                seen.add(reason)
                reasons.append(reason)
        rows.append(
            RoutedDoc(
                docId=doc.docId,
                title=doc.title,
                score=round(float(doc.score) + bonus, 6),
                summary=doc.summary,
                keywords=doc.keywords,
                sourceType=doc.sourceType,
                reason='+'.join(reasons) if reasons else doc.reason,
            )
        )

    rows.sort(key=lambda x: x.score, reverse=True)
    return rows[:top_n]


def _merge_retrieved_items(candidate_lists: list[list[RetrievedItem]], top_k: int) -> list[RetrievedItem]:
    merged: dict[int, dict] = {}
    for items in candidate_lists:
        for item in items:
            current = merged.get(item.chunkId)
            if current is None:
                merged[item.chunkId] = {'item': item, 'hits': 1}
                continue
            current['hits'] += 1
            if item.score > current['item'].score:
                current['item'] = item

    rows: list[RetrievedItem] = []
    for row in merged.values():
        item = row['item']
        bonus = 0.02 * max(0, row['hits'] - 1)
        blended_score = float(item.blendedScore if item.blendedScore is not None else item.score)
        rows.append(
            RetrievedItem(
                docId=item.docId,
                chunkId=item.chunkId,
                chunkIndex=item.chunkIndex,
                score=round(float(item.score) + bonus, 6),
                localScore=item.localScore,
                rerankScore=item.rerankScore,
                blendedScore=round(blended_score + bonus, 6),
                text=item.text,
                heading=item.heading,
                sectionPath=item.sectionPath,
                chunkType=item.chunkType,
                sourceType=item.sourceType,
                citation=item.citation,
            )
        )

    rows.sort(key=lambda x: x.score, reverse=True)
    return rows[:top_k]


def _merge_rerank_debug(candidate_debugs: list[dict]) -> dict | None:
    if not candidate_debugs:
        return None

    provider = next((row.get('provider') for row in candidate_debugs if row.get('provider')), None)
    model = next((row.get('model') for row in candidate_debugs if row.get('model')), None)
    resolved_intent = next((row.get('resolvedIntent') for row in candidate_debugs if row.get('resolvedIntent')), {})
    local_top_items = next((row.get('localTopItems') for row in candidate_debugs if row.get('localTopItems')), [])
    final_top_items = next((row.get('finalTopItems') for row in candidate_debugs if row.get('finalTopItems')), [])
    fallback_reasons = []
    seen_reasons = set()
    for row in candidate_debugs:
        reason = str(row.get('fallbackReason') or '').strip()
        if reason and reason not in seen_reasons:
            seen_reasons.add(reason)
            fallback_reasons.append(reason)

    return {
        'enabled': any(bool(row.get('enabled')) for row in candidate_debugs),
        'provider': provider,
        'model': model,
        'callCount': sum(int(row.get('callCount') or 0) for row in candidate_debugs),
        'requestedTopN': max(int(row.get('requestedTopN') or 0) for row in candidate_debugs),
        'candidateCount': sum(int(row.get('candidateCount') or 0) for row in candidate_debugs),
        'appliedCount': sum(int(row.get('appliedCount') or 0) for row in candidate_debugs),
        'fallback': any(bool(row.get('fallback')) for row in candidate_debugs),
        'fallbackReason': ' | '.join(fallback_reasons) if fallback_reasons else None,
        'latencyMs': sum(int(row.get('latencyMs') or 0) for row in candidate_debugs),
        'resolvedIntent': resolved_intent,
        'localTopItems': local_top_items,
        'finalTopItems': final_top_items,
        'orderingChanged': any(bool(row.get('orderingChanged')) for row in candidate_debugs),
    }


def _active_intents(intent: dict[str, bool]) -> list[str]:
    return [key for key, enabled in intent.items() if enabled]


def _format_score(score: float | None) -> str:
    if score is None:
        return 'n/a'
    return f"{float(score):.3f}"


def _evidence_band(evidence_score: float | None) -> str:
    score = float(evidence_score or 0.0)
    if score >= 0.38:
        return 'strong'
    if score >= 0.24:
        return 'moderate'
    return 'weak'


def _item_anchor(item: RetrievedItem) -> str:
    return item.heading or item.sectionPath or f"chunk#{item.chunkIndex}"


def _summarize_routed_doc(doc: RoutedDoc) -> str:
    detail = f"reason={doc.reason}" if doc.reason else 'reason=unspecified'
    return f"{doc.title} (score={doc.score:.3f}, {detail})"


def _summarize_item(item: RetrievedItem) -> str:
    return (
        f"{item.citation.title} / {_item_anchor(item)} "
        f"[{item.chunkType or 'chunk'}] score={item.score:.3f}"
    )


def _route_doc_debug(doc: RoutedDoc) -> dict:
    return {
        'docId': doc.docId,
        'title': doc.title,
        'score': round(float(doc.score), 6),
        'reason': doc.reason,
        'sourceType': doc.sourceType,
    }


def _build_route_run_debug(query_text: str, docs: list[RoutedDoc], query_intent: dict[str, bool]) -> dict:
    return {
        'query': query_text,
        'intent': dict(query_intent),
        'topDocs': [_route_doc_debug(doc) for doc in docs[:3]],
    }


def _build_retrieval_run_debug(query_text: str, debug: dict | None) -> dict:
    debug = debug or {}
    return {
        'query': query_text,
        'resolvedIntent': debug.get('resolvedIntent') or {},
        'localTopItems': debug.get('localTopItems') or [],
        'finalTopItems': debug.get('finalTopItems') or [],
        'orderingChanged': bool(debug.get('orderingChanged')),
        'rerankApplied': int(debug.get('appliedCount') or 0) > 0,
        'rerankFallback': bool(debug.get('fallback')),
    }


def _build_attribution_hints(query_plan, route_runs: list[dict], retrieval_runs: list[dict], rerank_debug: dict | None) -> list[str]:
    hints: list[str] = []
    if query_plan.focusQuestion:
        hints.append('planner_focus_query')
    if query_plan.decomposition:
        hints.append('planner_decomposition')
    if route_runs:
        hints.append('route_query_fanout')
    if retrieval_runs:
        hints.append('retrieval_query_fanout')
    if any(bool(run.get('orderingChanged')) for run in retrieval_runs):
        hints.append('rerank_reordered_top_items')
    if rerank_debug and bool(rerank_debug.get('fallback')):
        hints.append('rerank_fallback')
    return hints


def _build_decision_summary(
    question: str,
    requested_doc_scope: list[int],
    resolved_doc_scope: list[int],
    query_plan,
    routed_docs: list[RoutedDoc],
    items: list[RetrievedItem],
    citations,
    refused: bool,
    refusal_reason: str | None,
    evidence_score: float | None,
    rerank_debug: dict | None = None,
) -> DecisionSummary:
    active_intents = _active_intents(query_plan.intent)
    intent_label = ', '.join(active_intents) if active_intents else 'general'

    planner_summary = (
        f"Planner classified the query as {intent_label}; "
        f"prepared {len(query_plan.routeQueries)} route queries and {len(query_plan.retrievalQueries)} retrieval queries."
    )
    planner_highlights = []
    if query_plan.normalizedQuestion and query_plan.normalizedQuestion != question:
        planner_highlights.append(f"normalized={query_plan.normalizedQuestion}")
    if query_plan.focusQuestion:
        planner_highlights.append(f"focus={query_plan.focusQuestion}")
    if query_plan.decomposition:
        planner_highlights.append('subqueries=' + ' | '.join(query_plan.decomposition[:3]))
    if query_plan.routeQueries:
        planner_highlights.append('routeQueries=' + ' | '.join(query_plan.routeQueries[:2]))
    if query_plan.retrievalQueries:
        planner_highlights.append('retrievalQueries=' + ' | '.join(query_plan.retrievalQueries[:2]))

    if requested_doc_scope:
        routing_summary = f"Used explicit docScope with {len(requested_doc_scope)} document(s); automatic routing was skipped."
        routing_highlights = [f"requestedDocScope={requested_doc_scope[:5]}"]
    elif routed_docs:
        routing_summary = (
            f"Auto-routed to {len(routed_docs)} document(s); top candidate is {routed_docs[0].title}."
        )
        routing_highlights = [_summarize_routed_doc(doc) for doc in routed_docs[:3]]
    elif resolved_doc_scope:
        routing_summary = f"Used a resolved document scope with {len(resolved_doc_scope)} document(s)."
        routing_highlights = [f"resolvedDocScope={resolved_doc_scope[:5]}"]
    else:
        routing_summary = 'No document route was applied; retrieval searched the full ready knowledge base.'
        routing_highlights = []

    if items:
        top_item = items[0]
        retrieval_summary = (
            f"Retrieved {len(items)} chunk(s); top chunk is {_item_anchor(top_item)} from {top_item.citation.title} "
            f"with score {_format_score(top_item.score)}."
        )
        retrieval_highlights = [_summarize_item(item) for item in items[:3]]
        if rerank_debug and rerank_debug.get('enabled'):
            if rerank_debug.get('fallback'):
                retrieval_summary += " Cloud rerank fell back to local ordering."
                retrieval_highlights.append(
                    f"rerank fallback={rerank_debug.get('fallbackReason') or 'unknown'}"
                )
            elif int(rerank_debug.get('appliedCount') or 0) > 0:
                retrieval_summary += (
                    f" Cloud rerank re-ordered {int(rerank_debug.get('appliedCount') or 0)} candidate(s)."
                )
                retrieval_highlights.append(
                    f"rerank={rerank_debug.get('provider') or 'generic'}/{rerank_debug.get('model') or 'unknown'} "
                    f"calls={int(rerank_debug.get('callCount') or 0)} "
                    f"latencyMs={int(rerank_debug.get('latencyMs') or 0)}"
                )
    else:
        retrieval_summary = 'Retrieval returned no chunks.'
        retrieval_highlights = []

    evidence_band = _evidence_band(evidence_score)
    if refused:
        answerability_summary = (
            f"Generation was blocked: evidence is {evidence_band} "
            f"(score={_format_score(evidence_score)} reason={refusal_reason or 'unknown'})."
        )
    else:
        answerability_summary = (
            f"Answer generation proceeded with {evidence_band} evidence "
            f"(score={_format_score(evidence_score)})."
        )
    answerability_highlights = [
        f"refused={str(refused).lower()}",
        f"evidenceScore={_format_score(evidence_score)}",
    ]
    if refusal_reason:
        answerability_highlights.append(f"reason={refusal_reason}")

    if refused:
        citation_summary = 'Refusal path returned no citations.'
        citation_highlights = []
    elif citations:
        lead = citations[0]
        page = f" p{lead.page}" if getattr(lead, 'page', None) else ''
        citation_summary = f"Attached {len(citations)} citation(s); lead citation is {lead.title}{page}."
        citation_highlights = [
            f"{citation.title}{(' p' + str(citation.page)) if getattr(citation, 'page', None) else ''}"
            for citation in citations[:3]
        ]
    else:
        citation_summary = 'Answer completed without citations.'
        citation_highlights = []

    route_label = 'explicit scope' if requested_doc_scope else ('auto-routed' if routed_docs else 'global search')
    outcome_label = 'refused' if refused else 'answered'
    headline = (
        f"{outcome_label.capitalize()} after {route_label}; planner intent={intent_label}; "
        f"evidence={_format_score(evidence_score)} ({evidence_band})."
    )

    return DecisionSummary(
        headline=headline,
        planner=DecisionSummarySection(summary=planner_summary, highlights=planner_highlights),
        routing=DecisionSummarySection(summary=routing_summary, highlights=routing_highlights),
        retrieval=DecisionSummarySection(summary=retrieval_summary, highlights=retrieval_highlights),
        answerability=DecisionSummarySection(summary=answerability_summary, highlights=answerability_highlights),
        citation=DecisionSummarySection(summary=citation_summary, highlights=citation_highlights),
    )


@router.post('/internal/ingest')
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


@router.post('/internal/query', response_model=QueryResponse)
async def internal_query(req: QueryRequest, request: Request, response: Response):
    trace_id = get_trace_id(request)
    total_started_at = time.perf_counter()

    question = (req.question or '').strip()
    if not question:
        raise HTTPException(status_code=400, detail='question must not be empty')

    top_k = max(1, min(req.topK, 10))
    doc_scope = sorted(set(req.docScope or []))
    resolved_doc_scope = list(doc_scope)
    routed_docs: list[RoutedDoc] = []
    route_runs_debug: list[dict] = []
    retrieval_runs_debug: list[dict] = []
    query_plan = plan_query(question)

    logger.info(
        'internal_query start trace_id=%s question_len=%s top_k=%s requested_doc_scope=%s focus_question=%s route_queries=%s retrieval_queries=%s intent=%s',
        trace_id,
        len(question),
        top_k,
        doc_scope,
        query_plan.focusQuestion,
        query_plan.routeQueries,
        query_plan.retrievalQueries,
        query_plan.intent,
    )

    redis_cli = getattr(request.app.state, 'redis', None)
    kb_version = await get_kb_cache_version(redis_cli)

    cache_key = build_query_cache_key(
        question=question,
        doc_scope=doc_scope,
        top_k=top_k,
        embed_model=EMBEDDING_MODEL,
        gen_model=LLM_MODEL,
        kb_version=kb_version,
        rerank_signature=rerank_cache_signature(),
    )

    if redis_cli is not None:
        try:
            cached = await redis_cli.get(cache_key)
            if cached:
                resp_body = json.loads(cached)
                resp_body.setdefault('refused', False)
                resp_body.setdefault('refusalReason', None)
                resp_body.setdefault('evidenceScore', None)
                resp_body.setdefault('resolvedDocScope', resp_body.get('docScope', []))
                resp_body.setdefault('routedDocs', [])
                resp_body.setdefault('queryDebug', None)

                if resp_body.get('refused'):
                    resp_body['citations'] = []
                elif resp_body.get('items'):
                    cached_items = [RetrievedItem(**item) for item in resp_body['items']]
                    resp_body['citations'] = jsonable_encoder(
                        build_answer_citations(
                            question=resp_body.get('question', question),
                            items=cached_items,
                            answer=resp_body.get('answer', ''),
                        )
                    )

                resp_body['latencyMs'] = max(1, int((time.perf_counter() - total_started_at) * 1000))
                response.headers['x-cache'] = 'hit'
                response.headers['x-kb-version'] = str(kb_version)
                return QueryResponse(**resp_body)
        except Exception as e:
            logger.warning('internal_query cache_read_failed trace_id=%s error=%s', trace_id, str(e))

    try:
        embed_started_at = time.perf_counter()
        query_vectors: dict[str, list[float]] = {}
        for query_text in query_plan.retrievalQueries + query_plan.routeQueries:
            if query_text not in query_vectors:
                query_vectors[query_text] = embed_query(query_text)
        embed_ms = int((time.perf_counter() - embed_started_at) * 1000)

        route_ms = 0
        if not resolved_doc_scope:
            route_started_at = time.perf_counter()
            route_candidates = []
            for query_text in query_plan.routeQueries[:2]:
                route_docs = route_documents(
                    question=query_text,
                    question_embedding=query_vectors[query_text],
                    top_n=min(max(top_k + 2, 3), 5),
                    query_intent=query_plan.intent,
                )
                route_candidates.append(route_docs)
                route_runs_debug.append(_build_route_run_debug(query_text, route_docs, query_plan.intent))
            routed_docs = _merge_routed_docs(route_candidates, top_n=min(max(top_k + 2, 3), 5))
            route_ms = int((time.perf_counter() - route_started_at) * 1000)
            resolved_doc_scope = [doc.docId for doc in routed_docs]

        retrieve_started_at = time.perf_counter()
        retrieval_runs = []
        for query_text in query_plan.retrievalQueries[:2]:
            retrieved_items, retrieval_debug = search_chunks(
                query_text,
                query_vectors[query_text],
                resolved_doc_scope,
                top_k,
                query_intent=query_plan.intent,
            )
            retrieval_runs.append((retrieved_items, retrieval_debug))
            retrieval_runs_debug.append(_build_retrieval_run_debug(query_text, retrieval_debug))
        retrieved_lists = [items for items, _ in retrieval_runs]
        rerank_debug = _merge_rerank_debug([debug for _, debug in retrieval_runs])
        items = _merge_retrieved_items(retrieved_lists, top_k=top_k)
        retrieve_ms = int((time.perf_counter() - retrieve_started_at) * 1000)

        decision = assess_answerability(question, items)
        evidence_score = float(decision.get('evidenceScore') or 0.0)
        refused = bool(decision.get('shouldRefuse'))
        refusal_reason = str(decision.get('reason') or '') or None

        generate_ms = 0
        if refused:
            answer = build_refusal_answer(refusal_reason or 'low_retrieval_confidence')
        else:
            generate_started_at = time.perf_counter()
            answer = generate_answer(question, items, evidence_score=evidence_score)
            generate_ms = int((time.perf_counter() - generate_started_at) * 1000)
            if is_refusal_answer(answer):
                refused = True
                refusal_reason = 'model_insufficient_evidence'
                answer = build_refusal_answer(refusal_reason)

        citations = [] if refused else build_answer_citations(question=question, items=items, answer=answer)
        total_ms = int((time.perf_counter() - total_started_at) * 1000)
        decision_summary = _build_decision_summary(
            question=question,
            requested_doc_scope=doc_scope,
            resolved_doc_scope=resolved_doc_scope,
            query_plan=query_plan,
            routed_docs=routed_docs,
            items=items,
            citations=citations,
            refused=refused,
            refusal_reason=refusal_reason,
            evidence_score=evidence_score,
            rerank_debug=rerank_debug,
        )
        query_debug = {
            'plannerVersion': QUERY_PLANNER_VERSION,
            'normalizedQuestion': query_plan.normalizedQuestion,
            'focusQuestion': query_plan.focusQuestion,
            'decomposition': query_plan.decomposition,
            'intent': query_plan.intent,
            'routeQueries': query_plan.routeQueries,
            'retrievalQueries': query_plan.retrievalQueries,
            'routeRuns': route_runs_debug,
            'retrievalRuns': retrieval_runs_debug,
            'attributionHints': _build_attribution_hints(query_plan, route_runs_debug, retrieval_runs_debug, rerank_debug),
            'queryVectorCount': len(query_vectors),
            'rerank': rerank_debug,
            'timingsMs': {
                'embed': embed_ms,
                'route': route_ms,
                'retrieve': retrieve_ms,
                'generate': generate_ms,
                'total': total_ms,
            },
            'decisionSummary': jsonable_encoder(decision_summary),
        }

        response_obj = QueryResponse(
            question=question,
            answer=answer,
            refused=refused,
            refusalReason=refusal_reason,
            evidenceScore=evidence_score,
            items=items,
            citations=citations,
            resolvedDocScope=resolved_doc_scope,
            routedDocs=routed_docs,
            queryDebug=query_debug,
            latencyMs=total_ms,
        )
        response_data = jsonable_encoder(response_obj)

        logger.info(
            'internal_query success trace_id=%s result_count=%s citation_count=%s refused=%s refusal_reason=%s evidence_score=%s embed_ms=%s route_ms=%s routed_doc_count=%s retrieve_ms=%s generate_ms=%s total_ms=%s resolved_doc_scope=%s',
            trace_id,
            len(items),
            len(citations),
            refused,
            refusal_reason,
            evidence_score,
            embed_ms,
            route_ms,
            len(routed_docs),
            retrieve_ms,
            generate_ms,
            total_ms,
            resolved_doc_scope,
        )

        if redis_cli is not None:
            try:
                await redis_cli.setex(cache_key, QUERY_CACHE_TTL_SEC, json.dumps(response_data, ensure_ascii=False))
            except Exception as e:
                logger.warning('internal_query cache_write_failed trace_id=%s error=%s', trace_id, str(e))

        response.headers['x-cache'] = 'miss'
        response.headers['x-kb-version'] = str(kb_version)
        return response_obj

    except HTTPException:
        raise
    except Exception as e:
        logger.exception('internal_query failed trace_id=%s error=%s', trace_id, str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/internal/docs/upload', response_model=InternalUploadResponse)
def internal_docs_upload(req: InternalUploadRequest, request: Request, background_tasks: BackgroundTasks):
    trace_id = get_trace_id(request)

    source_path = Path(req.sourcePath)
    if not source_path.exists():
        raise HTTPException(status_code=400, detail=f'sourcePath not found: {req.sourcePath}')

    allowed_exts = {'.md', '.txt', '.pdf', '.docx'}
    ext = source_path.suffix.lower()
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail=f"unsupported file type: {ext}, supported: {', '.join(sorted(allowed_exts))}")

    doc_id, task_id, upload_status = create_doc_and_task(title=req.title, source_path=req.sourcePath, owner=req.owner)
    if upload_status == 'queued':
        background_tasks.add_task(
            run_ingest_job,
            task_id=task_id,
            doc_id=doc_id,
            source_path=req.sourcePath,
            title=req.title,
            trace_id=trace_id,
        )

    logger.info(
        'internal_docs_upload accepted trace_id=%s task_id=%s doc_id=%s status=%s source_path=%s title=%s owner=%s',
        trace_id,
        task_id,
        doc_id,
        upload_status,
        req.sourcePath,
        req.title,
        req.owner,
    )
    return InternalUploadResponse(docId=doc_id, taskId=task_id, status=upload_status)


@router.get('/internal/tasks/{task_id}', response_model=TaskStatusResponse)
def internal_task_status(task_id: str, request: Request):
    trace_id = get_trace_id(request)
    task = load_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f'task not found: {task_id}')

    task_pk, doc_id, status, progress, error = task
    logger.info('internal_task_status trace_id=%s task_id=%s status=%s progress=%s', trace_id, task_id, status, progress)
    return TaskStatusResponse(
        taskId=str(task_pk),
        docId=doc_id,
        status=status,
        progress=progress,
        error=error,
    )



