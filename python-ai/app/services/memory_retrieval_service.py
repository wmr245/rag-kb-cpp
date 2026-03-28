from app.models.game_schemas import GameSession, MemoryEntry


def _contains_term(text: str, term: str) -> bool:
    return (term or '').strip().lower() in (text or '').lower()


def _score_memory(entry: MemoryEntry, player_message: str, current_location_id: str, responder_id: str | None) -> float:
    score = float(entry.importance or 0.0)
    if entry.locationId and entry.locationId == current_location_id:
        score += 0.35
    if responder_id and responder_id in entry.characterIds:
        score += 0.35
    for hint in entry.triggerHints:
        if _contains_term(player_message, hint):
            score += 0.12
    return score


def select_relevant_memories(
    session: GameSession,
    player_message: str,
    current_location_id: str,
    responder_id: str | None = None,
    limit: int = 3,
) -> list[MemoryEntry]:
    ranked = sorted(
        session.memoryEntries,
        key=lambda entry: _score_memory(entry, player_message, current_location_id, responder_id),
        reverse=True,
    )
    return ranked[:limit]


def build_recent_turn_digest(session: GameSession, limit: int = 6) -> list[str]:
    turns = session.recentTurns[-limit:]
    return [f'{turn.actorType}:{turn.actorId}:{turn.text}' for turn in turns]


def build_memory_digest(entries: list[MemoryEntry]) -> list[str]:
    return [entry.summary for entry in entries]
