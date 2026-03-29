from app.models.game_schemas import CharacterCard, GameSession, Worldbook


TIME_BLOCKS = ['opening', 'afternoon', 'evening', 'night']


def _contains_term(text: str, term: str) -> bool:
    return (term or '').strip().lower() in (text or '').lower()


def _resolve_requested_location(worldbook: Worldbook, player_message: str) -> str | None:
    for location in worldbook.locations:
        if _contains_term(player_message, location.id) or _contains_term(player_message, location.name):
            return location.id
        for tag in location.tags + location.sceneHints:
            if len(tag) >= 2 and _contains_term(player_message, tag):
                return location.id
    return None


def _select_cast_for_location(characters: list[CharacterCard], location_id: str, current_cast: list[str]) -> list[str]:
    preferred = [card.id for card in characters if location_id in card.scenePreferences]
    if preferred:
        return preferred[:2]
    if current_cast:
        return current_cast[:2]
    return [card.id for card in characters[:2]]


def _pick_responder(player_message: str, characters: list[CharacterCard], cast_ids: list[str], session: GameSession) -> str:
    for card in characters:
        if card.id in cast_ids and _contains_term(player_message, card.name):
            return card.id

    def affinity(card_id: str) -> int:
        relation = session.runtimeState.relationshipStates.get(card_id)
        if relation is None:
            return 0
        return relation.trust + relation.affection - relation.tension

    ordered = sorted(cast_ids, key=affinity, reverse=True)
    return ordered[0] if ordered else characters[0].id


def _pick_event_seed(worldbook: Worldbook, player_message: str, location_id: str) -> str | None:
    if not worldbook.eventSeeds:
        return None
    for event_seed in worldbook.eventSeeds:
        if any(_contains_term(player_message, token) for token in [event_seed, '雨', '情书', '误会', '告白']):
            return event_seed
    return None


def _scene_goal(player_message: str) -> str:
    if any(token in player_message for token in ['秘密', '情书', '真相', '调查']):
        return 'investigate'
    if any(token in player_message for token in ['陪', '一起', '散步', '聊聊']):
        return 'bond'
    if any(token in player_message for token in ['对不起', '抱歉', '误会']):
        return 'repair'
    return 'continue_scene'


def _next_time_block(current: str, turn_count: int) -> str:
    if turn_count <= 0 or turn_count % 4 != 0:
        return current
    try:
        idx = TIME_BLOCKS.index(current)
    except ValueError:
        return current
    return TIME_BLOCKS[min(idx + 1, len(TIME_BLOCKS) - 1)]


def build_turn_plan(
    worldbook: Worldbook,
    characters: list[CharacterCard],
    session: GameSession,
    player_message: str,
    relevant_memory_summaries: list[str],
) -> dict:
    current_location_id = session.runtimeState.currentLocationId
    target_location_id = _resolve_requested_location(worldbook, player_message) or current_location_id
    cast_ids = _select_cast_for_location(characters, target_location_id, session.runtimeState.currentCast)
    responder_id = _pick_responder(player_message, characters, cast_ids, session)
    event_seed = _pick_event_seed(worldbook, player_message, target_location_id)
    location_changed = target_location_id != current_location_id
    goal = _scene_goal(player_message)
    time_block = _next_time_block(session.runtimeState.timeBlock, len(session.recentTurns) + 1)

    note_parts = []
    if location_changed:
        location_name = next((row.name for row in worldbook.locations if row.id == target_location_id), target_location_id)
        note_parts.append(f'场景切换到{location_name}。')
    if event_seed:
        note_parts.append(f'当前触发线索：{event_seed}。')
    if relevant_memory_summaries:
        note_parts.append('这轮对话会参考最近的重要互动。')

    return {
        'targetLocationId': target_location_id,
        'sceneId': f'{target_location_id}:{event_seed or goal}',
        'currentCast': cast_ids,
        'responderId': responder_id,
        'eventSeed': event_seed,
        'sceneGoal': goal,
        'timeBlock': time_block,
        'directorNote': ' '.join(note_parts).strip(),
    }
