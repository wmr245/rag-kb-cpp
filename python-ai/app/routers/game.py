from fastapi import APIRouter, HTTPException, Query

from app.models.game_schemas import (
    CharacterCard,
    CharacterCardCreateRequest,
    CharacterCardListResponse,
    GameSessionCreateRequest,
    GameSessionListResponse,
    GameSessionStateResponse,
    GameTurnRequest,
    GameTurnResponse,
    Worldbook,
    WorldbookCreateRequest,
    WorldbookListResponse,
)
from app.services.character_card_service import create_character_card, get_character_card, list_character_cards
from app.services.game_exceptions import GameConflictError, GameNotFoundError, GameValidationError
from app.services.game_session_service import create_game_session, get_game_session, list_game_sessions, play_turn
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


@router.post('/sessions', response_model=GameSessionStateResponse)
def create_game_session_endpoint(req: GameSessionCreateRequest):
    try:
        session = create_game_session(req)
        worldbook = get_worldbook(session.worldbookId)
        characters = [get_character_card(character_id) for character_id in session.characterIds]
        scene = build_scene_snapshot(worldbook, characters, session)
        return GameSessionStateResponse(session=session, scene=scene)
    except Exception as exc:
        _raise_http_error(exc)


@router.get('/sessions', response_model=GameSessionListResponse)
def list_game_sessions_endpoint():
    try:
        return GameSessionListResponse(items=list_game_sessions())
    except Exception as exc:
        _raise_http_error(exc)


@router.get('/sessions/{session_id}', response_model=GameSessionStateResponse)
def get_game_session_endpoint(session_id: str):
    try:
        session = get_game_session(session_id)
        worldbook = get_worldbook(session.worldbookId)
        characters = [get_character_card(character_id) for character_id in session.characterIds]
        scene = build_scene_snapshot(worldbook, characters, session)
        return GameSessionStateResponse(session=session, scene=scene)
    except Exception as exc:
        _raise_http_error(exc)


@router.post('/sessions/{session_id}/turns', response_model=GameTurnResponse)
def play_turn_endpoint(session_id: str, req: GameTurnRequest):
    try:
        session, result, debug = play_turn(session_id, req.message)
        worldbook = get_worldbook(session.worldbookId)
        characters = [get_character_card(character_id) for character_id in session.characterIds]
        scene = build_scene_snapshot(worldbook, characters, session)
        return GameTurnResponse(acknowledged=True, session=session, scene=scene, result=result, debug=debug)
    except Exception as exc:
        _raise_http_error(exc)
