import time

import httpx

from app.core.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from app.core.logging_config import logger
from app.models.game_schemas import CharacterCard, GameSession, Worldbook


def _allowed_secret_summaries(card: CharacterCard, session: GameSession) -> list[str]:
    relation = session.runtimeState.relationshipStates.get(card.id)
    unlocked = set(relation.unlockedSecrets if relation is not None else [])
    return [secret.summary for secret in card.unlockableSecrets if secret.id in unlocked]


def _heuristic_response(
    worldbook: Worldbook,
    card: CharacterCard,
    session: GameSession,
    plan: dict,
    player_message: str,
    relevant_memory_summaries: list[str],
) -> str:
    location_id = plan['targetLocationId']
    location_name = next((row.name for row in worldbook.locations if row.id == location_id), location_id)
    habit = card.speechStyle.habitPhrases[0] if card.speechStyle.habitPhrases else ''
    opener = f'{habit}，' if habit else ''
    relation = session.runtimeState.relationshipStates.get(card.id)
    trust = relation.trust if relation is not None else 0

    if plan['sceneGoal'] == 'investigate':
        body = f'{location_name}现在比较安静，适合把线索慢慢理清。我们先从最可疑的部分看起。'
    elif plan['sceneGoal'] == 'repair':
        body = f'如果你是认真想把话说清楚，那就先别急。到{location_name}再谈，会更合适。'
    elif plan['sceneGoal'] == 'bond':
        body = f'去{location_name}也好。至少那里不会被别人打扰，我们可以慢慢聊。'
    else:
        body = f'先去{location_name}吧。现在这个场景更适合把话接下去。'

    if plan.get('eventSeed'):
        body += f' 这件事大概和“{plan["eventSeed"]}”脱不开关系。'

    if relevant_memory_summaries:
        body += ' 我还记得我们之前说过的一些事，所以这次我想更认真一点。'

    if trust >= 30 and _allowed_secret_summaries(card, session):
        body += ' 有些话，我现在也许可以告诉你一点了。'

    return (opener + body).strip()


def _llm_prompt(
    worldbook: Worldbook,
    card: CharacterCard,
    session: GameSession,
    plan: dict,
    player_message: str,
    recent_turn_digest: list[str],
    relevant_memory_summaries: list[str],
) -> str:
    allowed_secrets = _allowed_secret_summaries(card, session)
    return f'''
You are writing one in-character reply for an interactive romance narrative game.
Stay consistent with the character card and current scene.
Do not reveal locked secrets.
Write only the character's reply in Chinese, in 1 to 4 sentences.

World title: {worldbook.title}
World tone: {', '.join(worldbook.tone) if worldbook.tone else 'neutral'}
World rules: {' | '.join(worldbook.worldRules[:3])}
Narrative boundaries: {' | '.join(worldbook.narrativeBoundaries[:3])}

Character name: {card.name}
Persona tags: {', '.join(card.personaTags)}
Core traits: {', '.join(card.coreTraits)}
Speech tone: {card.speechStyle.tone}
Habit phrases: {' | '.join(card.speechStyle.habitPhrases[:3])}
Public facts: {' | '.join(card.publicFacts[:3])}
Allowed secrets now: {' | '.join(allowed_secrets) if allowed_secrets else 'none'}
Behavior constraints: {' | '.join(card.behaviorConstraints[:3])}
Disclosure rules: {' | '.join(card.disclosureRules[:3])}

Scene goal: {plan['sceneGoal']}
Current location id: {plan['targetLocationId']}
Triggered event: {plan.get('eventSeed') or 'none'}
Recent turns: {' || '.join(recent_turn_digest[-5:]) if recent_turn_digest else 'none'}
Relevant memories: {' || '.join(relevant_memory_summaries) if relevant_memory_summaries else 'none'}

Player message:
{player_message}
'''.strip()


def generate_character_response(
    worldbook: Worldbook,
    card: CharacterCard,
    session: GameSession,
    plan: dict,
    player_message: str,
    recent_turn_digest: list[str],
    relevant_memory_summaries: list[str],
) -> str:
    if not LLM_API_KEY:
        return _heuristic_response(worldbook, card, session, plan, player_message, relevant_memory_summaries)

    prompt = _llm_prompt(worldbook, card, session, plan, player_message, recent_turn_digest, relevant_memory_summaries)
    payload = {
        'model': LLM_MODEL,
        'messages': [
            {
                'role': 'system',
                'content': 'You are a character writer for an interactive romance game. Stay in character, stay grounded in the provided canon, and do not leak hidden information.',
            },
            {
                'role': 'user',
                'content': prompt,
            },
        ],
        'temperature': 0.7,
        'max_tokens': 220,
    }
    headers = {
        'Authorization': f'Bearer {LLM_API_KEY}',
        'Content-Type': 'application/json',
    }

    start_time = time.time()
    try:
        with httpx.Client(timeout=45.0) as client:
            response = client.post(f'{LLM_BASE_URL}/chat/completions', headers=headers, json=payload)
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info('game character response status_code=%s elapsed_ms=%s responder=%s', response.status_code, elapsed_ms, card.id)
        response.raise_for_status()
        body = response.json()
        choices = body.get('choices', [])
        if not choices:
            raise ValueError('missing choices')
        content = str(choices[0].get('message', {}).get('content', '')).strip()
        if not content:
            raise ValueError('empty content')
        return content
    except Exception as exc:
        logger.warning('game character response fallback responder=%s error=%s', card.id, exc)
        return _heuristic_response(worldbook, card, session, plan, player_message, relevant_memory_summaries)
