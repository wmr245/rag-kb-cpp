import { readSessionWorkspaceMemory, type ImportLaunchCue } from './sessionWorkspace';
import type { AssistantSummary, CharacterCardSummary, GameSessionSummary, WorldbookSummary } from './types';

const WORKSPACE_MEMORY_KEY = 'rag-web-game:assistant-workspace-memory';

export interface AssistantWorkspaceMemory {
  lastSelectedAssistantId: string;
  lastSelectedWorldbookId: string;
  lastActiveSessionId: string;
  recentSessionIdsByAssistant: Record<string, string>;
  recentSessionIdsByWorldbook: Record<string, string>;
  importLaunchCue: ImportLaunchCue | null;
}

const EMPTY_WORKSPACE_MEMORY: AssistantWorkspaceMemory = {
  lastSelectedAssistantId: '',
  lastSelectedWorldbookId: '',
  lastActiveSessionId: '',
  recentSessionIdsByAssistant: {},
  recentSessionIdsByWorldbook: {},
  importLaunchCue: null,
};

function safeObjectRecord(value: unknown) {
  if (!value || typeof value !== 'object') return {};
  return Object.fromEntries(
    Object.entries(value).filter(
      (entry): entry is [string, string] => typeof entry[0] === 'string' && typeof entry[1] === 'string',
    ),
  );
}

export function buildProjectedAssistants(params: {
  worldbooks: WorldbookSummary[];
  characters: CharacterCardSummary[];
  sessions: GameSessionSummary[];
}): AssistantSummary[] {
  const { worldbooks, characters, sessions } = params;
  const worldbookTitleById = new Map(worldbooks.map((worldbook) => [worldbook.id, worldbook.title]));

  return [...characters]
    .map((character) => {
      const assistantId = `assistant:${character.id}`;
      const relatedSessions = sessions.filter(
        (session) =>
          session.assistantId
            ? session.assistantId === assistantId
            : session.worldbookId === character.worldbookId && session.characterIds.includes(character.id),
      );
      const activeSessionCount = relatedSessions.filter((session) => session.status === 'active').length;
      const archivedSessionCount = relatedSessions.filter((session) => session.status === 'archived').length;
      const recentSession =
        [...relatedSessions].sort((left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime())[0] ||
        null;

      const status = activeSessionCount
        ? 'active'
        : archivedSessionCount
          ? 'archived'
          : 'draft';
      const memoryStatus = relatedSessions.length ? 'ready' : 'empty';
      const summary = character.personaTags.slice(0, 3).join(' · ') || character.role || '等待补充助手摘要';

      return {
        id: assistantId,
        source: 'projected_character',
        name: character.name,
        worldbookId: character.worldbookId,
        worldbookTitle: worldbookTitleById.get(character.worldbookId) || character.worldbookId,
        characterId: character.id,
        characterRole: character.role,
        personaTags: character.personaTags,
        userScope: 'default_player',
        summary,
        status,
        memoryStatus,
        updatedAt: recentSession?.updatedAt || '',
        sessionCount: relatedSessions.length,
        activeSessionCount,
        archivedSessionCount,
        recentSessionId: recentSession?.id || '',
      } satisfies AssistantSummary;
    })
    .sort((left, right) => {
      if (left.status !== right.status) {
        const rank = { active: 0, draft: 1, archived: 2 };
        return rank[left.status] - rank[right.status];
      }
      const timeDelta = new Date(right.updatedAt || 0).getTime() - new Date(left.updatedAt || 0).getTime();
      if (timeDelta !== 0) return timeDelta;
      return left.name.localeCompare(right.name, 'zh-CN');
    });
}

export function readAssistantWorkspaceMemory(): AssistantWorkspaceMemory {
  if (typeof window === 'undefined') return EMPTY_WORKSPACE_MEMORY;

  try {
    const raw = window.localStorage.getItem(WORKSPACE_MEMORY_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<AssistantWorkspaceMemory>;
      return {
        lastSelectedAssistantId:
          typeof parsed.lastSelectedAssistantId === 'string' ? parsed.lastSelectedAssistantId : '',
        lastSelectedWorldbookId:
          typeof parsed.lastSelectedWorldbookId === 'string' ? parsed.lastSelectedWorldbookId : '',
        lastActiveSessionId: typeof parsed.lastActiveSessionId === 'string' ? parsed.lastActiveSessionId : '',
        recentSessionIdsByAssistant: safeObjectRecord(parsed.recentSessionIdsByAssistant),
        recentSessionIdsByWorldbook: safeObjectRecord(parsed.recentSessionIdsByWorldbook),
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
    }
  } catch {
    return EMPTY_WORKSPACE_MEMORY;
  }

  const legacy = readSessionWorkspaceMemory();
  return {
    ...EMPTY_WORKSPACE_MEMORY,
    lastSelectedWorldbookId: legacy.lastSelectedWorldbookId,
    lastActiveSessionId: legacy.lastActiveSessionId,
    recentSessionIdsByWorldbook: legacy.recentSessionIdsByWorldbook,
    importLaunchCue: legacy.importLaunchCue,
  };
}

export function writeAssistantWorkspaceMemory(memory: AssistantWorkspaceMemory) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(WORKSPACE_MEMORY_KEY, JSON.stringify(memory));
}

export function rememberSelectedAssistant(
  memory: AssistantWorkspaceMemory,
  assistant: Pick<AssistantSummary, 'id' | 'worldbookId'>,
): AssistantWorkspaceMemory {
  return {
    ...memory,
    lastSelectedAssistantId: assistant.id,
    lastSelectedWorldbookId: assistant.worldbookId,
  };
}

export function rememberSelectedWorldbook(
  memory: AssistantWorkspaceMemory,
  worldbookId: string,
): AssistantWorkspaceMemory {
  return {
    ...memory,
    lastSelectedWorldbookId: worldbookId,
  };
}

export function rememberAssistantSessionActivation(
  memory: AssistantWorkspaceMemory,
  assistantId: string,
  session: Pick<GameSessionSummary, 'id' | 'worldbookId'>,
): AssistantWorkspaceMemory {
  return {
    ...memory,
    lastSelectedAssistantId: assistantId || memory.lastSelectedAssistantId,
    lastSelectedWorldbookId: session.worldbookId,
    lastActiveSessionId: session.id,
    recentSessionIdsByAssistant: assistantId
      ? {
          ...memory.recentSessionIdsByAssistant,
          [assistantId]: session.id,
        }
      : memory.recentSessionIdsByAssistant,
    recentSessionIdsByWorldbook: {
      ...memory.recentSessionIdsByWorldbook,
      [session.worldbookId]: session.id,
    },
    importLaunchCue:
      memory.importLaunchCue?.worldbookId === session.worldbookId ? null : memory.importLaunchCue,
  };
}

export function rememberImportLaunchCue(
  memory: AssistantWorkspaceMemory,
  cue: ImportLaunchCue | null,
): AssistantWorkspaceMemory {
  return {
    ...memory,
    lastSelectedWorldbookId: cue?.worldbookId || memory.lastSelectedWorldbookId,
    importLaunchCue: cue,
  };
}

export function resolvePreferredAssistantId(params: {
  assistants: AssistantSummary[];
  selectedWorldbookId: string;
  memory: AssistantWorkspaceMemory;
}) {
  const { assistants, selectedWorldbookId, memory } = params;
  const byId = new Set(assistants.map((assistant) => assistant.id));
  if (memory.lastSelectedAssistantId && byId.has(memory.lastSelectedAssistantId)) {
    return memory.lastSelectedAssistantId;
  }

  const scopedAssistants = selectedWorldbookId
    ? assistants.filter((assistant) => assistant.worldbookId === selectedWorldbookId)
    : assistants;

  return scopedAssistants[0]?.id || assistants[0]?.id || '';
}

export function resolveAssistantIdForSession(params: {
  session: Pick<GameSessionSummary, 'assistantId' | 'worldbookId' | 'characterIds'>;
  assistants: AssistantSummary[];
  fallbackAssistantId?: string;
}) {
  const { session, assistants, fallbackAssistantId = '' } = params;
  if (session.assistantId && assistants.some((assistant) => assistant.id === session.assistantId)) {
    return session.assistantId;
  }

  if (
    fallbackAssistantId &&
    assistants.some(
      (assistant) =>
        assistant.id === fallbackAssistantId &&
        assistant.worldbookId === session.worldbookId &&
        session.characterIds.includes(assistant.characterId),
    )
  ) {
    return fallbackAssistantId;
  }

  return (
    assistants.find(
      (assistant) =>
        assistant.worldbookId === session.worldbookId && session.characterIds.includes(assistant.characterId),
    )?.id || ''
  );
}

export function resolvePreferredSessionIdForAssistant(params: {
  assistant: AssistantSummary | null;
  sessions: GameSessionSummary[];
  memory: AssistantWorkspaceMemory;
}) {
  const { assistant, sessions, memory } = params;
  if (!assistant) return '';

  const scopedSessions = [...sessions]
    .filter(
      (session) =>
        session.status === 'active' &&
        (session.assistantId
          ? session.assistantId === assistant.id
          : session.worldbookId === assistant.worldbookId && session.characterIds.includes(assistant.characterId)),
    )
    .sort((left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime());

  if (!scopedSessions.length) return '';

  const rememberedByAssistant = memory.recentSessionIdsByAssistant[assistant.id];
  if (rememberedByAssistant && scopedSessions.some((session) => session.id === rememberedByAssistant)) {
    return rememberedByAssistant;
  }

  const rememberedByWorldbook = memory.recentSessionIdsByWorldbook[assistant.worldbookId];
  if (rememberedByWorldbook && scopedSessions.some((session) => session.id === rememberedByWorldbook)) {
    return rememberedByWorldbook;
  }

  if (memory.lastActiveSessionId && scopedSessions.some((session) => session.id === memory.lastActiveSessionId)) {
    return memory.lastActiveSessionId;
  }

  return scopedSessions[0]?.id || '';
}
