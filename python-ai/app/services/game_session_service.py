from app.models.game_schemas import (
    CharacterCard,
    GameSession,
    GameSessionCreateRequest,
    GameSessionSummary,
    GameSessionUpdateRequest,
    GameTurnDebug,
    GameTurnResult,
    MemoryProfile,
    PresentedTurn,
    RelationshipState,
    RuntimeState,
)
from app.services.character_card_service import get_character_card
from app.services.character_response_service import generate_character_response
from app.services.director_agent_service import build_turn_plan
from app.services.game_exceptions import GameConflictError, GameNotFoundError, GameValidationError
from app.services.game_storage_service import list_records, load_record, save_record
from app.services.game_utils import dump_model, new_id, utc_now_iso
from app.services.memory_retrieval_service import build_memory_digest, build_recent_turn_digest, select_relevant_memories
from app.services.state_update_service import apply_turn_result, build_state_diff, snapshot_turn_state
from app.services.worldbook_service import get_worldbook


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        rows.append(item)
    return rows


def _initial_relationship_state(card: CharacterCard) -> RelationshipState:
    defaults = card.relationshipDefaults
    return RelationshipState(
        trust=defaults.trust,
        affection=defaults.affection,
        tension=defaults.tension,
        familiarity=defaults.familiarity,
        stage=defaults.stage,
        unlockedSecrets=[],
    )


def _initial_memory_profile(card: CharacterCard) -> MemoryProfile:
    return MemoryProfile(
        characterId=card.id,
        playerImageSummary='',
        relationshipSummary=f'Current relationship stage: {card.relationshipDefaults.stage}.',
        openThreads=[],
        preferredInteractionPatterns=card.softSpots[:3],
        avoidPatterns=card.tabooTopics[:3],
    )


def _select_initial_location(worldbook, opening_location_id: str) -> str:
    if opening_location_id:
        valid_location_ids = {row.id for row in worldbook.locations}
        if opening_location_id not in valid_location_ids:
            raise GameValidationError(f'openingLocationId not found in worldbook: {opening_location_id}')
        return opening_location_id
    if worldbook.locations:
        return worldbook.locations[0].id
    return 'opening_scene'


def _select_initial_cast(cards: list[CharacterCard], location_id: str) -> list[str]:
    preferred = [card.id for card in cards if location_id in card.scenePreferences]
    if preferred:
        return preferred[:2]
    return [card.id for card in cards[:2]]


def _resolve_actor_name(actor_type: str, actor_id: str, characters_by_id: dict[str, CharacterCard]) -> str:
    if actor_type == 'player':
        return '玩家'
    if actor_type == 'director':
        return '导演'
    character = characters_by_id.get(actor_id)
    return character.name if character else actor_id


def create_game_session(req: GameSessionCreateRequest) -> GameSession:
    if not req.characterIds:
        raise GameValidationError('characterIds must not be empty')

    worldbook = get_worldbook(req.worldbookId)
    character_ids = _dedupe_preserve(req.characterIds)
    characters = [get_character_card(character_id) for character_id in character_ids]

    mismatched = [card.id for card in characters if card.worldbookId != worldbook.id]
    if mismatched:
        raise GameValidationError(f'character cards do not belong to worldbook {worldbook.id}: {mismatched}')

    location_id = _select_initial_location(worldbook, req.openingLocationId)
    current_cast = _select_initial_cast(characters, location_id)
    now = utc_now_iso()

    runtime_state = RuntimeState(
        currentSceneId=f'{location_id}:opening',
        currentLocationId=location_id,
        timeBlock='opening',
        dayIndex=1,
        currentCast=current_cast,
        worldFlags={},
        activeEvents=[],
        completedEvents=[],
        relationshipStates={card.id: _initial_relationship_state(card) for card in characters},
    )

    session = GameSession(
        id=new_id('sess'),
        worldbookId=worldbook.id,
        characterIds=character_ids,
        title=req.title or worldbook.title,
        status='active',
        createdAt=now,
        updatedAt=now,
        runtimeState=runtime_state,
        recentTurns=[],
        memoryEntries=[],
        memoryProfiles={card.id: _initial_memory_profile(card) for card in characters},
    )
    if load_record('sessions', session.id) is not None:
        raise GameConflictError(f'session already exists: {session.id}')
    save_record('sessions', session.id, dump_model(session))
    return session


def get_game_session(session_id: str) -> GameSession:
    payload = load_record('sessions', session_id)
    if payload is None:
        raise GameNotFoundError(f'game session not found: {session_id}')
    return GameSession.model_validate(payload)


def list_game_sessions() -> list[GameSessionSummary]:
    rows = [GameSession.model_validate(payload) for payload in list_records('sessions')]
    rows.sort(key=lambda row: row.updatedAt, reverse=True)
    return [
        GameSessionSummary(
            id=row.id,
            worldbookId=row.worldbookId,
            title=row.title,
            status=row.status,
            characterIds=row.characterIds,
            updatedAt=row.updatedAt,
            currentLocationId=row.runtimeState.currentLocationId,
            currentCast=row.runtimeState.currentCast,
        )
        for row in rows
    ]


def update_game_session(session_id: str, req: GameSessionUpdateRequest) -> GameSession:
    session = get_game_session(session_id)
    next_title = req.title.strip()
    next_status = req.status.strip()

    if next_title:
        session.title = next_title

    if next_status:
        if next_status not in {'active', 'archived'}:
            raise GameValidationError(f'unsupported session status: {next_status}')
        session.status = next_status

    session.updatedAt = utc_now_iso()
    save_record('sessions', session.id, dump_model(session))
    return session


def play_turn(session_id: str, message: str) -> tuple[GameSession, GameTurnResult, GameTurnDebug]:
    session = get_game_session(session_id)
    if session.status != 'active':
        raise GameValidationError('archived session cannot accept new turns')
    before_state = snapshot_turn_state(session)
    worldbook = get_worldbook(session.worldbookId)
    characters = [get_character_card(character_id) for character_id in session.characterIds]
    characters_by_id = {card.id: card for card in characters}

    preliminary_plan = build_turn_plan(
        worldbook,
        characters,
        session,
        message,
        relevant_memory_summaries=[],
    )
    relevant_memories = select_relevant_memories(
        session,
        message,
        preliminary_plan['targetLocationId'],
        preliminary_plan['responderId'],
        limit=3,
    )
    relevant_memory_summaries = build_memory_digest(relevant_memories)
    recent_turn_digest = build_recent_turn_digest(session)
    final_plan = build_turn_plan(
        worldbook,
        characters,
        session,
        message,
        relevant_memory_summaries=relevant_memory_summaries,
    )

    responder = characters_by_id[final_plan['responderId']]
    character_reply = generate_character_response(
        worldbook,
        responder,
        session,
        final_plan,
        message,
        recent_turn_digest,
        relevant_memory_summaries,
    )

    session, appended_turns = apply_turn_result(
        session,
        worldbook,
        responder,
        final_plan,
        message,
        character_reply,
    )
    state_diff = build_state_diff(before_state, session)
    save_record('sessions', session.id, dump_model(session))

    result = GameTurnResult(
        responderId=responder.id,
        responderName=responder.name,
        sceneGoal=final_plan['sceneGoal'],
        eventSeed=final_plan.get('eventSeed'),
        turns=[
            PresentedTurn(
                turnId=turn.turnId,
                actorType=turn.actorType,
                actorId=turn.actorId,
                actorName=_resolve_actor_name(turn.actorType, turn.actorId, characters_by_id),
                text=turn.text,
                sceneId=turn.sceneId,
                createdAt=turn.createdAt,
            )
            for turn in appended_turns
        ],
        primaryReply=character_reply,
        stateDiff=state_diff,
    )
    debug = GameTurnDebug(
        targetLocationId=final_plan['targetLocationId'],
        sceneId=final_plan['sceneId'],
        selectedMemorySummaries=relevant_memory_summaries,
        recentTurnDigest=recent_turn_digest,
        directorNote=final_plan.get('directorNote', ''),
        characterReply=character_reply,
    )
    return session, result, debug
