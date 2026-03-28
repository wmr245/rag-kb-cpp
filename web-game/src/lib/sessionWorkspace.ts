import type { GameSessionSummary, WorldbookSummary } from './types';

const WORKSPACE_MEMORY_KEY = 'rag-web-game:session-workspace-memory';

export interface ImportLaunchCue {
  worldbookId: string;
  worldbookTitle: string;
  characterCount: number;
  importedAt: string;
}

export interface SessionWorkspaceMemory {
  lastSelectedWorldbookId: string;
  lastActiveSessionId: string;
  recentSessionIdsByWorldbook: Record<string, string>;
  importLaunchCue: ImportLaunchCue | null;
}

const EMPTY_WORKSPACE_MEMORY: SessionWorkspaceMemory = {
  lastSelectedWorldbookId: '',
  lastActiveSessionId: '',
  recentSessionIdsByWorldbook: {},
  importLaunchCue: null,
};

export function readSessionWorkspaceMemory(): SessionWorkspaceMemory {
  if (typeof window === 'undefined') return EMPTY_WORKSPACE_MEMORY;

  try {
    const raw = window.localStorage.getItem(WORKSPACE_MEMORY_KEY);
    if (!raw) return EMPTY_WORKSPACE_MEMORY;
    const parsed = JSON.parse(raw) as Partial<SessionWorkspaceMemory>;

    return {
      lastSelectedWorldbookId:
        typeof parsed.lastSelectedWorldbookId === 'string' ? parsed.lastSelectedWorldbookId : '',
      lastActiveSessionId: typeof parsed.lastActiveSessionId === 'string' ? parsed.lastActiveSessionId : '',
      recentSessionIdsByWorldbook:
        parsed.recentSessionIdsByWorldbook && typeof parsed.recentSessionIdsByWorldbook === 'object'
          ? Object.fromEntries(
              Object.entries(parsed.recentSessionIdsByWorldbook).filter(
                (entry): entry is [string, string] => typeof entry[0] === 'string' && typeof entry[1] === 'string',
              ),
            )
          : {},
      importLaunchCue:
        parsed.importLaunchCue &&
        typeof parsed.importLaunchCue === 'object' &&
        typeof parsed.importLaunchCue.worldbookId === 'string' &&
        typeof parsed.importLaunchCue.worldbookTitle === 'string' &&
        typeof parsed.importLaunchCue.characterCount === 'number' &&
        typeof parsed.importLaunchCue.importedAt === 'string'
          ? parsed.importLaunchCue
          : null,
    };
  } catch {
    return EMPTY_WORKSPACE_MEMORY;
  }
}

export function writeSessionWorkspaceMemory(memory: SessionWorkspaceMemory) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(WORKSPACE_MEMORY_KEY, JSON.stringify(memory));
}

export function rememberSelectedWorldbook(
  memory: SessionWorkspaceMemory,
  worldbookId: string,
): SessionWorkspaceMemory {
  return {
    ...memory,
    lastSelectedWorldbookId: worldbookId,
  };
}

export function rememberSessionActivation(
  memory: SessionWorkspaceMemory,
  session: Pick<GameSessionSummary, 'id' | 'worldbookId'>,
): SessionWorkspaceMemory {
  return {
    ...memory,
    lastSelectedWorldbookId: session.worldbookId,
    lastActiveSessionId: session.id,
    recentSessionIdsByWorldbook: {
      ...memory.recentSessionIdsByWorldbook,
      [session.worldbookId]: session.id,
    },
    importLaunchCue:
      memory.importLaunchCue?.worldbookId === session.worldbookId ? null : memory.importLaunchCue,
  };
}

export function rememberImportLaunchCue(
  memory: SessionWorkspaceMemory,
  cue: ImportLaunchCue | null,
): SessionWorkspaceMemory {
  return {
    ...memory,
    lastSelectedWorldbookId: cue?.worldbookId || memory.lastSelectedWorldbookId,
    importLaunchCue: cue,
  };
}

export function sortSessionsByUpdatedAt<T extends Pick<GameSessionSummary, 'updatedAt'>>(sessions: T[]) {
  return [...sessions].sort((left, right) => {
    const leftTime = new Date(left.updatedAt).getTime();
    const rightTime = new Date(right.updatedAt).getTime();
    return rightTime - leftTime;
  });
}

export function resolvePreferredWorldbookId(params: {
  worldbooks: WorldbookSummary[];
  sessions: GameSessionSummary[];
  memory: SessionWorkspaceMemory;
}) {
  const { worldbooks, sessions, memory } = params;
  const worldbookIds = new Set(worldbooks.map((item) => item.id));
  if (memory.lastSelectedWorldbookId && worldbookIds.has(memory.lastSelectedWorldbookId)) {
    return memory.lastSelectedWorldbookId;
  }

  const sortedSessions = sortSessionsByUpdatedAt(sessions.filter((session) => session.status === 'active'));
  const mostRecentWorldbookId = sortedSessions[0]?.worldbookId;
  if (mostRecentWorldbookId && worldbookIds.has(mostRecentWorldbookId)) {
    return mostRecentWorldbookId;
  }

  return worldbooks[0]?.id || '';
}

export function resolvePreferredSessionId(params: {
  worldbookId: string;
  sessions: GameSessionSummary[];
  memory: SessionWorkspaceMemory;
}) {
  const { worldbookId, sessions, memory } = params;
  if (!worldbookId) return '';

  const scopedSessions = sortSessionsByUpdatedAt(
    sessions.filter((session) => session.worldbookId === worldbookId && session.status === 'active'),
  );
  if (!scopedSessions.length) return '';

  const rememberedId = memory.recentSessionIdsByWorldbook[worldbookId];
  if (rememberedId && scopedSessions.some((session) => session.id === rememberedId)) {
    return rememberedId;
  }

  if (
    memory.lastActiveSessionId &&
    scopedSessions.some((session) => session.id === memory.lastActiveSessionId)
  ) {
    return memory.lastActiveSessionId;
  }

  return scopedSessions[0]?.id || '';
}
