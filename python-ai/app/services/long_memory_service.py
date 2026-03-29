import json
import re
from datetime import datetime

from app.db.postgres import get_conn
from app.models.game_schemas import (
    ArchivePromotionSummary,
    CharacterCard,
    GameSession,
    LongMemoryItem,
    LongMemoryProfile,
    LongMemoryState,
    MemoryProfile,
)
from app.services.assistant_service import DEFAULT_USER_SCOPE, resolve_session_assistant_id
from app.services.embedding_service import embed_query, embed_texts, vector_to_pg
from app.services.worldbook_service import get_worldbook


PROMOTION_IMPORTANCE_THRESHOLD = 0.7
LONG_MEMORY_CANDIDATE_K = 12


def _session_user_scope(session: GameSession) -> str:
    return DEFAULT_USER_SCOPE


def _session_assistant_id(session: GameSession) -> str:
    assistant_id = resolve_session_assistant_id(session)
    if assistant_id:
        return assistant_id
    if session.characterIds:
        return f'assistant:{session.characterIds[0]}'
    return ''


def _to_db_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def _from_db_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.replace(microsecond=0).isoformat()


def _contains_term(text: str, term: str) -> bool:
    return (term or '').strip().lower() in (text or '').lower()


def _normalize_memory_text(text: str) -> str:
    return re.sub(r'\s+', '', (text or '').strip()).lower()


def _dedupe_texts(items: list[str], limit: int | None = None) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = _normalize_memory_text(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        rows.append(item.strip())
        if limit is not None and len(rows) >= limit:
            break
    return rows


def _keyword_terms(text: str) -> list[str]:
    normalized = (text or '').strip().lower()
    if not normalized:
        return []

    ascii_terms = [term for term in re.findall(r'[a-z0-9_]+', normalized) if len(term) >= 2]
    cjk_terms: list[str] = []
    for chunk in re.findall(r'[\u4e00-\u9fff]{2,}', normalized):
        cjk_terms.append(chunk)
        if len(chunk) > 2:
            cjk_terms.extend(chunk[index : index + 2] for index in range(len(chunk) - 1))

    deduped: list[str] = []
    seen: set[str] = set()
    for term in ascii_terms + cjk_terms:
        if term in seen:
            continue
        seen.add(term)
        deduped.append(term)
    return deduped


def _build_retrieval_text(session: GameSession, entry, characters_by_id: dict[str, CharacterCard]) -> str:
    character_names = [characters_by_id[character_id].name for character_id in entry.characterIds if character_id in characters_by_id]
    parts = [
        entry.summary,
        entry.type,
        entry.locationId or '',
        entry.sceneId or '',
        ' '.join(entry.triggerHints),
        ' '.join(character_names),
        session.title,
    ]
    return ' '.join(part.strip() for part in parts if part and part.strip())


def _memory_identity(memory_type: str, location_id: str | None, retrieval_summary: str) -> tuple[str, str, str]:
    return ((memory_type or '').strip().lower(), (location_id or '').strip().lower(), _normalize_memory_text(retrieval_summary))


def _location_labels(worldbook_id: str) -> dict[str, str]:
    try:
        worldbook = get_worldbook(worldbook_id)
    except Exception:
        return {}
    return {location.id: location.name for location in worldbook.locations}


def _location_label(location_labels: dict[str, str], location_id: str | None) -> str:
    if not location_id:
        return '那个场景'
    return location_labels.get(location_id, location_id)


def _infer_memory_type(retrieval_summary: str, memory_type: str | None = None) -> str:
    if memory_type:
        return memory_type
    if '陪伴或承诺' in retrieval_summary or '守约' in retrieval_summary or '承诺' in retrieval_summary:
        return 'promise'
    if '秘密线索' in retrieval_summary or '解锁' in retrieval_summary:
        return 'secret_unlock'
    return 'event'


def _location_id_from_retrieval_summary(retrieval_summary: str) -> str | None:
    patterns = [
        r'在([a-zA-Z0-9_]+)场景中',
        r'在([a-zA-Z0-9_]+)向',
        r'在([a-zA-Z0-9_]+)聊过',
    ]
    for pattern in patterns:
        match = re.search(pattern, retrieval_summary)
        if match:
            return match.group(1).strip()
    return None


def _display_summary_from_retrieval(retrieval_summary: str, memory_type: str | None, location_id: str | None, location_labels: dict[str, str]) -> str:
    resolved_type = _infer_memory_type(retrieval_summary, memory_type)
    resolved_location_id = location_id or _location_id_from_retrieval_summary(retrieval_summary)
    location_name = _location_label(location_labels, resolved_location_id)
    topic_match = re.search(r'围绕“([^”]+)”', retrieval_summary)
    secret_match = re.search(r'秘密线索：([^。]+)', retrieval_summary)

    if resolved_type == 'promise':
        return f'你曾在{location_name}给过她一个关于陪伴或守约的承诺。'
    if resolved_type == 'secret_unlock':
        secret_label = secret_match.group(1).strip() if secret_match else '更私密的线索'
        return f'她曾在{location_name}向你透露过关于“{secret_label}”的线索。'
    if topic_match:
        return f'她还记得你们在{location_name}聊过“{topic_match.group(1).strip()}”。'
    return f'{location_name}那次互动，被她安静地记在心里。'


def _stage_display_phrase(relationship_stage: str) -> str:
    stage = (relationship_stage or '').strip().lower()
    if stage == 'close':
        return '她已经把你放进了更亲近的位置。'
    if stage == 'warming_up':
        return '她开始愿意把注意力更多地留在你身上。'
    if stage == 'strained':
        return '你们之间还有没彻底放下的紧张感。'
    return '她仍保持着一点谨慎的距离。'


def _extract_profile_memory_summaries(retrieval_summary: str) -> list[str]:
    marker = '重要记忆：'
    if marker not in retrieval_summary:
        return []
    tail = retrieval_summary.split(marker, 1)[1]
    return _dedupe_texts([item.strip() for item in tail.split('/') if item.strip()], limit=3)


def _build_profile_display_summary(
    relationship_stage: str,
    player_image_summary: str,
    retrieval_summary: str,
    location_labels: dict[str, str],
) -> tuple[str, str]:
    memory_display_summaries = _dedupe_texts(
        [
            _display_summary_from_retrieval(summary, None, None, location_labels)
            for summary in _extract_profile_memory_summaries(retrieval_summary)
        ],
        limit=2,
    )
    base_summary = player_image_summary.strip() or _stage_display_phrase(relationship_stage)
    detail = f'她记得：{"；".join(memory_display_summaries)}' if memory_display_summaries else ''
    display_summary = ' '.join(part for part in [base_summary, detail] if part).strip()
    display_teaser = memory_display_summaries[0] if memory_display_summaries else base_summary
    return display_summary, display_teaser


def _profile_retrieval_summary(
    session_profile: MemoryProfile | None,
    relationship_stage: str,
    trust: int,
    affection: int,
    tension: int,
    latest_memory_summaries: list[str],
) -> str:
    relationship_summary = (
        session_profile.relationshipSummary.strip()
        if session_profile and session_profile.relationshipSummary.strip()
        else f'当前关系阶段为 {relationship_stage}，trust={trust}，affection={affection}，tension={tension}。'
    )
    player_image_summary = session_profile.playerImageSummary.strip() if session_profile else ''

    parts = [relationship_summary, player_image_summary]
    if latest_memory_summaries:
        parts.append(f'重要记忆：{" / ".join(latest_memory_summaries[:3])}')

    return ' '.join(part for part in parts if part)


def _dedupe_memory_entries(entries: list) -> list:
    deduped: dict[tuple[str, str, str], object] = {}
    for entry in entries:
        key = _memory_identity(entry.type, entry.locationId, entry.summary)
        current = deduped.get(key)
        if current is None:
            deduped[key] = entry
            continue
        current_importance = float(current.importance or 0.0)
        entry_importance = float(entry.importance or 0.0)
        if entry_importance > current_importance or (entry_importance == current_importance and entry.createdAt > current.createdAt):
            deduped[key] = entry
    rows = list(deduped.values())
    rows.sort(key=lambda item: item.createdAt)
    return rows


def _row_to_item(row: tuple, location_labels: dict[str, str]) -> LongMemoryItem:
    (
        memory_id,
        session_id,
        responder_id,
        character_ids,
        location_id,
        memory_type,
        summary,
        created_at,
        importance,
        salience,
    ) = row
    retrieval_summary = summary or ''
    return LongMemoryItem(
        id=memory_id,
        sessionId=session_id,
        responderId=responder_id,
        characterIds=list(character_ids or []),
        locationId=location_id,
        memoryType=memory_type,
        retrievalSummary=retrieval_summary,
        displaySummary=_display_summary_from_retrieval(retrieval_summary, memory_type, location_id, location_labels),
        createdAt=_from_db_timestamp(created_at) or '',
        importance=float(importance or 0.0),
        salience=float(salience or 0.0),
    )


def _dedupe_long_memory_items(items: list[LongMemoryItem], limit: int | None = None) -> list[LongMemoryItem]:
    rows: list[LongMemoryItem] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = _memory_identity(item.memoryType, item.locationId, item.retrievalSummary)
        if key in seen:
            continue
        seen.add(key)
        rows.append(item)
        if limit is not None and len(rows) >= limit:
            break
    return rows


def _upsert_memory_profile(
    cur,
    *,
    assistant_id: str,
    user_scope: str,
    worldbook_id: str,
    character_id: str,
    latest_session_id: str,
    relationship_stage: str,
    trust: int,
    affection: int,
    tension: int,
    familiarity: int,
    player_image_summary: str,
    relationship_summary: str,
    long_term_summary: str,
    open_threads: list[str],
    important_memory_ids: list[str],
    created_at: datetime,
    updated_at: datetime,
) -> None:
    update_payload = (
        worldbook_id,
        user_scope,
        latest_session_id,
        relationship_stage,
        trust,
        affection,
        tension,
        familiarity,
        player_image_summary,
        relationship_summary,
        long_term_summary,
        open_threads,
        important_memory_ids,
        updated_at,
        assistant_id,
        character_id,
        user_scope,
    )
    cur.execute(
        """
        UPDATE game_memory_profiles
        SET
          worldbook_id = %s,
          player_scope = %s,
          latest_session_id = %s,
          relationship_stage = %s,
          trust = %s,
          affection = %s,
          tension = %s,
          familiarity = %s,
          player_image_summary = %s,
          relationship_summary = %s,
          long_term_summary = %s,
          open_threads = %s::text[],
          important_memory_ids = %s::text[],
          last_interaction_at = %s,
          updated_at = %s
        WHERE assistant_id = %s
          AND character_id = %s
          AND user_scope = %s
        """,
        (
            *update_payload[:13],
            updated_at,
            *update_payload[13:],
        ),
    )
    if cur.rowcount:
        return

    cur.execute(
        """
        UPDATE game_memory_profiles
        SET
          assistant_id = %s,
          user_scope = %s,
          latest_session_id = %s,
          relationship_stage = %s,
          trust = %s,
          affection = %s,
          tension = %s,
          familiarity = %s,
          player_image_summary = %s,
          relationship_summary = %s,
          long_term_summary = %s,
          open_threads = %s::text[],
          important_memory_ids = %s::text[],
          last_interaction_at = %s,
          updated_at = %s
        WHERE worldbook_id = %s
          AND character_id = %s
          AND player_scope = %s
        """,
        (
            assistant_id,
            user_scope,
            latest_session_id,
            relationship_stage,
            trust,
            affection,
            tension,
            familiarity,
            player_image_summary,
            relationship_summary,
            long_term_summary,
            open_threads,
            important_memory_ids,
            updated_at,
            updated_at,
            worldbook_id,
            character_id,
            user_scope,
        ),
    )
    if cur.rowcount:
        return

    cur.execute(
        """
        INSERT INTO game_memory_profiles (
          assistant_id,
          user_scope,
          worldbook_id,
          character_id,
          player_scope,
          latest_session_id,
          relationship_stage,
          trust,
          affection,
          tension,
          familiarity,
          player_image_summary,
          relationship_summary,
          long_term_summary,
          open_threads,
          important_memory_ids,
          last_interaction_at,
          created_at,
          updated_at
        ) VALUES (
          %s,
          %s,
          %s,
          %s,
          %s,
          %s,
          %s,
          %s,
          %s,
          %s,
          %s,
          %s,
          %s,
          %s,
          %s::text[],
          %s::text[],
          %s,
          %s,
          %s
        )
        ON CONFLICT (assistant_id, character_id, user_scope) DO UPDATE SET
          worldbook_id = EXCLUDED.worldbook_id,
          player_scope = EXCLUDED.player_scope,
          latest_session_id = EXCLUDED.latest_session_id,
          relationship_stage = EXCLUDED.relationship_stage,
          trust = EXCLUDED.trust,
          affection = EXCLUDED.affection,
          tension = EXCLUDED.tension,
          familiarity = EXCLUDED.familiarity,
          player_image_summary = EXCLUDED.player_image_summary,
          relationship_summary = EXCLUDED.relationship_summary,
          long_term_summary = EXCLUDED.long_term_summary,
          open_threads = EXCLUDED.open_threads,
          important_memory_ids = EXCLUDED.important_memory_ids,
          last_interaction_at = EXCLUDED.last_interaction_at,
          updated_at = EXCLUDED.updated_at
        """,
        (
            assistant_id,
            user_scope,
            worldbook_id,
            character_id,
            user_scope,
            latest_session_id,
            relationship_stage,
            trust,
            affection,
            tension,
            familiarity,
            player_image_summary,
            relationship_summary,
            long_term_summary,
            open_threads,
            important_memory_ids,
            updated_at,
            created_at,
            updated_at,
        ),
    )


def promote_session_memories(
    session: GameSession,
    characters_by_id: dict[str, CharacterCard],
) -> ArchivePromotionSummary:
    assistant_id = _session_assistant_id(session)
    user_scope = _session_user_scope(session)
    promotable = [entry for entry in session.memoryEntries if float(entry.importance or 0.0) >= PROMOTION_IMPORTANCE_THRESHOLD]
    promotable = _dedupe_memory_entries(promotable)
    retrieval_texts = [_build_retrieval_text(session, entry, characters_by_id) for entry in promotable]
    vectors = embed_texts(retrieval_texts) if retrieval_texts else []
    vector_literals = [vector_to_pg(vector) for vector in vectors]

    with get_conn() as conn:
        with conn.cursor() as cur:
            for index, entry in enumerate(promotable):
                responder_id = entry.characterIds[0] if entry.characterIds else 'unknown'
                visibility_json = json.dumps(entry.visibility, ensure_ascii=False)
                cur.execute(
                    """
                    INSERT INTO game_memories (
                      id,
                      assistant_id,
                      user_scope,
                      worldbook_id,
                      session_id,
                      responder_id,
                      character_ids,
                      location_id,
                      scene_id,
                      day_index,
                      memory_type,
                      summary,
                      retrieval_text,
                      trigger_hints,
                      emotion_payload,
                      relation_payload,
                      salience,
                      importance,
                      visibility,
                      archived_from_session,
                      last_used_at,
                      created_at,
                      updated_at,
                      embedding
                    ) VALUES (
                      %s,
                      %s,
                      %s,
                      %s,
                      %s,
                      %s,
                      %s::text[],
                      %s,
                      %s,
                      %s,
                      %s,
                      %s,
                      %s,
                      %s::text[],
                      %s::jsonb,
                      %s::jsonb,
                      %s,
                      %s,
                      %s::jsonb,
                      TRUE,
                      NULL,
                      %s,
                      %s,
                      %s::vector
                    )
                    ON CONFLICT (id) DO UPDATE SET
                      assistant_id = EXCLUDED.assistant_id,
                      user_scope = EXCLUDED.user_scope,
                      worldbook_id = EXCLUDED.worldbook_id,
                      session_id = EXCLUDED.session_id,
                      responder_id = EXCLUDED.responder_id,
                      character_ids = EXCLUDED.character_ids,
                      location_id = EXCLUDED.location_id,
                      scene_id = EXCLUDED.scene_id,
                      day_index = EXCLUDED.day_index,
                      memory_type = EXCLUDED.memory_type,
                      summary = EXCLUDED.summary,
                      retrieval_text = EXCLUDED.retrieval_text,
                      trigger_hints = EXCLUDED.trigger_hints,
                      emotion_payload = EXCLUDED.emotion_payload,
                      relation_payload = EXCLUDED.relation_payload,
                      salience = EXCLUDED.salience,
                      importance = EXCLUDED.importance,
                      visibility = EXCLUDED.visibility,
                      archived_from_session = EXCLUDED.archived_from_session,
                      updated_at = EXCLUDED.updated_at,
                      embedding = EXCLUDED.embedding
                    """,
                    (
                        entry.id,
                        assistant_id,
                        user_scope,
                        session.worldbookId,
                        session.id,
                        responder_id,
                        entry.characterIds,
                        entry.locationId,
                        entry.sceneId,
                        session.runtimeState.dayIndex,
                        entry.type,
                        entry.summary,
                        retrieval_texts[index],
                        entry.triggerHints,
                        json.dumps(entry.emotionPayload, ensure_ascii=False),
                        json.dumps(entry.factPayload, ensure_ascii=False),
                        max(float(entry.importance or 0.0), PROMOTION_IMPORTANCE_THRESHOLD),
                        float(entry.importance or 0.0),
                        visibility_json,
                        _to_db_timestamp(entry.createdAt),
                        _to_db_timestamp(session.updatedAt),
                        vector_literals[index],
                    ),
                )

            for character_id in session.characterIds:
                relationship = session.runtimeState.relationshipStates.get(character_id)
                if relationship is None:
                    continue

                cur.execute(
                    """
                    SELECT summary
                    FROM game_memories
                    WHERE user_scope = %s
                      AND (assistant_id = %s OR worldbook_id = %s)
                      AND %s = ANY(character_ids)
                    ORDER BY created_at DESC, importance DESC
                    LIMIT 12
                    """,
                    (user_scope, assistant_id, session.worldbookId, character_id),
                )
                latest_memory_summaries = _dedupe_texts([row[0] for row in cur.fetchall()], limit=3)

                cur.execute(
                    """
                    SELECT id
                    FROM game_memories
                    WHERE user_scope = %s
                      AND (assistant_id = %s OR worldbook_id = %s)
                      AND %s = ANY(character_ids)
                    ORDER BY importance DESC, created_at DESC
                    LIMIT 5
                    """,
                    (user_scope, assistant_id, session.worldbookId, character_id),
                )
                important_memory_ids = [row[0] for row in cur.fetchall()]

                session_profile = session.memoryProfiles.get(character_id)
                relationship_summary = (
                    session_profile.relationshipSummary.strip()
                    if session_profile and session_profile.relationshipSummary.strip()
                    else f'当前关系阶段为 {relationship.stage}，trust={relationship.trust}，affection={relationship.affection}，tension={relationship.tension}。'
                )
                player_image_summary = session_profile.playerImageSummary.strip() if session_profile else ''
                retrieval_summary = _profile_retrieval_summary(
                    session_profile,
                    relationship.stage,
                    relationship.trust,
                    relationship.affection,
                    relationship.tension,
                    latest_memory_summaries,
                )
                open_threads = (
                    session_profile.openThreads[:3]
                    if session_profile and session_profile.openThreads
                    else session.runtimeState.activeEvents[:3]
                )
                _upsert_memory_profile(
                    cur,
                    assistant_id=assistant_id,
                    user_scope=user_scope,
                    worldbook_id=session.worldbookId,
                    character_id=character_id,
                    latest_session_id=session.id,
                    relationship_stage=relationship.stage,
                    trust=relationship.trust,
                    affection=relationship.affection,
                    tension=relationship.tension,
                    familiarity=relationship.familiarity,
                    player_image_summary=player_image_summary,
                    relationship_summary=relationship_summary,
                    long_term_summary=retrieval_summary,
                    open_threads=open_threads,
                    important_memory_ids=important_memory_ids,
                    created_at=_to_db_timestamp(session.createdAt),
                    updated_at=_to_db_timestamp(session.updatedAt),
                )

        conn.commit()

    return ArchivePromotionSummary(promotedCount=len(promotable), profileCount=len(session.characterIds))


def delete_session_long_memories(session_id: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM game_memories WHERE session_id = %s', (session_id,))


def load_long_memory_profiles(session: GameSession) -> dict[str, LongMemoryProfile]:
    assistant_id = _session_assistant_id(session)
    user_scope = _session_user_scope(session)
    if not assistant_id or not session.characterIds:
        return {}

    location_labels = _location_labels(session.worldbookId)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                      assistant_id,
                      character_id,
                      relationship_stage,
                      player_image_summary,
                      relationship_summary,
                      long_term_summary,
                      open_threads,
                      last_interaction_at
                    FROM game_memory_profiles
                    WHERE user_scope = %s
                      AND (assistant_id = %s OR worldbook_id = %s)
                      AND character_id = ANY(%s::text[])
                    ORDER BY
                      character_id ASC,
                      CASE WHEN assistant_id = %s THEN 0 ELSE 1 END ASC,
                      updated_at DESC
                    """,
                    (user_scope, assistant_id, session.worldbookId, session.characterIds, assistant_id),
                )
                rows = cur.fetchall()
    except Exception:
        return {}

    profiles: dict[str, LongMemoryProfile] = {}
    for (
        row_assistant_id,
        character_id,
        relationship_stage,
        player_image_summary,
        relationship_summary,
        long_term_summary,
        open_threads,
        last_interaction_at,
    ) in rows:
        if character_id in profiles and row_assistant_id != assistant_id:
            continue
        retrieval_summary = long_term_summary or ''
        display_summary, display_teaser = _build_profile_display_summary(
            relationship_stage or '',
            player_image_summary or '',
            retrieval_summary,
            location_labels,
        )
        profiles[character_id] = LongMemoryProfile(
            characterId=character_id,
            relationshipStage=relationship_stage or '',
            playerImageSummary=player_image_summary or '',
            relationshipSummary=relationship_summary or '',
            retrievalSummary=retrieval_summary,
            displaySummary=display_summary,
            displayTeaser=display_teaser,
            openThreads=list(open_threads or []),
            lastInteractionAt=_from_db_timestamp(last_interaction_at),
        )
    return profiles


def list_recent_long_memory_items(session: GameSession, limit: int = 6) -> list[LongMemoryItem]:
    assistant_id = _session_assistant_id(session)
    user_scope = _session_user_scope(session)
    if not assistant_id or not session.characterIds:
        return []

    location_labels = _location_labels(session.worldbookId)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                      id,
                      session_id,
                      responder_id,
                      character_ids,
                      location_id,
                      memory_type,
                      summary,
                      created_at,
                      importance,
                      salience
                    FROM game_memories
                    WHERE user_scope = %s
                      AND (assistant_id = %s OR worldbook_id = %s)
                      AND character_ids && %s::text[]
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_scope, assistant_id, session.worldbookId, session.characterIds, max(limit * 4, limit)),
                )
                rows = cur.fetchall()
    except Exception:
        return []

    return _dedupe_long_memory_items([_row_to_item(row, location_labels) for row in rows], limit=limit)


def _fetch_vector_rows(
    session: GameSession,
    responder_id: str,
    vector_literal: str,
    candidate_k: int,
) -> list[tuple]:
    assistant_id = _session_assistant_id(session)
    user_scope = _session_user_scope(session)
    sql = """
        SELECT
          id,
          session_id,
          responder_id,
          character_ids,
          location_id,
          memory_type,
          summary,
          created_at,
          importance,
          salience,
          trigger_hints,
          1 - (embedding <=> %s::vector) AS score
        FROM game_memories
        WHERE user_scope = %s
          AND (assistant_id = %s OR worldbook_id = %s)
          AND session_id <> %s
          AND embedding IS NOT NULL
          AND (responder_id = %s OR character_ids && %s::text[])
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    vector_literal,
                    user_scope,
                    assistant_id,
                    session.worldbookId,
                    session.id,
                    responder_id,
                    session.characterIds,
                    vector_literal,
                    candidate_k,
                ),
            )
            return cur.fetchall()


def _fetch_keyword_rows(
    session: GameSession,
    player_message: str,
    responder_id: str,
    candidate_k: int,
) -> list[tuple]:
    assistant_id = _session_assistant_id(session)
    user_scope = _session_user_scope(session)
    terms = _keyword_terms(player_message)
    where_parts: list[str] = []
    params: list[object] = []

    for term in terms:
        pattern = f'%{term}%'
        where_parts.append("(summary ILIKE %s OR retrieval_text ILIKE %s)")
        params.extend([pattern, pattern])

    keyword_filter = "similarity(COALESCE(summary, ''), %s) > 0.08 OR similarity(COALESCE(retrieval_text, ''), %s) > 0.08"
    params.extend([player_message, player_message])

    if where_parts:
        keyword_filter = f"(({' OR '.join(where_parts)}) OR {keyword_filter})"

    sql = f"""
        SELECT
          id,
          session_id,
          responder_id,
          character_ids,
          location_id,
          memory_type,
          summary,
          created_at,
          importance,
          salience,
          trigger_hints,
          (
            0.40 * similarity(COALESCE(summary, ''), %s)
            + 0.60 * similarity(COALESCE(retrieval_text, ''), %s)
          ) AS score
        FROM game_memories
        WHERE user_scope = %s
          AND (assistant_id = %s OR worldbook_id = %s)
          AND session_id <> %s
          AND (responder_id = %s OR character_ids && %s::text[])
          AND {keyword_filter}
        ORDER BY score DESC, created_at DESC
        LIMIT %s
    """

    exec_params: list[object] = [
        player_message,
        player_message,
        user_scope,
        assistant_id,
        session.worldbookId,
        session.id,
        responder_id,
        session.characterIds,
        *params,
        candidate_k,
    ]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(exec_params))
            return cur.fetchall()


def _merge_candidate_rows(
    vector_rows: list[tuple],
    keyword_rows: list[tuple],
    player_message: str,
    current_location_id: str,
    responder_id: str,
    location_labels: dict[str, str],
) -> list[dict]:
    merged: dict[str, dict] = {}

    def upsert(row: tuple, source: str) -> None:
        (
            memory_id,
            session_id,
            row_responder_id,
            character_ids,
            location_id,
            memory_type,
            summary,
            created_at,
            importance,
            salience,
            trigger_hints,
            score,
        ) = row
        current = merged.get(memory_id)
        if current is None:
            current = {
                'row': (
                    memory_id,
                    session_id,
                    row_responder_id,
                    character_ids,
                    location_id,
                    memory_type,
                    summary,
                    created_at,
                    importance,
                    salience,
                ),
                'triggerHints': list(trigger_hints or []),
                'vectorScore': 0.0,
                'keywordScore': 0.0,
            }
            merged[memory_id] = current

        if source == 'vector':
            current['vectorScore'] = max(float(current['vectorScore']), float(score or 0.0))
        else:
            current['keywordScore'] = max(float(current['keywordScore']), float(score or 0.0))

    for row in vector_rows:
        upsert(row, 'vector')
    for row in keyword_rows:
        upsert(row, 'keyword')

    ranked: list[dict] = []
    for candidate in merged.values():
        memory_id, session_id, row_responder_id, character_ids, location_id, memory_type, summary, created_at, importance, salience = candidate['row']
        trigger_hints = list(candidate['triggerHints'])
        local_score = 0.55 * float(candidate['vectorScore']) + 0.20 * float(candidate['keywordScore'])
        if row_responder_id == responder_id:
            local_score += 0.15
        if location_id and location_id == current_location_id:
            local_score += 0.10
        if trigger_hints and any(_contains_term(player_message, hint) for hint in trigger_hints):
            local_score += 0.05

        ranked.append(
            {
                'score': local_score,
                'item': LongMemoryItem(
                    id=memory_id,
                    sessionId=session_id,
                    responderId=row_responder_id,
                    characterIds=list(character_ids or []),
                    locationId=location_id,
                    memoryType=memory_type,
                    retrievalSummary=summary,
                    displaySummary=_display_summary_from_retrieval(summary, memory_type, location_id, location_labels),
                    createdAt=_from_db_timestamp(created_at) or '',
                    importance=float(importance or 0.0),
                    salience=float(salience or 0.0),
                ),
            }
        )

    ranked.sort(key=lambda row: row['score'], reverse=True)
    return ranked


def touch_long_memory_items(memory_ids: list[str]) -> None:
    if not memory_ids:
        return

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE game_memories
                    SET last_used_at = NOW()
                    WHERE id = ANY(%s::text[])
                    """,
                    (memory_ids,),
                )
            conn.commit()
    except Exception:
        return


def select_long_term_memories(
    session: GameSession,
    player_message: str,
    current_location_id: str,
    responder_id: str,
    limit: int = 3,
) -> list[LongMemoryItem]:
    vector_rows: list[tuple] = []
    try:
        vector_literal = vector_to_pg(embed_query(player_message))
        vector_rows = _fetch_vector_rows(session, responder_id, vector_literal, LONG_MEMORY_CANDIDATE_K)
    except Exception:
        vector_rows = []

    try:
        keyword_rows = _fetch_keyword_rows(session, player_message, responder_id, LONG_MEMORY_CANDIDATE_K)
    except Exception:
        keyword_rows = []
    ranked = _merge_candidate_rows(
        vector_rows,
        keyword_rows,
        player_message,
        current_location_id,
        responder_id,
        _location_labels(session.worldbookId),
    )
    items = _dedupe_long_memory_items([row['item'] for row in ranked], limit=limit)
    touch_long_memory_items([item.id for item in items])
    return items


def build_long_memory_state(
    session: GameSession,
    selected_items: list[LongMemoryItem] | None = None,
    archive_summary: ArchivePromotionSummary | None = None,
) -> LongMemoryState:
    return LongMemoryState(
        profiles=load_long_memory_profiles(session),
        recentItems=list_recent_long_memory_items(session),
        selectedItems=selected_items or [],
        archivePromotion=archive_summary,
    )
