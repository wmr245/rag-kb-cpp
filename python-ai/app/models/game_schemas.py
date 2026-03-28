from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class WorldbookFaction(StrictModel):
    id: str
    name: str
    description: str = ''


class WorldbookLocation(StrictModel):
    id: str
    name: str
    description: str = ''
    tags: List[str] = Field(default_factory=list)
    sceneHints: List[str] = Field(default_factory=list)


class Worldbook(StrictModel):
    id: str
    version: str = '1.0.0'
    title: str
    genre: List[str] = Field(default_factory=list)
    tone: List[str] = Field(default_factory=list)
    era: str
    locale: str = ''
    author: str = ''
    tags: List[str] = Field(default_factory=list)
    worldRules: List[str] = Field(default_factory=list)
    hardConstraints: List[str] = Field(default_factory=list)
    socialNorms: List[str] = Field(default_factory=list)
    narrativeBoundaries: List[str] = Field(default_factory=list)
    factions: List[WorldbookFaction] = Field(default_factory=list)
    locations: List[WorldbookLocation] = Field(default_factory=list)
    eventSeeds: List[str] = Field(default_factory=list)
    defaultScenePatterns: List[str] = Field(default_factory=list)
    mapAssets: List[str] = Field(default_factory=list)


class SpeechStyle(StrictModel):
    tone: str = 'neutral'
    verbosity: str = 'medium'
    habitPhrases: List[str] = Field(default_factory=list)
    avoidPhrases: List[str] = Field(default_factory=list)
    cadenceHints: List[str] = Field(default_factory=list)


class UnlockableSecret(StrictModel):
    id: str
    summary: str
    unlockCondition: str


class RelationshipDefaults(StrictModel):
    trust: int = 0
    affection: int = 0
    tension: int = 0
    familiarity: int = 0
    stage: str = 'stranger'


class CharacterCard(StrictModel):
    id: str
    worldbookId: str
    name: str
    role: str = ''
    tags: List[str] = Field(default_factory=list)
    appearanceHints: List[str] = Field(default_factory=list)
    personaTags: List[str] = Field(default_factory=list)
    coreTraits: List[str] = Field(default_factory=list)
    emotionalStyle: str = ''
    socialStyle: str = ''
    innerConflict: str = ''
    speechStyle: SpeechStyle = Field(default_factory=SpeechStyle)
    likes: List[str] = Field(default_factory=list)
    dislikes: List[str] = Field(default_factory=list)
    softSpots: List[str] = Field(default_factory=list)
    tabooTopics: List[str] = Field(default_factory=list)
    publicFacts: List[str] = Field(default_factory=list)
    privateFacts: List[str] = Field(default_factory=list)
    unlockableSecrets: List[UnlockableSecret] = Field(default_factory=list)
    knowledgeBoundaries: List[str] = Field(default_factory=list)
    scenePreferences: List[str] = Field(default_factory=list)
    eventHooks: List[str] = Field(default_factory=list)
    entryConditions: List[str] = Field(default_factory=list)
    exitConditions: List[str] = Field(default_factory=list)
    safetyRules: List[str] = Field(default_factory=list)
    behaviorConstraints: List[str] = Field(default_factory=list)
    disclosureRules: List[str] = Field(default_factory=list)
    relationshipDefaults: RelationshipDefaults = Field(default_factory=RelationshipDefaults)


class RelationshipState(StrictModel):
    trust: int = 0
    affection: int = 0
    tension: int = 0
    familiarity: int = 0
    stage: str = 'stranger'
    unlockedSecrets: List[str] = Field(default_factory=list)


class RuntimeState(StrictModel):
    currentSceneId: str
    currentLocationId: str
    timeBlock: str = 'opening'
    dayIndex: int = 1
    currentCast: List[str] = Field(default_factory=list)
    worldFlags: Dict[str, Any] = Field(default_factory=dict)
    activeEvents: List[str] = Field(default_factory=list)
    completedEvents: List[str] = Field(default_factory=list)
    relationshipStates: Dict[str, RelationshipState] = Field(default_factory=dict)


class RecentTurn(StrictModel):
    turnId: str
    actorType: Literal['player', 'director', 'character']
    actorId: str
    text: str
    sceneId: Optional[str] = None
    createdAt: str


class PresentedTurn(StrictModel):
    turnId: str
    actorType: Literal['player', 'director', 'character']
    actorId: str
    actorName: str
    text: str
    sceneId: Optional[str] = None
    createdAt: str


class MemoryEntry(StrictModel):
    id: str
    type: str = 'event'
    scope: str = 'session'
    characterIds: List[str] = Field(default_factory=list)
    locationId: Optional[str] = None
    summary: str
    factPayload: Dict[str, Any] = Field(default_factory=dict)
    emotionPayload: Dict[str, Any] = Field(default_factory=dict)
    importance: float = 0.5
    visibility: Dict[str, bool] = Field(default_factory=lambda: {'player': True})
    triggerHints: List[str] = Field(default_factory=list)
    createdAt: str


class MemoryProfile(StrictModel):
    characterId: str
    playerImageSummary: str = ''
    relationshipSummary: str = ''
    openThreads: List[str] = Field(default_factory=list)
    preferredInteractionPatterns: List[str] = Field(default_factory=list)
    avoidPatterns: List[str] = Field(default_factory=list)


class GameSession(StrictModel):
    id: str
    worldbookId: str
    characterIds: List[str] = Field(default_factory=list)
    title: str
    status: str = 'active'
    createdAt: str
    updatedAt: str
    runtimeState: RuntimeState
    recentTurns: List[RecentTurn] = Field(default_factory=list)
    memoryEntries: List[MemoryEntry] = Field(default_factory=list)
    memoryProfiles: Dict[str, MemoryProfile] = Field(default_factory=dict)


class WorldbookSummary(StrictModel):
    id: str
    title: str
    version: str
    genre: List[str] = Field(default_factory=list)
    tone: List[str] = Field(default_factory=list)
    locationCount: int = 0
    factionCount: int = 0
    eventSeedCount: int = 0


class CharacterCardSummary(StrictModel):
    id: str
    worldbookId: str
    name: str
    role: str = ''
    personaTags: List[str] = Field(default_factory=list)
    scenePreferences: List[str] = Field(default_factory=list)


class GameSessionSummary(StrictModel):
    id: str
    worldbookId: str
    title: str
    status: str
    characterIds: List[str] = Field(default_factory=list)
    updatedAt: str
    currentLocationId: str
    currentCast: List[str] = Field(default_factory=list)


class SceneSnapshot(StrictModel):
    locationId: str
    locationName: str
    locationDescription: str = ''
    timeBlock: str
    dayIndex: int
    currentCast: List[str] = Field(default_factory=list)
    moodHints: List[str] = Field(default_factory=list)
    worldRules: List[str] = Field(default_factory=list)
    activeEvents: List[str] = Field(default_factory=list)


class RelationshipStateDiff(StrictModel):
    characterId: str
    trustBefore: int
    trustAfter: int
    affectionBefore: int
    affectionAfter: int
    tensionBefore: int
    tensionAfter: int
    familiarityBefore: int
    familiarityAfter: int
    stageBefore: str
    stageAfter: str
    unlockedSecretsAdded: List[str] = Field(default_factory=list)


class TurnStateDiff(StrictModel):
    locationChanged: bool = False
    previousLocationId: str
    newLocationId: str
    previousSceneId: str
    newSceneId: str
    previousTimeBlock: str
    newTimeBlock: str
    previousCast: List[str] = Field(default_factory=list)
    newCast: List[str] = Field(default_factory=list)
    activeEventsAdded: List[str] = Field(default_factory=list)
    newMemorySummaries: List[str] = Field(default_factory=list)
    recentTurnCountBefore: int = 0
    recentTurnCountAfter: int = 0
    relationshipChanges: List[RelationshipStateDiff] = Field(default_factory=list)


class GameTurnResult(StrictModel):
    responderId: str
    responderName: str
    sceneGoal: str
    eventSeed: Optional[str] = None
    turns: List[PresentedTurn] = Field(default_factory=list)
    primaryReply: str
    stateDiff: TurnStateDiff


class GameTurnDebug(StrictModel):
    targetLocationId: str
    sceneId: str
    selectedMemorySummaries: List[str] = Field(default_factory=list)
    recentTurnDigest: List[str] = Field(default_factory=list)
    directorNote: str = ''
    characterReply: str


class WorldbookCreateRequest(StrictModel):
    worldbook: Worldbook


class WorldbookListResponse(StrictModel):
    items: List[WorldbookSummary] = Field(default_factory=list)


class CharacterCardCreateRequest(StrictModel):
    characterCard: CharacterCard


class CharacterCardListResponse(StrictModel):
    items: List[CharacterCardSummary] = Field(default_factory=list)


class GameSessionCreateRequest(StrictModel):
    worldbookId: str
    characterIds: List[str] = Field(default_factory=list)
    title: str = ''
    openingLocationId: str = ''


class GameSessionStateResponse(StrictModel):
    session: GameSession
    scene: SceneSnapshot


class GameSessionListResponse(StrictModel):
    items: List[GameSessionSummary] = Field(default_factory=list)


class GameTurnRequest(StrictModel):
    message: str = Field(min_length=1, max_length=4000)


class GameTurnResponse(StrictModel):
    acknowledged: bool = True
    session: GameSession
    scene: SceneSnapshot
    result: GameTurnResult
    debug: GameTurnDebug
