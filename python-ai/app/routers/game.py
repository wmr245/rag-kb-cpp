from fastapi import APIRouter, HTTPException, Query

from app.core.config import GAME_TESTING_API_ENABLED
from app.models.game_schemas import (
    Assistant,
    AssistantCreateRequest,
    AssistantFixtureResetRequest,
    AssistantFixtureResetResponse,
    AssistantListResponse,
    AssistantUpdateRequest,
    CharacterCard,
    CharacterCardCreateRequest,
    CharacterCardListResponse,
    GameSessionDeleteResponse,
    GameSessionCreateRequest,
    GameSessionListResponse,
    GameSessionStateResponse,
    GameSessionUpdateRequest,
    GameTurnRequest,
    GameTurnResponse,
    Worldbook,
    WorldbookCreateRequest,
    WorldbookListResponse,
)
from app.services.assistant_fixture_service import reset_assistant_fixture
from app.services.assistant_service import create_assistant, get_assistant, list_assistants, update_assistant
from app.services.character_card_service import create_character_card, get_character_card, list_character_cards
from app.services.game_exceptions import GameConflictError, GameNotFoundError, GameValidationError
from app.services.game_session_service import (
    create_game_session,
    delete_game_session,
    get_game_session,
    list_game_sessions,
    play_turn,
    update_game_session,
)
from app.services.long_memory_service import build_long_memory_state
from app.services.scene_resolver_service import build_scene_snapshot
from app.services.worldbook_service import create_worldbook, get_worldbook, list_worldbooks

router = APIRouter(prefix='/game', tags=['game'])


def _raise_http_error(exc: Exception) -> None:
    if isinstance(exc, GameNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, GameConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, GameValidationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail='unexpected game service error') from exc


@router.post('/worldbooks', response_model=Worldbook)
def create_worldbook_endpoint(req: WorldbookCreateRequest):
    try:
        return create_worldbook(req.worldbook)
    except Exception as exc:
        _raise_http_error(exc)


@router.get('/worldbooks', response_model=WorldbookListResponse)
def list_worldbooks_endpoint():
    try:
        return WorldbookListResponse(items=list_worldbooks())
    except Exception as exc:
        _raise_http_error(exc)


@router.get('/worldbooks/{worldbook_id}', response_model=Worldbook)
def get_worldbook_endpoint(worldbook_id: str):
    try:
        return get_worldbook(worldbook_id)
    except Exception as exc:
        _raise_http_error(exc)


@router.post('/character-cards', response_model=CharacterCard)
def create_character_card_endpoint(req: CharacterCardCreateRequest):
    try:
        return create_character_card(req.characterCard)
    except Exception as exc:
        _raise_http_error(exc)


@router.get('/character-cards', response_model=CharacterCardListResponse)
def list_character_cards_endpoint(worldbookId: str | None = Query(default=None)):
    try:
        return CharacterCardListResponse(items=list_character_cards(worldbookId))
    except Exception as exc:
        _raise_http_error(exc)


@router.get('/character-cards/{character_id}', response_model=CharacterCard)
def get_character_card_endpoint(character_id: str):
    try:
        return get_character_card(character_id)
    except Exception as exc:
        _raise_http_error(exc)


@router.post('/assistants', response_model=Assistant)
def create_assistant_endpoint(req: AssistantCreateRequest):
    try:
        return create_assistant(req)
    except Exception as exc:
        _raise_http_error(exc)


@router.get('/assistants', response_model=AssistantListResponse)
def list_assistants_endpoint():
    try:
        return AssistantListResponse(items=list_assistants())
    except Exception as exc:
        _raise_http_error(exc)


@router.get('/assistants/{assistant_id}', response_model=Assistant)
def get_assistant_endpoint(assistant_id: str):
    try:
        return get_assistant(assistant_id)
    except Exception as exc:
        _raise_http_error(exc)


@router.patch('/assistants/{assistant_id}', response_model=Assistant)
def update_assistant_endpoint(assistant_id: str, req: AssistantUpdateRequest):
    try:
        return update_assistant(assistant_id, name=req.name, status=req.status, summary=req.summary)
    except Exception as exc:
        _raise_http_error(exc)


@router.post('/testing/reset-assistant-fixture', response_model=AssistantFixtureResetResponse)
def reset_assistant_fixture_endpoint(req: AssistantFixtureResetRequest):
    if not GAME_TESTING_API_ENABLED:
        raise HTTPException(status_code=404, detail='not found')
    try:
        return reset_assistant_fixture(req)
    except Exception as exc:
        _raise_http_error(exc)


@router.post('/sessions', response_model=GameSessionStateResponse)
def create_game_session_endpoint(req: GameSessionCreateRequest):
    try:
        session = create_game_session(req)
        worldbook = get_worldbook(session.worldbookId)
        characters = [get_character_card(character_id) for character_id in session.characterIds]
        scene = build_scene_snapshot(worldbook, characters, session)
        return GameSessionStateResponse(session=session, scene=scene, longMemory=build_long_memory_state(session))
    except Exception as exc:
        _raise_http_error(exc)


@router.get('/sessions', response_model=GameSessionListResponse)
def list_game_sessions_endpoint(assistantId: str | None = Query(default=None)):
    try:
        return GameSessionListResponse(items=list_game_sessions(assistantId or ''))
    except Exception as exc:
        _raise_http_error(exc)


@router.get('/sessions/{session_id}', response_model=GameSessionStateResponse)
def get_game_session_endpoint(session_id: str):
    try:
        session = get_game_session(session_id)
        worldbook = get_worldbook(session.worldbookId)
        characters = [get_character_card(character_id) for character_id in session.characterIds]
        scene = build_scene_snapshot(worldbook, characters, session)
        return GameSessionStateResponse(session=session, scene=scene, longMemory=build_long_memory_state(session))
    except Exception as exc:
        _raise_http_error(exc)


@router.patch('/sessions/{session_id}', response_model=GameSessionStateResponse)
def update_game_session_endpoint(session_id: str, req: GameSessionUpdateRequest):
    try:
        session, archive_summary = update_game_session(session_id, req)
        worldbook = get_worldbook(session.worldbookId)
        characters = [get_character_card(character_id) for character_id in session.characterIds]
        scene = build_scene_snapshot(worldbook, characters, session)
        return GameSessionStateResponse(
            session=session,
            scene=scene,
            longMemory=build_long_memory_state(session, archive_summary=archive_summary),
        )
    except Exception as exc:
        _raise_http_error(exc)


@router.delete('/sessions/{session_id}', response_model=GameSessionDeleteResponse)
def delete_game_session_endpoint(session_id: str):
    try:
        session = delete_game_session(session_id)
        return GameSessionDeleteResponse(deleted=True, sessionId=session.id, title=session.title)
    except Exception as exc:
        _raise_http_error(exc)


@router.post('/sessions/{session_id}/turns', response_model=GameTurnResponse)
def play_turn_endpoint(session_id: str, req: GameTurnRequest):
    try:
        session, result, debug, selected_long_memory_items = play_turn(session_id, req.message)
        worldbook = get_worldbook(session.worldbookId)
        characters = [get_character_card(character_id) for character_id in session.characterIds]
        scene = build_scene_snapshot(worldbook, characters, session)
        return GameTurnResponse(
            acknowledged=True,
            session=session,
            scene=scene,
            longMemory=build_long_memory_state(session, selected_items=selected_long_memory_items),
            result=result,
            debug=debug,
        )
    except Exception as exc:
        _raise_http_error(exc)
