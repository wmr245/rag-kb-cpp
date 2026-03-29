export type ActorType = 'player' | 'director' | 'character';
export type PresentationType = 'speech' | 'narration';
export type AssistantStatus = 'draft' | 'active' | 'archived';
export type AssistantMemoryStatus = 'empty' | 'building' | 'ready';

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

export interface AssistantSummary {
  id: string;
  source: 'projected_character' | 'assistant';
  name: string;
  worldbookId: string;
  worldbookTitle: string;
  characterId: string;
  characterRole: string;
  personaTags: string[];
  userScope: string;
  summary: string;
  status: AssistantStatus;
  memoryStatus: AssistantMemoryStatus;
  updatedAt: string;
  sessionCount: number;
  activeSessionCount: number;
  archivedSessionCount: number;
  recentSessionId: string;
}

export interface Assistant {
  id: string;
  name: string;
  worldbookId: string;
  characterId: string;
  userScope: string;
  status: AssistantStatus;
  memoryStatus: AssistantMemoryStatus;
  summary: string;
  createdAt: string;
  updatedAt: string;
}

export interface AssistantListResponse {
  items: AssistantSummary[];
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
  assistantId?: string;
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

export interface GameSessionDeleteResponse {
  deleted: boolean;
  sessionId: string;
  title: string;
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
  presentationType?: PresentationType;
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
  sceneId?: string | null;
  createdAt: string;
}

export interface GameSession {
  id: string;
  assistantId?: string;
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
  presentationType?: PresentationType;
  sceneId?: string | null;
  createdAt: string;
}

export interface GameTurnResult {
  responderId: string;
  responderName: string;
  sceneGoal: string;
  eventSeed?: string | null;
  turns: PresentedTurn[];
  primaryDialogue: string;
  primaryNarration: string;
  primaryReply: string;
  stateDiff: TurnStateDiff;
}

export interface GameTurnDebug {
  targetLocationId: string;
  sceneId: string;
  selectedMemorySummaries: string[];
  recentTurnDigest: string[];
  directorNote: string;
  characterDialogue: string;
  characterNarration: string;
  characterReply: string;
}

export interface LongMemoryItem {
  id: string;
  sessionId: string;
  responderId: string;
  characterIds: string[];
  locationId?: string | null;
  memoryType: string;
  retrievalSummary: string;
  displaySummary: string;
  createdAt: string;
  importance: number;
  salience: number;
}

export interface LongMemoryProfile {
  characterId: string;
  relationshipStage: string;
  playerImageSummary: string;
  relationshipSummary: string;
  retrievalSummary: string;
  displaySummary: string;
  displayTeaser: string;
  openThreads: string[];
  lastInteractionAt?: string | null;
}

export interface ArchivePromotionSummary {
  promotedCount: number;
  profileCount: number;
}

export interface LongMemoryState {
  profiles: Record<string, LongMemoryProfile>;
  recentItems: LongMemoryItem[];
  selectedItems: LongMemoryItem[];
  archivePromotion?: ArchivePromotionSummary | null;
}

export interface GameSessionStateResponse {
  session: GameSession;
  scene: SceneSnapshot;
  longMemory: LongMemoryState;
}

export interface GameTurnResponse extends GameSessionStateResponse {
  acknowledged: boolean;
  result: GameTurnResult;
  debug: GameTurnDebug;
}
