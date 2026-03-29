from datetime import datetime

from app.models.game_schemas import Assistant, AssistantCreateRequest, AssistantSummary, CharacterCard, GameSession, Worldbook
from app.services.game_exceptions import GameConflictError, GameNotFoundError, GameValidationError
from app.services.game_storage_service import list_records, load_record, save_record
from app.services.game_utils import dump_model, utc_now_iso
from app.services.character_card_service import get_character_card
from app.services.worldbook_service import get_worldbook


DEFAULT_USER_SCOPE = 'default_player'


def build_assistant_id(character_id: str) -> str:
    return f'assistant:{character_id}'


def resolve_session_assistant_id(session: GameSession) -> str:
    if session.assistantId.strip():
        return session.assistantId.strip()
    if session.characterIds:
        return build_assistant_id(session.characterIds[0])
    return ''


def _load_assistant_record(assistant_id: str) -> Assistant | None:
    payload = load_record('assistants', assistant_id)
    if payload is None:
        return None
    return Assistant.model_validate(payload)


def _all_sessions() -> list[GameSession]:
    return [GameSession.model_validate(payload) for payload in list_records('sessions')]


def _assistant_sessions(assistant: Assistant) -> list[GameSession]:
    rows: list[GameSession] = []
    for session in _all_sessions():
        session_assistant_id = resolve_session_assistant_id(session)
        if session_assistant_id == assistant.id:
            rows.append(session)
            continue
        if not session_assistant_id and session.worldbookId == assistant.worldbookId and assistant.characterId in session.characterIds:
            rows.append(session)
    rows.sort(key=lambda row: row.updatedAt, reverse=True)
    return rows


def _status_rank(status: str) -> int:
    if status == 'active':
        return 0
    if status == 'draft':
        return 1
    return 2


def _sort_timestamp(value: str) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
    except ValueError:
        return 0.0


def _fallback_summary(card: CharacterCard) -> str:
    return ' · '.join(card.personaTags[:3]) or card.role or '等待补充助手摘要'


def _materialize_projected_assistant(character: CharacterCard, worldbook: Worldbook) -> Assistant:
    sessions = [
        session for session in _all_sessions()
        if session.worldbookId == worldbook.id and character.id in session.characterIds
    ]
    sessions.sort(key=lambda row: row.updatedAt, reverse=True)
    recent_session = sessions[0] if sessions else None
    status = 'active' if any(session.status == 'active' for session in sessions) else ('archived' if sessions else 'draft')
    memory_status = 'ready' if sessions else 'empty'
    timestamp = recent_session.updatedAt if recent_session else ''
    return Assistant(
        id=build_assistant_id(character.id),
        name=character.name,
        worldbookId=worldbook.id,
        characterId=character.id,
        userScope=DEFAULT_USER_SCOPE,
        status=status,
        memoryStatus=memory_status,
        summary=_fallback_summary(character),
        createdAt=timestamp,
        updatedAt=timestamp,
    )


def _summary_from_assistant(assistant: Assistant, character: CharacterCard, worldbook: Worldbook, source: str) -> AssistantSummary:
    sessions = _assistant_sessions(assistant)
    active_session_count = sum(1 for session in sessions if session.status == 'active')
    archived_session_count = sum(1 for session in sessions if session.status == 'archived')
    recent_session = sessions[0] if sessions else None
    memory_status = assistant.memoryStatus
    if sessions and memory_status == 'empty':
        memory_status = 'ready'
    if not sessions and source == 'projected_character':
        memory_status = 'empty'

    return AssistantSummary(
        id=assistant.id,
        source=source,
        name=assistant.name,
        worldbookId=assistant.worldbookId,
        worldbookTitle=worldbook.title,
        characterId=assistant.characterId,
        characterRole=character.role,
        personaTags=character.personaTags,
        userScope=assistant.userScope,
        status=assistant.status,
        memoryStatus=memory_status,
        summary=assistant.summary or _fallback_summary(character),
        updatedAt=recent_session.updatedAt if recent_session else assistant.updatedAt,
        sessionCount=len(sessions),
        activeSessionCount=active_session_count,
        archivedSessionCount=archived_session_count,
        recentSessionId=recent_session.id if recent_session else '',
    )


def _validate_assistant_binding(worldbook: Worldbook, character: CharacterCard) -> None:
    if character.worldbookId != worldbook.id:
        raise GameValidationError(f'character {character.id} does not belong to worldbook {worldbook.id}')


def list_assistants() -> list[AssistantSummary]:
    worldbooks = {
        worldbook.id: worldbook
        for worldbook in (Worldbook.model_validate(row) for row in list_records('worldbooks'))
    }
    characters = {
        character.id: character
        for character in (CharacterCard.model_validate(row) for row in list_records('character_cards'))
    }
    stored = {
        assistant.id: assistant
        for assistant in (Assistant.model_validate(row) for row in list_records('assistants'))
    }

    rows: list[AssistantSummary] = []
    for assistant in stored.values():
        character = characters.get(assistant.characterId)
        worldbook = worldbooks.get(assistant.worldbookId)
        if character is None or worldbook is None:
            continue
        rows.append(_summary_from_assistant(assistant, character, worldbook, 'assistant'))

    for character in characters.values():
        assistant_id = build_assistant_id(character.id)
        if assistant_id in stored:
            continue
        worldbook = worldbooks.get(character.worldbookId)
        if worldbook is None:
            continue
        projected = _materialize_projected_assistant(character, worldbook)
        rows.append(_summary_from_assistant(projected, character, worldbook, 'projected_character'))

    return sorted(
        rows,
        key=lambda row: (_status_rank(row.status), -_sort_timestamp(row.updatedAt), row.name),
    )


def get_assistant(assistant_id: str) -> Assistant:
    stored = _load_assistant_record(assistant_id)
    if stored is not None:
        return stored

    if not assistant_id.startswith('assistant:'):
        raise GameNotFoundError(f'assistant not found: {assistant_id}')

    character_id = assistant_id.split(':', 1)[1].strip()
    if not character_id:
        raise GameNotFoundError(f'assistant not found: {assistant_id}')
    character = get_character_card(character_id)
    worldbook = get_worldbook(character.worldbookId)
    return _materialize_projected_assistant(character, worldbook)


def create_assistant(req: AssistantCreateRequest) -> Assistant:
    worldbook = get_worldbook(req.worldbookId)
    character = get_character_card(req.characterId)
    _validate_assistant_binding(worldbook, character)

    assistant_id = build_assistant_id(character.id)
    if _load_assistant_record(assistant_id) is not None:
        raise GameConflictError(f'assistant already exists: {assistant_id}')

    now = utc_now_iso()
    projected = _materialize_projected_assistant(character, worldbook)
    assistant = Assistant(
        id=assistant_id,
        name=req.name.strip() or character.name,
        worldbookId=worldbook.id,
        characterId=character.id,
        userScope=req.userScope.strip() or DEFAULT_USER_SCOPE,
        status=req.status,
        memoryStatus=projected.memoryStatus,
        summary=req.summary.strip() or _fallback_summary(character),
        createdAt=now,
        updatedAt=projected.updatedAt or now,
    )
    save_record('assistants', assistant.id, dump_model(assistant))
    return assistant


def update_assistant(assistant_id: str, name: str = '', status: str = '', summary: str = '') -> Assistant:
    try:
        assistant = get_assistant(assistant_id)
    except GameNotFoundError:
        raise

    stored = _load_assistant_record(assistant_id)
    if stored is None:
        stored = assistant
        if not stored.createdAt:
            stored.createdAt = utc_now_iso()

    if name.strip():
        stored.name = name.strip()
    if summary.strip():
        stored.summary = summary.strip()
    if status.strip():
        if status.strip() not in {'draft', 'active', 'archived'}:
            raise GameValidationError(f'unsupported assistant status: {status}')
        stored.status = status.strip()

    stored.updatedAt = utc_now_iso()
    save_record('assistants', stored.id, dump_model(stored))
    return stored
