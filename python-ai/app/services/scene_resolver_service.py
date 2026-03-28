from app.models.game_schemas import CharacterCard, GameSession, SceneSnapshot, Worldbook


def build_scene_snapshot(worldbook: Worldbook, characters: list[CharacterCard], session: GameSession) -> SceneSnapshot:
    location = next(
        (row for row in worldbook.locations if row.id == session.runtimeState.currentLocationId),
        None,
    )
    cast_map = {row.id: row.name for row in characters}
    current_cast = [cast_map.get(row, row) for row in session.runtimeState.currentCast]
    mood_hints = location.sceneHints[:3] if location is not None else []

    return SceneSnapshot(
        locationId=session.runtimeState.currentLocationId,
        locationName=location.name if location is not None else session.runtimeState.currentLocationId,
        locationDescription=location.description if location is not None else '',
        timeBlock=session.runtimeState.timeBlock,
        dayIndex=session.runtimeState.dayIndex,
        currentCast=current_cast,
        moodHints=mood_hints,
        worldRules=worldbook.worldRules[:3],
        activeEvents=session.runtimeState.activeEvents,
    )
