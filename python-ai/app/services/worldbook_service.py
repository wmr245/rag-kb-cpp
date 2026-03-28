from app.models.game_schemas import Worldbook, WorldbookSummary
from app.services.game_exceptions import GameConflictError, GameNotFoundError, GameValidationError
from app.services.game_storage_service import list_records, load_record, save_record
from app.services.game_utils import dump_model


def _ensure_unique_ids(rows: list, label: str) -> None:
    seen: set[str] = set()
    for row in rows:
        if row.id in seen:
            raise GameValidationError(f'duplicate {label} id: {row.id}')
        seen.add(row.id)


def validate_worldbook(worldbook: Worldbook) -> None:
    if not worldbook.hardConstraints:
        raise GameValidationError('worldbook.hardConstraints must not be empty')
    if not worldbook.narrativeBoundaries:
        raise GameValidationError('worldbook.narrativeBoundaries must not be empty')
    if not worldbook.locations and not worldbook.defaultScenePatterns:
        raise GameValidationError('worldbook must define at least one location or defaultScenePattern')
    _ensure_unique_ids(worldbook.locations, 'location')
    _ensure_unique_ids(worldbook.factions, 'faction')


def build_worldbook_summary(worldbook: Worldbook) -> WorldbookSummary:
    return WorldbookSummary(
        id=worldbook.id,
        title=worldbook.title,
        version=worldbook.version,
        genre=worldbook.genre,
        tone=worldbook.tone,
        locationCount=len(worldbook.locations),
        factionCount=len(worldbook.factions),
        eventSeedCount=len(worldbook.eventSeeds),
    )


def create_worldbook(worldbook: Worldbook) -> Worldbook:
    validate_worldbook(worldbook)
    if load_record('worldbooks', worldbook.id) is not None:
        raise GameConflictError(f'worldbook already exists: {worldbook.id}')
    save_record('worldbooks', worldbook.id, dump_model(worldbook))
    return worldbook


def get_worldbook(worldbook_id: str) -> Worldbook:
    payload = load_record('worldbooks', worldbook_id)
    if payload is None:
        raise GameNotFoundError(f'worldbook not found: {worldbook_id}')
    return Worldbook.model_validate(payload)


def list_worldbooks() -> list[WorldbookSummary]:
    rows = [Worldbook.model_validate(payload) for payload in list_records('worldbooks')]
    rows.sort(key=lambda row: row.id)
    return [build_worldbook_summary(row) for row in rows]
