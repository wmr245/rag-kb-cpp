from app.models.game_schemas import CharacterCard, CharacterCardSummary
from app.services.game_exceptions import GameConflictError, GameNotFoundError, GameValidationError
from app.services.game_storage_service import list_records, load_record, save_record
from app.services.game_utils import dump_model
from app.services.worldbook_service import get_worldbook


def validate_character_card(card: CharacterCard) -> None:
    worldbook = get_worldbook(card.worldbookId)
    location_ids = {row.id for row in worldbook.locations}
    event_seed_ids = set(worldbook.eventSeeds)

    if not card.name.strip():
        raise GameValidationError('characterCard.name must not be empty')
    if not (card.personaTags or card.coreTraits or card.speechStyle.habitPhrases):
        raise GameValidationError('characterCard must define personaTags, coreTraits, or speechStyle.habitPhrases')
    if not (card.behaviorConstraints or card.disclosureRules or card.safetyRules):
        raise GameValidationError('characterCard must define behaviorConstraints, disclosureRules, or safetyRules')
    if card.privateFacts and not (card.disclosureRules or card.unlockableSecrets):
        raise GameValidationError('privateFacts require disclosureRules or unlockableSecrets')

    missing_locations = [location_id for location_id in card.scenePreferences if location_id not in location_ids]
    if missing_locations:
        raise GameValidationError(f'characterCard.scenePreferences reference unknown locations: {missing_locations}')

    missing_events = [event_id for event_id in card.eventHooks if event_id not in event_seed_ids]
    if missing_events:
        raise GameValidationError(f'characterCard.eventHooks reference unknown event seeds: {missing_events}')


def build_character_card_summary(card: CharacterCard) -> CharacterCardSummary:
    return CharacterCardSummary(
        id=card.id,
        worldbookId=card.worldbookId,
        name=card.name,
        role=card.role,
        personaTags=card.personaTags,
        scenePreferences=card.scenePreferences,
    )


def create_character_card(card: CharacterCard) -> CharacterCard:
    validate_character_card(card)
    if load_record('character_cards', card.id) is not None:
        raise GameConflictError(f'character card already exists: {card.id}')
    save_record('character_cards', card.id, dump_model(card))
    return card


def get_character_card(character_id: str) -> CharacterCard:
    payload = load_record('character_cards', character_id)
    if payload is None:
        raise GameNotFoundError(f'character card not found: {character_id}')
    return CharacterCard.model_validate(payload)


def list_character_cards(worldbook_id: str | None = None) -> list[CharacterCardSummary]:
    rows = [CharacterCard.model_validate(payload) for payload in list_records('character_cards')]
    if worldbook_id:
        rows = [row for row in rows if row.worldbookId == worldbook_id]
    rows.sort(key=lambda row: row.id)
    return [build_character_card_summary(row) for row in rows]
