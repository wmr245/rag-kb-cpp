import json
import re
import time

import httpx

from app.core.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from app.core.logging_config import logger
from app.models.game_schemas import CharacterCard, CharacterReply, GameSession, Worldbook


def _allowed_secret_summaries(card: CharacterCard, session: GameSession) -> list[str]:
    relation = session.runtimeState.relationshipStates.get(card.id)
    unlocked = set(relation.unlockedSecrets if relation is not None else [])
    return [secret.summary for secret in card.unlockableSecrets if secret.id in unlocked]


def _parse_digest_item(item: str) -> tuple[str, str, str, str]:
    parts = item.split(':', 3)
    if len(parts) == 4:
        return parts[0], parts[1], parts[2], parts[3]
    if len(parts) == 3:
        return parts[0], parts[1], 'speech', parts[2]
    return '', '', 'speech', item


def _recent_character_turn_texts(card: CharacterCard, recent_turn_digest: list[str], limit: int = 2) -> list[str]:
    rows: list[str] = []
    for item in reversed(recent_turn_digest):
        actor_type, actor_id, presentation_type, text = _parse_digest_item(item)
        if actor_type != 'character' or actor_id != card.id or presentation_type != 'speech':
            continue
        rows.append(text.strip())
        if len(rows) >= limit:
            break
    return rows


def _recent_character_narration_texts(card: CharacterCard, recent_turn_digest: list[str], limit: int = 3) -> list[str]:
    rows: list[str] = []
    for item in reversed(recent_turn_digest):
        actor_type, actor_id, presentation_type, text = _parse_digest_item(item)
        if actor_type != 'character' or actor_id != card.id or presentation_type != 'narration':
            continue
        rows.append(text.strip())
        if len(rows) >= limit:
            break
    return rows


def _recently_used_habit_phrases(card: CharacterCard, recent_turn_digest: list[str]) -> list[str]:
    recent_texts = _recent_character_turn_texts(card, recent_turn_digest)
    if not recent_texts or not card.speechStyle.habitPhrases:
        return []

    repeated: list[str] = []
    for phrase in card.speechStyle.habitPhrases[:3]:
        if any(phrase and phrase in text for text in recent_texts):
            repeated.append(phrase)
    return repeated


def _flatten_reply(reply: CharacterReply) -> str:
    return ' '.join(part for part in [reply.narration.strip(), reply.dialogue.strip()] if part).strip()


def _response_reuses_recent_habits(reply: CharacterReply, repeated_habits: list[str]) -> bool:
    normalized = re.sub(r'\s+', '', _flatten_reply(reply))
    return any(phrase and phrase in normalized for phrase in repeated_habits)


def _normalized_compare_text(text: str) -> str:
    return re.sub(r'\s+', '', text or '')


def _contains_any(text: str, terms: tuple[str, ...] | list[str]) -> bool:
    normalized = _normalized_compare_text(text).lower()
    return any(term and term in normalized for term in terms)


def _is_brief_greeting(text: str) -> bool:
    normalized = _normalized_compare_text(text).lower()
    if not normalized:
        return False
    greeting_terms = (
        '你好',
        '您好',
        '嗨',
        'hi',
        'hello',
        '早上好',
        '晚上好',
        '午安',
        '在吗',
        '哈喽',
        '嘿',
    )
    return len(normalized) <= 8 and any(term in normalized for term in greeting_terms)


def _is_direct_clarification(text: str) -> bool:
    normalized = _normalized_compare_text(text).lower()
    clarification_terms = (
        '你在说什么',
        '你说什么',
        '什么意思',
        '什么情况',
        '怎么回事',
        '你刚才说什么',
    )
    return any(term in normalized for term in clarification_terms)


def _looks_like_question(text: str) -> bool:
    normalized = _normalized_compare_text(text).lower()
    if not normalized:
        return False
    question_terms = (
        '?',
        '？',
        '吗',
        '么',
        '是不是',
        '有没有',
        '会不会',
        '能不能',
        '要不要',
        '为什么',
        '怎么',
        '怎么了',
        '什么意思',
        '谁',
        '哪',
        '哪里',
        '哪儿',
        '喜欢',
        '讨厌',
    )
    return any(term in normalized for term in question_terms)


def _char_bigrams(text: str) -> set[str]:
    normalized = _normalized_compare_text(text)
    if len(normalized) < 2:
        return {normalized} if normalized else set()
    return {normalized[index : index + 2] for index in range(len(normalized) - 1)}


def _text_similarity(left: str, right: str) -> float:
    left_parts = _char_bigrams(left)
    right_parts = _char_bigrams(right)
    if not left_parts or not right_parts:
        return 0.0
    overlap = left_parts & right_parts
    union = left_parts | right_parts
    return len(overlap) / len(union)


def _response_reuses_recent_narration(reply: CharacterReply, recent_narrations: list[str]) -> bool:
    narration = reply.narration.strip()
    if not narration or not recent_narrations:
        return False
    normalized = _normalized_compare_text(narration)
    for recent in recent_narrations:
        recent_normalized = _normalized_compare_text(recent)
        if not recent_normalized:
            continue
        if normalized == recent_normalized:
            return True
        if _text_similarity(normalized, recent_normalized) >= 0.58:
            return True
    return False


_BLOCKED_FINGER_TERMS = ('指尖', '手指', '指腹', '指节', '指根')


def _response_mentions_blocked_finger_action(reply: CharacterReply) -> bool:
    narration = reply.narration.strip()
    return bool(narration and any(term in narration for term in _BLOCKED_FINGER_TERMS))


def _dialogue_clause_count(text: str) -> int:
    return len([segment for segment in re.split(r'[。！？!?；;]', text or '') if segment.strip()])


def _dialogue_needs_more_forward_motion(dialogue: str, player_message: str) -> bool:
    value = (dialogue or '').strip()
    if not value:
        return True
    normalized_length = len(_normalized_compare_text(value))
    question_count = value.count('？') + value.count('?')
    if _is_brief_greeting(player_message):
        return normalized_length < 8
    if _is_direct_clarification(player_message):
        return normalized_length < 10
    if _looks_like_question(player_message):
        if question_count > 1:
            return True
        return normalized_length < 5
    if question_count > 1:
        return True
    if normalized_length < 18:
        return True
    if _dialogue_clause_count(value) < 2 and normalized_length < 30:
        return True
    return False


def _sanitize_generated_reply(
    reply: CharacterReply,
    recent_narrations: list[str],
) -> CharacterReply:
    sanitized = _normalize_reply(reply)
    narration = sanitized.narration.strip()
    if narration and (
        _response_reuses_recent_narration(sanitized, recent_narrations)
        or _response_mentions_blocked_finger_action(sanitized)
        or _text_looks_overformatted(narration)
    ):
        sanitized = CharacterReply(dialogue=sanitized.dialogue, narration='')
    return _normalize_reply(sanitized)


def _text_looks_overformatted(text: str) -> bool:
    value = (text or '').strip()
    if not value:
        return False
    ellipsis_count = value.count('……') + value.count('...')
    starts_with_ellipsis = value.startswith('……') or value.startswith('...')
    has_parenthetical = '（' in value or '(' in value
    fragment_lines = [line.strip() for line in value.splitlines() if line.strip()]
    has_fragmented_layout = len(fragment_lines) >= 3
    return starts_with_ellipsis or ellipsis_count >= 3 or (has_parenthetical and ellipsis_count >= 1) or has_fragmented_layout


def _response_looks_overformatted(reply: CharacterReply) -> bool:
    dialogue = reply.dialogue.strip()
    narration = reply.narration.strip()
    if not dialogue and not narration:
        return True
    if _text_looks_overformatted(dialogue):
        return True
    return bool(narration and _text_looks_overformatted(narration))


def _normalize_reply(reply: CharacterReply) -> CharacterReply:
    dialogue = re.sub(r'\s+', ' ', reply.dialogue or '').strip()
    narration = re.sub(r'\s+', ' ', reply.narration or '').strip()
    dialogue = re.sub(r'^(?:…|\.|……|\.\.\.)+', '', dialogue).lstrip('，。！？、,.;；:： ')
    return CharacterReply(dialogue=dialogue.strip(), narration=narration.strip())


def _parse_llm_text(raw: str) -> str:
    candidate = _strip_code_fence(raw).strip()
    if candidate.startswith('{'):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            for key in ('dialogue', 'narration', 'text'):
                value = str(parsed.get(key, '') or '').strip()
                if value:
                    candidate = value
                    break
    if len(candidate) >= 2 and candidate[0] == candidate[-1] and candidate[0] in {'"', "'"}:
        candidate = candidate[1:-1].strip()
    return re.sub(r'\s+', ' ', candidate).strip()


def _heuristic_response(
    worldbook: Worldbook,
    card: CharacterCard,
    session: GameSession,
    plan: dict,
    player_message: str,
    recent_turn_digest: list[str],
    relevant_memory_summaries: list[str],
) -> CharacterReply:
    location_id = plan['targetLocationId']
    location_name = next((row.name for row in worldbook.locations if row.id == location_id), location_id)
    relation = session.runtimeState.relationshipStates.get(card.id)
    trust = relation.trust if relation is not None else 0
    repeated_habits = set(_recently_used_habit_phrases(card, recent_turn_digest))
    normalized_message = _normalized_compare_text(player_message)

    if _is_brief_greeting(player_message):
        dialogue = '你好。你先坐吧，我这边马上弄完。'
        narration = '她抬头看了你一眼，语气放轻了一点。'
    elif _is_direct_clarification(player_message):
        dialogue = '我是说，你刚才像是有话没说完。要是你想说，就直接说；不想说也没关系。'
        narration = '她顿了一下，把话说得更直白了一点。'
    elif plan['sceneGoal'] == 'investigate':
        dialogue = (
            f'{location_name}这会儿挺安静的，适合把事情说清楚。'
            ' 你先把刚才发生的顺序告诉我，我们一点点捋。'
        )
        narration = '她把声音放轻了些，像是在等你把事情从头说清楚。'
    elif plan['sceneGoal'] == 'repair':
        dialogue = (
            f'如果你是想把话说清楚，那就慢一点。我们先在{location_name}坐下，我听你说。'
            ' 你先说最在意的那一句，别一下子全压在一起。'
        )
        narration = '她没有躲开，只是把语气压低了些。'
    elif plan['sceneGoal'] == 'bond':
        dialogue = (
            f'{location_name}现在挺安静的，我们就在这儿聊吧。'
            ' 雨停前还有时间，你慢慢说就行。'
        )
        narration = '她神色缓下来了一点，没有把这句话躲过去。'
    else:
        if _looks_like_question(player_message):
            dialogue = '你刚才问的那句，我会直接答。要是你还想听细一点，我就顺着往下说。'
        else:
            dialogue = (
                f'我听见了。要是你想继续说，我们就在{location_name}把这段话慢慢接下去。'
            )
        narration = '她把注意力重新放回你这边，像是准备认真接这段话。'

    if trust >= 30 and _allowed_secret_summaries(card, session):
        dialogue += ' 有些话，我现在可以多告诉你一点。'

    if '也许吧' in repeated_habits:
        dialogue = dialogue.replace('也许会', '会').replace('也许可以', '可以')

    if any(token in normalized_message for token in ('谢谢', '多谢')):
        dialogue = f'嗯，我知道。你肯留下来这件事，本身就已经很难得了。{dialogue}'
    elif any(token in normalized_message for token in ('对不起', '抱歉')):
        dialogue = f'我听见了。先别急着把自己逼得太紧，慢一点说也没关系。{dialogue}'

    return CharacterReply(dialogue=dialogue.strip(), narration=narration.strip())


def _llm_prompt(
    worldbook: Worldbook,
    card: CharacterCard,
    session: GameSession,
    plan: dict,
    player_message: str,
    recent_turn_digest: list[str],
    relevant_memory_summaries: list[str],
    repeated_habits: list[str],
    recent_narrations: list[str],
    force_avoid_repeated_habits: bool = False,
    force_natural_flow: bool = False,
    force_fresh_narration: bool = False,
    force_forward_motion: bool = False,
) -> str:
    allowed_secrets = _allowed_secret_summaries(card, session)
    recent_character_turns = _recent_character_turn_texts(card, recent_turn_digest)
    optional_habit_phrases = ' | '.join(card.speechStyle.habitPhrases[:3]) if card.speechStyle.habitPhrases else 'none'
    repeated_habit_text = ' | '.join(repeated_habits) if repeated_habits else 'none'
    recent_character_turn_text = ' || '.join(recent_character_turns) if recent_character_turns else 'none'
    recent_narration_text = ' || '.join(recent_narrations) if recent_narrations else 'none'
    event_reference_rule = (
        'Do not mention the background cue by name unless the player directly referred to it or the conversation has already clearly reached it.'
        if plan.get('eventSeed')
        else 'No hidden background cue needs to be named in the dialogue.'
    )
    repetition_rule = (
        f'Do not use these recently repeated catchphrases at all in this reply: {repeated_habit_text}.'
        if force_avoid_repeated_habits and repeated_habits
        else f'Avoid repeating these recently used catchphrases unless absolutely necessary: {repeated_habit_text}.'
    )
    natural_flow_rule = (
        'Use flowing natural prose. Do not start dialogue with ellipses. Do not use parenthetical stage directions.'
        if force_natural_flow
        else 'Prefer flowing natural prose. Avoid opening with ellipses, avoid screenplay-style parenthetical gestures, and do not break every thought into fragments.'
    )
    narration_focus_rule = (
        'Treat narration as a fresh reaction to this exact exchange. Shift the physical or sensory focus away from the recent narrations.'
        if force_fresh_narration
        else 'Treat narration as a fresh reaction to this exact exchange. Use the recent narrations only to avoid echoing the same imagery, object focus, or body focus too closely.'
    )
    forward_motion_rule = (
        'The dialogue must move the scene forward. Give at least two natural clauses or sentences, and end with a concrete continuation beat instead of a closed reaction.'
        if force_forward_motion
        else 'The dialogue should usually move the scene forward with at least two natural clauses or sentences, ending on a concrete continuation beat instead of a closed reaction.'
    )
    return f'''
You are writing one in-character reply for a contemporary slice-of-life conversation game.
Stay consistent with the character card and current scene.
Do not reveal locked secrets.
Return only a JSON object with exactly two string fields: "dialogue" and "narration".
"dialogue" must contain only what the character actually says out loud in Chinese.
"dialogue" must not contain quoted narration, stage directions, or meta commentary.
"narration" may contain only the character's动作、神态、沉默、迟疑、心理活动 in Chinese.
"narration" must not contain spoken lines, quoted dialogue, or scene-planning notes.
If a field is not needed, return an empty string for that field.
Prefer giving the player at least a short spoken reply unless silence is clearly the strongest choice.
Keep the writing concise, plain, and conversational. The style should feel like an everyday real-person exchange, not a novel.
Do not output markdown, code fences, or explanations.
If the player only opens with a brief greeting or low-pressure line, a natural greeting back is enough. Do not force a plot turn or dramatic pivot.
If the player asks a direct question like “你在说什么” or “你很喜欢这本书吗”, answer that exact question directly first. A brief direct answer is acceptable if it clearly addresses what was asked.
Do not mechanically repeat the same catchphrase, disclaimer, or sentence frame across adjacent turns.
Habit phrases are optional flavor cues, not mandatory openings.
Use at most one habit phrase in the dialogue, and prefer fresh wording when the same mood can be expressed naturally.
Cadence hints are low-frequency style tendencies, not sentence templates that must appear every turn.
Avoid consecutive replies that all use parentheses, leading ellipses, or the same "deny first, then soften" pattern.
Let the character say a little more than a bare reaction when the moment allows it.
After answering the player, actively keep the exchange moving with one concrete continuation beat: an observation, an offer, a suggestion, a small disclosure, or a next step.
Do not rely on repeated questioning to carry the conversation. Prefer statements, offers, invitations, scene observations, or partial disclosures.
Use at most one question in the dialogue, and many turns should contain no question at all.
{forward_motion_rule}
Do not write poetic prose, lyrical imagery, symbolic metaphors, or novel-like inner monologue.
Do not use English words unless the player used English first.
Avoid counseling-sounding lines, abstract emotional analysis, or lines that sound like narration notes instead of real speech.
If you are unsure about narration, prefer one short neutral sentence over a decorative beat.
{repetition_rule}
{natural_flow_rule}
{narration_focus_rule}
{event_reference_rule}
For narration, prioritize the immediate exchange over signature props or stock gestures.
Do not mention finger or fingertip micro-gestures in narration.
Narration should stay plain and observable. No poetic comparisons like “像一句未写完的话” or “比雨声更……” .
Narration priority order:
1. The player's latest words or action.
2. The immediate shift in distance, posture, breath, gaze, silence, pace, or emotional pressure.
3. The current location and atmosphere.
4. The character's personality as a light filter, not as the main source of imagery.

World title: {worldbook.title}
World tone: {', '.join(worldbook.tone) if worldbook.tone else 'neutral'}
World rules: {' | '.join(worldbook.worldRules[:3])}
Narrative boundaries: {' | '.join(worldbook.narrativeBoundaries[:3])}

Character name: {card.name}
Persona tags: {', '.join(card.personaTags)}
Core traits: {', '.join(card.coreTraits)}
Speech tone: {card.speechStyle.tone}
Optional speech cues: {optional_habit_phrases}
Low-frequency style tendencies: {' | '.join(card.speechStyle.cadenceHints[:4]) if card.speechStyle.cadenceHints else 'none'}
Allowed secrets now: {' | '.join(allowed_secrets) if allowed_secrets else 'none'}
Behavior constraints: {' | '.join(card.behaviorConstraints[:3])}
Disclosure rules: {' | '.join(card.disclosureRules[:3])}

Scene goal: {plan['sceneGoal']}
Current location id: {plan['targetLocationId']}
Background cue (internal, do not quote directly unless earned): {plan.get('eventSeed') or 'none'}
Recent exchange beats: {' || '.join(recent_turn_digest[-5:]) if recent_turn_digest else 'none'}
Recent spoken replies from this same character: {recent_character_turn_text}
Recent narrations from this same character: {recent_narration_text}
Relevant memories: {' || '.join(relevant_memory_summaries) if relevant_memory_summaries else 'none'}

Player message:
{player_message}
'''.strip()


def _llm_narration_prompt(
    worldbook: Worldbook,
    card: CharacterCard,
    session: GameSession,
    plan: dict,
    player_message: str,
    dialogue: str,
    recent_turn_digest: list[str],
    recent_narrations: list[str],
    relevant_memory_summaries: list[str],
    force_natural_flow: bool = False,
    force_fresh_narration: bool = False,
) -> str:
    recent_narration_text = ' || '.join(recent_narrations) if recent_narrations else 'none'
    natural_flow_rule = (
        'Write smooth prose. Avoid leading ellipses, parenthetical stage directions, and broken fragments.'
        if force_natural_flow
        else 'Prefer smooth prose. Avoid leading ellipses, parenthetical stage directions, and broken fragments.'
    )
    freshness_rule = (
        'Shift to a clearly different physical or sensory angle from the recent narrations.'
        if force_fresh_narration
        else 'Use the recent narrations only to avoid echoing the same imagery, object focus, or body focus too closely.'
    )
    return f'''
You are writing only the narration beat for one turn in a contemporary slice-of-life conversation game.
Return only the narration text in Chinese. Do not output JSON, markdown, labels, or explanations.
This narration must be derived first from the current exchange:
1. The player's latest words or action.
2. The character's spoken reply.
3. The immediate shift in distance, posture, breath, gaze, silence, pace, or emotional pressure.
Use the character card only as a light filter. Do not let hobbies, props, or signature imagery dominate unless the exchange directly calls for them.
Keep the narration concise, plain, and grounded in this exact moment.
Do not mention finger or fingertip micro-gestures in narration.
Do not use poetic comparisons, abstract symbolism, literary phrasing, or English words.
Prefer one short everyday sentence. Focus on what can be plainly noticed.
{natural_flow_rule}
{freshness_rule}

World title: {worldbook.title}
World tone: {', '.join(worldbook.tone) if worldbook.tone else 'neutral'}
Character name: {card.name}
Persona tags: {', '.join(card.personaTags[:3])}
Core traits: {', '.join(card.coreTraits[:3])}
Emotional style: {card.emotionalStyle}
Scene goal: {plan['sceneGoal']}
Current location id: {plan['targetLocationId']}
Background cue (internal, do not quote directly unless earned): {plan.get('eventSeed') or 'none'}
Recent exchange beats: {' || '.join(recent_turn_digest[-5:]) if recent_turn_digest else 'none'}
Recent narrations from this same character: {recent_narration_text}
Relevant memories: {' || '.join(relevant_memory_summaries[:3]) if relevant_memory_summaries else 'none'}

Player message:
{player_message}

Character dialogue:
{dialogue or 'none'}
'''.strip()


def _request_llm_response(prompt: str, responder_id: str) -> str:
    payload = {
        'model': LLM_MODEL,
        'messages': [
            {
                'role': 'system',
                'content': 'You write grounded everyday Chinese dialogue for a contemporary character interaction game. Stay in character, stay natural, avoid literary prose, and do not leak hidden information.',
            },
            {
                'role': 'user',
                'content': prompt,
            },
        ],
        'temperature': 0.45,
        'max_tokens': 260,
    }
    headers = {
        'Authorization': f'Bearer {LLM_API_KEY}',
        'Content-Type': 'application/json',
    }

    start_time = time.time()
    with httpx.Client(timeout=45.0) as client:
        response = client.post(f'{LLM_BASE_URL}/chat/completions', headers=headers, json=payload)
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info('game character response status_code=%s elapsed_ms=%s responder=%s', response.status_code, elapsed_ms, responder_id)
    response.raise_for_status()
    body = response.json()
    choices = body.get('choices', [])
    if not choices:
        raise ValueError('missing choices')
    content = str(choices[0].get('message', {}).get('content', '')).strip()
    if not content:
        raise ValueError('empty content')
    return content


def _strip_code_fence(raw: str) -> str:
    value = raw.strip()
    if not value.startswith('```'):
        return value
    lines = value.splitlines()
    if not lines:
        return value
    if lines[0].startswith('```'):
        lines = lines[1:]
    if lines and lines[-1].strip() == '```':
        lines = lines[:-1]
    return '\n'.join(lines).strip()


def _parse_character_reply(raw: str) -> CharacterReply:
    candidate = _strip_code_fence(raw)
    payload_text = candidate
    if not candidate.startswith('{'):
        match = re.search(r'\{[\s\S]+\}', candidate)
        if match:
            payload_text = match.group(0)

    try:
        parsed = json.loads(payload_text)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        dialogue = str(parsed.get('dialogue', '') or '').strip()
        narration = str(parsed.get('narration', '') or '').strip()
        if dialogue or narration:
            return _normalize_reply(CharacterReply(dialogue=dialogue, narration=narration))

    fallback = candidate.strip()
    return _normalize_reply(CharacterReply(dialogue=fallback, narration=''))


def generate_character_response(
    worldbook: Worldbook,
    card: CharacterCard,
    session: GameSession,
    plan: dict,
    player_message: str,
    recent_turn_digest: list[str],
    relevant_memory_summaries: list[str],
) -> CharacterReply:
    repeated_habits = _recently_used_habit_phrases(card, recent_turn_digest)
    recent_narrations = _recent_character_narration_texts(card, recent_turn_digest)
    if not LLM_API_KEY:
        return _heuristic_response(worldbook, card, session, plan, player_message, recent_turn_digest, relevant_memory_summaries)

    prompt = _llm_prompt(
        worldbook,
        card,
        session,
        plan,
        player_message,
        recent_turn_digest,
        relevant_memory_summaries,
        repeated_habits,
        recent_narrations,
    )

    try:
        reply = _sanitize_generated_reply(
            _parse_character_reply(_request_llm_response(prompt, card.id)),
            recent_narrations,
        )
        if reply.dialogue:
            narration_prompt = _llm_narration_prompt(
                worldbook,
                card,
                session,
                plan,
                player_message,
                reply.dialogue,
                recent_turn_digest,
                recent_narrations,
                relevant_memory_summaries,
            )
            generated_narration = _parse_llm_text(_request_llm_response(narration_prompt, card.id))
            if generated_narration:
                reply = _sanitize_generated_reply(
                    CharacterReply(dialogue=reply.dialogue, narration=generated_narration),
                    recent_narrations,
                )
        quality_retry_needed = (
            not reply.dialogue.strip()
            or (repeated_habits and _response_reuses_recent_habits(reply, repeated_habits))
            or _text_looks_overformatted(reply.dialogue)
        )
        if quality_retry_needed:
            retry_prompt = _llm_prompt(
                worldbook,
                card,
                session,
                plan,
                player_message,
                recent_turn_digest,
                relevant_memory_summaries,
                repeated_habits,
                recent_narrations,
                force_avoid_repeated_habits=True,
                force_natural_flow=True,
                force_fresh_narration=True,
                force_forward_motion=True,
            )
            retry_reply = _sanitize_generated_reply(
                _parse_character_reply(_request_llm_response(retry_prompt, card.id)),
                recent_narrations,
            )
            if retry_reply.dialogue:
                retry_narration_prompt = _llm_narration_prompt(
                    worldbook,
                    card,
                    session,
                    plan,
                    player_message,
                    retry_reply.dialogue,
                    recent_turn_digest,
                    recent_narrations,
                    relevant_memory_summaries,
                    force_natural_flow=True,
                    force_fresh_narration=True,
                )
                retry_narration = _parse_llm_text(_request_llm_response(retry_narration_prompt, card.id))
                if retry_narration:
                    retry_reply = _sanitize_generated_reply(
                        CharacterReply(dialogue=retry_reply.dialogue, narration=retry_narration),
                        recent_narrations,
                    )
            if retry_reply.dialogue.strip() and not _text_looks_overformatted(retry_reply.dialogue):
                reply = retry_reply
            elif not reply.dialogue.strip():
                return _heuristic_response(worldbook, card, session, plan, player_message, recent_turn_digest, relevant_memory_summaries)
        if not reply.dialogue.strip() and not reply.narration.strip():
            return _heuristic_response(worldbook, card, session, plan, player_message, recent_turn_digest, relevant_memory_summaries)
        return reply
    except Exception as exc:
        logger.warning('game character response fallback responder=%s error=%s', card.id, exc)
        return _heuristic_response(worldbook, card, session, plan, player_message, recent_turn_digest, relevant_memory_summaries)
