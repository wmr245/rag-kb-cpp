import copy

from app.models.game_schemas import (
    CharacterCard,
    CharacterReply,
    GameSession,
    MemoryEntry,
    MemoryProfile,
    RecentTurn,
    RelationshipStateDiff,
    TurnStateDiff,
    Worldbook,
)
from app.services.game_utils import new_id, utc_now_iso


def _contains_term(text: str, term: str) -> bool:
    return (term or '').strip().lower() in (text or '').lower()


def _clamp(value: int, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, value))


def _update_stage(trust: int, affection: int, tension: int) -> str:
    if trust >= 60 or affection >= 60:
        return 'close'
    if trust >= 35 or affection >= 30:
        return 'warming_up'
    if tension >= 40:
        return 'strained'
    return 'stranger'


def snapshot_turn_state(session: GameSession) -> dict:
    return {
        'locationId': session.runtimeState.currentLocationId,
        'sceneId': session.runtimeState.currentSceneId,
        'timeBlock': session.runtimeState.timeBlock,
        'currentCast': list(session.runtimeState.currentCast),
        'activeEvents': list(session.runtimeState.activeEvents),
        'recentTurnCount': len(session.recentTurns),
        'memoryCount': len(session.memoryEntries),
        'memorySummaries': [entry.summary for entry in session.memoryEntries],
        'relationshipStates': copy.deepcopy(session.runtimeState.relationshipStates),
    }


def _apply_relationship_delta(card: CharacterCard, relation, player_message: str, event_seed: str | None) -> None:
    trust_delta = 0
    affection_delta = 0
    tension_delta = 0
    familiarity_delta = 1

    warm_terms = ['谢谢', '陪', '一起', '想你', '抱歉', '对不起', '相信']
    if any(_contains_term(player_message, term) for term in warm_terms):
        trust_delta += 1
        affection_delta += 1

    if any(_contains_term(player_message, term) for term in ['答应', 'promise', '守约']):
        trust_delta += 2

    if any(_contains_term(player_message, term) for term in card.softSpots):
        affection_delta += 2
        trust_delta += 1

    if any(_contains_term(player_message, term) for term in card.tabooTopics):
        tension_delta += 2
        trust_delta -= 1

    if event_seed and event_seed in card.eventHooks:
        familiarity_delta += 1

    relation.trust = _clamp(relation.trust + trust_delta)
    relation.affection = _clamp(relation.affection + affection_delta)
    relation.tension = _clamp(relation.tension + tension_delta)
    relation.familiarity = _clamp(relation.familiarity + familiarity_delta)
    relation.stage = _update_stage(relation.trust, relation.affection, relation.tension)


def _unlock_secrets(card: CharacterCard, relation) -> list[str]:
    unlocked: list[str] = []
    current = set(relation.unlockedSecrets)
    for secret in card.unlockableSecrets:
        if secret.id in current:
            continue
        if secret.unlockCondition == 'trust_ge_30' and relation.trust >= 30:
            relation.unlockedSecrets.append(secret.id)
            unlocked.append(secret.id)
        elif secret.unlockCondition == 'affection_ge_25' and relation.affection >= 25:
            relation.unlockedSecrets.append(secret.id)
            unlocked.append(secret.id)
    return unlocked


def _append_recent_turn(
    session: GameSession,
    actor_type: str,
    actor_id: str,
    text: str,
    scene_id: str,
    created_at: str,
    presentation_type: str = 'speech',
) -> RecentTurn:
    turn = RecentTurn(
        turnId=new_id('turn'),
        actorType=actor_type,
        actorId=actor_id,
        text=text,
        presentationType=presentation_type,
        sceneId=scene_id,
        createdAt=created_at,
    )
    session.recentTurns.append(turn)
    session.recentTurns = session.recentTurns[-12:]
    return turn


def _append_memory(session: GameSession, summary: str, character_ids: list[str], location_id: str, trigger_hints: list[str], created_at: str, memory_type: str = 'event') -> None:
    session.memoryEntries.append(
        MemoryEntry(
            id=new_id('mem'),
            type=memory_type,
            scope='session',
            characterIds=character_ids,
            locationId=location_id,
            sceneId=session.runtimeState.currentSceneId,
            summary=summary,
            factPayload={},
            emotionPayload={},
            importance=0.72,
            visibility={'player': True},
            triggerHints=trigger_hints,
            createdAt=created_at,
        )
    )
    session.memoryEntries = session.memoryEntries[-40:]


def _refresh_memory_profile(session: GameSession, card: CharacterCard, relation) -> None:
    session.memoryProfiles[card.id] = MemoryProfile(
        characterId=card.id,
        playerImageSummary=(
            '她觉得玩家愿意认真回应，也在慢慢建立可信度。'
            if relation.trust >= 25
            else '她还在观察玩家是否值得继续靠近。'
        ),
        relationshipSummary=(
            f'当前关系阶段为 {relation.stage}，trust={relation.trust}，affection={relation.affection}，tension={relation.tension}。'
        ),
        openThreads=session.runtimeState.activeEvents[:3],
        preferredInteractionPatterns=card.softSpots[:3],
        avoidPatterns=card.tabooTopics[:3],
    )


def build_state_diff(before: dict, session: GameSession) -> TurnStateDiff:
    after_states = session.runtimeState.relationshipStates
    relationship_changes: list[RelationshipStateDiff] = []
    for character_id, after in after_states.items():
        before_state = before['relationshipStates'].get(character_id)
        if before_state is None:
            continue
        unlocked_before = set(before_state.unlockedSecrets)
        unlocked_after = list(after.unlockedSecrets)
        change = RelationshipStateDiff(
            characterId=character_id,
            trustBefore=before_state.trust,
            trustAfter=after.trust,
            affectionBefore=before_state.affection,
            affectionAfter=after.affection,
            tensionBefore=before_state.tension,
            tensionAfter=after.tension,
            familiarityBefore=before_state.familiarity,
            familiarityAfter=after.familiarity,
            stageBefore=before_state.stage,
            stageAfter=after.stage,
            unlockedSecretsAdded=[secret_id for secret_id in unlocked_after if secret_id not in unlocked_before],
        )
        has_change = any(
            [
                change.trustBefore != change.trustAfter,
                change.affectionBefore != change.affectionAfter,
                change.tensionBefore != change.tensionAfter,
                change.familiarityBefore != change.familiarityAfter,
                change.stageBefore != change.stageAfter,
                bool(change.unlockedSecretsAdded),
            ]
        )
        if has_change:
            relationship_changes.append(change)

    added_events = [event for event in session.runtimeState.activeEvents if event not in before['activeEvents']]
    added_memories = session.memoryEntries[before['memoryCount'] :]

    return TurnStateDiff(
        locationChanged=before['locationId'] != session.runtimeState.currentLocationId,
        previousLocationId=before['locationId'],
        newLocationId=session.runtimeState.currentLocationId,
        previousSceneId=before['sceneId'],
        newSceneId=session.runtimeState.currentSceneId,
        previousTimeBlock=before['timeBlock'],
        newTimeBlock=session.runtimeState.timeBlock,
        previousCast=before['currentCast'],
        newCast=list(session.runtimeState.currentCast),
        activeEventsAdded=added_events,
        newMemorySummaries=[entry.summary for entry in added_memories],
        recentTurnCountBefore=before['recentTurnCount'],
        recentTurnCountAfter=len(session.recentTurns),
        relationshipChanges=relationship_changes,
    )


def apply_turn_result(
    session: GameSession,
    worldbook: Worldbook,
    responder: CharacterCard,
    plan: dict,
    player_message: str,
    character_reply: CharacterReply,
) -> tuple[GameSession, list[RecentTurn]]:
    now = utc_now_iso()
    appended_turns: list[RecentTurn] = []
    session.runtimeState.currentLocationId = plan['targetLocationId']
    session.runtimeState.currentSceneId = plan['sceneId']
    session.runtimeState.currentCast = plan['currentCast']
    session.runtimeState.timeBlock = plan['timeBlock']

    if plan.get('eventSeed') and plan['eventSeed'] not in session.runtimeState.activeEvents:
        session.runtimeState.activeEvents.append(plan['eventSeed'])
        session.runtimeState.activeEvents = session.runtimeState.activeEvents[-5:]

    appended_turns.append(_append_recent_turn(session, 'player', 'player', player_message, plan['sceneId'], now))
    if character_reply.narration.strip():
        appended_turns.append(
            _append_recent_turn(
                session,
                'character',
                responder.id,
                character_reply.narration.strip(),
                plan['sceneId'],
                now,
                'narration',
            )
        )
    if character_reply.dialogue.strip():
        appended_turns.append(
            _append_recent_turn(
                session,
                'character',
                responder.id,
                character_reply.dialogue.strip(),
                plan['sceneId'],
                now,
                'speech',
            )
        )

    relation = session.runtimeState.relationshipStates[responder.id]
    _apply_relationship_delta(responder, relation, player_message, plan.get('eventSeed'))
    unlocked = _unlock_secrets(responder, relation)

    if plan.get('eventSeed'):
        _append_memory(
            session,
            f'在{plan["targetLocationId"]}场景中，{responder.name}围绕“{plan["eventSeed"]}”回应了玩家。',
            [responder.id],
            plan['targetLocationId'],
            [plan['eventSeed'], responder.name],
            now,
            'event',
        )

    if any(_contains_term(player_message, term) for term in ['答应', 'promise', '陪']):
        _append_memory(
            session,
            f'玩家在{plan["targetLocationId"]}向{responder.name}表达了陪伴或承诺。',
            [responder.id],
            plan['targetLocationId'],
            ['陪伴', '承诺', responder.name],
            now,
            'promise',
        )

    for secret_id in unlocked:
        _append_memory(
            session,
            f'{responder.name}对玩家解锁了新的秘密线索：{secret_id}。',
            [responder.id],
            plan['targetLocationId'],
            [secret_id, responder.name],
            now,
            'secret_unlock',
        )

    _refresh_memory_profile(session, responder, relation)
    session.updatedAt = now
    return session, appended_turns
