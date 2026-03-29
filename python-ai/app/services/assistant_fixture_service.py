from app.models.game_schemas import (
    Assistant,
    AssistantFixtureResetRequest,
    AssistantFixtureResetResponse,
    CharacterCard,
    GameSession,
)
from app.services.assistant_service import build_assistant_id, resolve_session_assistant_id
from app.services.game_exceptions import GameValidationError
from app.services.game_storage_service import delete_record, list_records, load_record, save_record
from app.services.game_utils import dump_model, utc_now_iso
from app.db.postgres import get_conn


LEGACY_ASSISTANT_PREFIX = 'assistant:assistant_reg_'
LEGACY_CHARACTER_PREFIX = 'assistant_reg_'


def _collect_legacy_generated_ids() -> tuple[set[str], set[str]]:
    assistant_ids: set[str] = set()
    character_ids: set[str] = set()

    for payload in list_records('assistants'):
        assistant = Assistant.model_validate(payload)
        if assistant.id.startswith(LEGACY_ASSISTANT_PREFIX) or assistant.characterId.startswith(LEGACY_CHARACTER_PREFIX):
            assistant_ids.add(assistant.id)
            character_ids.add(assistant.characterId)

    for payload in list_records('character_cards'):
        character = CharacterCard.model_validate(payload)
        if character.id.startswith(LEGACY_CHARACTER_PREFIX):
            character_ids.add(character.id)
            assistant_ids.add(build_assistant_id(character.id))

    return assistant_ids, character_ids


def _matching_sessions(assistant_ids: set[str], character_ids: set[str]) -> list[GameSession]:
    rows: list[GameSession] = []
    for payload in list_records('sessions'):
        session = GameSession.model_validate(payload)
        session_assistant_id = resolve_session_assistant_id(session)
        if session.assistantId in assistant_ids or session_assistant_id in assistant_ids:
            rows.append(session)
            continue
        if any(character_id in character_ids for character_id in session.characterIds):
            rows.append(session)
    return rows


def _delete_file_records(kind: str, record_ids: set[str]) -> int:
    deleted = 0
    for record_id in sorted(record_ids):
        if load_record(kind, record_id) is None:
            continue
        delete_record(kind, record_id)
        deleted += 1
    return deleted


def _delete_memory_rows(session_ids: list[str], assistant_ids: list[str], character_ids: list[str]) -> tuple[int, int]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM game_memories
                WHERE session_id = ANY(%s::text[])
                   OR assistant_id = ANY(%s::text[])
                   OR responder_id = ANY(%s::text[])
                   OR character_ids && %s::text[]
                """,
                (session_ids, assistant_ids, character_ids, character_ids),
            )
            deleted_memories = cur.rowcount

            cur.execute(
                """
                DELETE FROM game_memory_profiles
                WHERE assistant_id = ANY(%s::text[])
                   OR character_id = ANY(%s::text[])
                """,
                (assistant_ids, character_ids),
            )
            deleted_profiles = cur.rowcount

        conn.commit()

    return deleted_memories, deleted_profiles


def _reset_fixture_assistant_state(assistant_id: str) -> None:
    payload = load_record('assistants', assistant_id)
    if payload is None:
        return

    assistant = Assistant.model_validate(payload)
    assistant.memoryStatus = 'empty'
    assistant.status = 'active'
    assistant.updatedAt = utc_now_iso()
    save_record('assistants', assistant.id, dump_model(assistant))


def reset_assistant_fixture(req: AssistantFixtureResetRequest) -> AssistantFixtureResetResponse:
    assistant_id = req.assistantId.strip()
    character_id = req.characterId.strip()
    if not assistant_id or not character_id:
        raise GameValidationError('assistantId and characterId are required')
    if assistant_id != build_assistant_id(character_id):
        raise GameValidationError('assistantId must match characterId')

    reused_fixture = bool(load_record('assistants', assistant_id) or load_record('character_cards', character_id))

    cleanup_assistant_ids: set[str] = {assistant_id}
    cleanup_character_ids: set[str] = {character_id}
    legacy_assistant_ids: set[str] = set()
    legacy_character_ids: set[str] = set()

    if req.purgeLegacyGeneratedData:
        legacy_assistant_ids, legacy_character_ids = _collect_legacy_generated_ids()
        cleanup_assistant_ids.update(legacy_assistant_ids)
        cleanup_character_ids.update(legacy_character_ids)

    sessions = _matching_sessions(cleanup_assistant_ids, cleanup_character_ids)
    session_ids = [session.id for session in sessions]

    deleted_memories, deleted_profiles = _delete_memory_rows(
        session_ids,
        sorted(cleanup_assistant_ids),
        sorted(cleanup_character_ids),
    )

    deleted_sessions = _delete_file_records('sessions', set(session_ids))
    deleted_assistants = _delete_file_records('assistants', legacy_assistant_ids)
    deleted_characters = _delete_file_records('character_cards', legacy_character_ids)

    _reset_fixture_assistant_state(assistant_id)

    return AssistantFixtureResetResponse(
        deletedAssistants=deleted_assistants,
        deletedCharacters=deleted_characters,
        deletedSessions=deleted_sessions,
        deletedMemories=deleted_memories,
        deletedProfiles=deleted_profiles,
        reusedFixture=reused_fixture,
    )
