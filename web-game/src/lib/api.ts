import type {
  CharacterCardListResponse,
  GameSessionListResponse,
  GameSessionStateResponse,
  GameTurnResponse,
  Worldbook,
  WorldbookListResponse,
} from './types';

const API_BASE = import.meta.env.VITE_GAME_API_BASE_URL || '';

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function listWorldbooks() {
  return requestJson<WorldbookListResponse>('/game/worldbooks');
}

export async function getWorldbook(worldbookId: string) {
  return requestJson<Worldbook>(`/game/worldbooks/${worldbookId}`);
}

export async function listCharacters(worldbookId?: string) {
  const query = worldbookId ? `?worldbookId=${encodeURIComponent(worldbookId)}` : '';
  return requestJson<CharacterCardListResponse>(`/game/character-cards${query}`);
}

export async function listSessions() {
  return requestJson<GameSessionListResponse>('/game/sessions');
}

export async function getSession(sessionId: string) {
  return requestJson<GameSessionStateResponse>(`/game/sessions/${sessionId}`);
}

export async function createSession(payload: {
  worldbookId: string;
  characterIds: string[];
  title: string;
  openingLocationId?: string;
}) {
  return requestJson<GameSessionStateResponse>('/game/sessions', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function sendTurn(sessionId: string, message: string) {
  return requestJson<GameTurnResponse>(`/game/sessions/${sessionId}/turns`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
}
