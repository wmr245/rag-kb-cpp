export type ActorType = 'player' | 'director' | 'character';

export interface WorldbookFaction {
  id: string;
  name: string;
  description: string;
}

export interface WorldbookLocation {
  id: string;
  name: string;
  description: string;
  tags: string[];
  sceneHints: string[];
}

export interface WorldbookSummary {
  id: string;
  title: string;
  version: string;
  genre: string[];
  tone: string[];
  locationCount: number;
  factionCount: number;
  eventSeedCount: number;
}

export interface Worldbook {
  id: string;
  version: string;
  title: string;
  genre: string[];
  tone: string[];
  era: string;
  locale: string;
  author: string;
  tags: string[];
  worldRules: string[];
  hardConstraints: string[];
  socialNorms: string[];
  narrativeBoundaries: string[];
  factions: WorldbookFaction[];
  locations: WorldbookLocation[];
  eventSeeds: string[];
  defaultScenePatterns: string[];
  mapAssets: string[];
}

export interface WorldbookListResponse {
  items: WorldbookSummary[];
}

export interface CharacterCardSummary {
  id: string;
  worldbookId: string;
  name: string;
  role: string;
  personaTags: string[];
  scenePreferences: string[];
}

export interface CharacterCardListResponse {
  items: CharacterCardSummary[];
}

export interface SpeechStyle {
  tone: string;
  verbosity: string;
  habitPhrases: string[];
  avoidPhrases: string[];
  cadenceHints: string[];
}

export interface UnlockableSecret {
  id: string;
  summary: string;
  unlockCondition: string;
}

export interface RelationshipDefaults {
  trust: number;
  affection: number;
  tension: number;
  familiarity: number;
  stage: string;
}

export interface CharacterCard {
  id: string;
  worldbookId: string;
  name: string;
  role: string;
  tags: string[];
  appearanceHints: string[];
  personaTags: string[];
  coreTraits: string[];
  emotionalStyle: string;
  socialStyle: string;
  innerConflict: string;
  speechStyle: SpeechStyle;
  likes: string[];
  dislikes: string[];
  softSpots: string[];
  tabooTopics: string[];
  publicFacts: string[];
  privateFacts: string[];
  unlockableSecrets: UnlockableSecret[];
  knowledgeBoundaries: string[];
  scenePreferences: string[];
  eventHooks: string[];
  entryConditions: string[];
  exitConditions: string[];
  safetyRules: string[];
  behaviorConstraints: string[];
  disclosureRules: string[];
  relationshipDefaults: RelationshipDefaults;
}

export interface GameSessionSummary {
  id: string;
  worldbookId: string;
  title: string;
  status: string;
  characterIds: string[];
  updatedAt: string;
  currentLocationId: string;
  currentCast: string[];
}

export interface GameSessionListResponse {
  items: GameSessionSummary[];
}

export interface RelationshipState {
  trust: number;
  affection: number;
  tension: number;
  familiarity: number;
  stage: string;
  unlockedSecrets: string[];
}

export interface RuntimeState {
  currentSceneId: string;
  currentLocationId: string;
  timeBlock: string;
  dayIndex: number;
  currentCast: string[];
  worldFlags: Record<string, unknown>;
  activeEvents: string[];
  completedEvents: string[];
  relationshipStates: Record<string, RelationshipState>;
}

export interface RecentTurn {
  turnId: string;
  actorType: ActorType;
  actorId: string;
  text: string;
  sceneId?: string | null;
  createdAt: string;
}

export interface MemoryProfile {
  characterId: string;
  playerImageSummary: string;
  relationshipSummary: string;
  openThreads: string[];
  preferredInteractionPatterns: string[];
  avoidPatterns: string[];
}

export interface MemoryEntry {
  id: string;
  summary: string;
  type: string;
  createdAt: string;
}

export interface GameSession {
  id: string;
  worldbookId: string;
  characterIds: string[];
  title: string;
  status: string;
  createdAt: string;
  updatedAt: string;
  runtimeState: RuntimeState;
  recentTurns: RecentTurn[];
  memoryEntries: MemoryEntry[];
  memoryProfiles: Record<string, MemoryProfile>;
}

export interface SceneSnapshot {
  locationId: string;
  locationName: string;
  locationDescription: string;
  timeBlock: string;
  dayIndex: number;
  currentCast: string[];
  moodHints: string[];
  worldRules: string[];
  activeEvents: string[];
}

export interface RelationshipStateDiff {
  characterId: string;
  trustBefore: number;
  trustAfter: number;
  affectionBefore: number;
  affectionAfter: number;
  tensionBefore: number;
  tensionAfter: number;
  familiarityBefore: number;
  familiarityAfter: number;
  stageBefore: string;
  stageAfter: string;
  unlockedSecretsAdded: string[];
}

export interface TurnStateDiff {
  locationChanged: boolean;
  previousLocationId: string;
  newLocationId: string;
  previousSceneId: string;
  newSceneId: string;
  previousTimeBlock: string;
  newTimeBlock: string;
  previousCast: string[];
  newCast: string[];
  activeEventsAdded: string[];
  newMemorySummaries: string[];
  recentTurnCountBefore: number;
  recentTurnCountAfter: number;
  relationshipChanges: RelationshipStateDiff[];
}

export interface PresentedTurn {
  turnId: string;
  actorType: ActorType;
  actorId: string;
  actorName: string;
  text: string;
  sceneId?: string | null;
  createdAt: string;
}

export interface GameTurnResult {
  responderId: string;
  responderName: string;
  sceneGoal: string;
  eventSeed?: string | null;
  turns: PresentedTurn[];
  primaryReply: string;
  stateDiff: TurnStateDiff;
}

export interface GameTurnDebug {
  targetLocationId: string;
  sceneId: string;
  selectedMemorySummaries: string[];
  recentTurnDigest: string[];
  directorNote: string;
  characterReply: string;
}

export interface GameSessionStateResponse {
  session: GameSession;
  scene: SceneSnapshot;
}

export interface GameTurnResponse extends GameSessionStateResponse {
  acknowledged: boolean;
  result: GameTurnResult;
  debug: GameTurnDebug;
}
