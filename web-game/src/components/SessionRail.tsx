interface SessionRailProps {
  worldbooks: Array<{
    id: string;
    title: string;
    version: string;
    genre: string[];
    tone: string[];
    locationCount: number;
  }>;
  selectedWorldbookId: string;
  onSelectWorldbook: (worldbookId: string) => void;
  worldbookCharacters: Array<{
    id: string;
    name: string;
    role: string;
    personaTags: string[];
  }>;
  sessions: Array<{
    id: string;
    title: string;
    status: string;
    currentLocationId: string;
    currentCast: string[];
  }>;
  activeSessionId: string;
  onSelectSession: (sessionId: string) => void;
  onOpenSessionComposer: () => void;
  creatingSession: boolean;
}

export function SessionRail({
  worldbooks,
  selectedWorldbookId,
  onSelectWorldbook,
  worldbookCharacters,
  sessions,
  activeSessionId,
  onSelectSession,
  onOpenSessionComposer,
  creatingSession,
}: SessionRailProps) {
  return (
    <aside className="session-rail">
      <div className="rail-brand">
        <p className="eyebrow">{'\u96fe\u591c\u6863\u6848'}</p>
        <h1>{'\u96fe\u591c\u604b\u7231\u6863\u6848\u5ba4'}</h1>
        <p className="brand-copy">{'\u4e00\u8fb9\u770b\u4e16\u754c\u8bbe\u5b9a\uff0c\u4e00\u8fb9\u8ba9\u5bfc\u6f14\u4e0e\u89d2\u8272\u5728\u540c\u4e00\u4e2a\u591c\u8272\u821e\u53f0\u91cc\u9192\u8fc7\u6765\u3002'}</p>
      </div>

      <section className="rail-section">
        <div className="section-heading">
          <span>{'\u4e16\u754c\u89c2'}</span>
          <span>{worldbooks.length}</span>
        </div>
        <div className="worldbook-list">
          {worldbooks.length ? (
            worldbooks.map((worldbook) => {
              const selected = worldbook.id === selectedWorldbookId;
              return (
                <button
                  key={worldbook.id}
                  className={`worldbook-pill${selected ? ' is-selected' : ''}`}
                  onClick={() => onSelectWorldbook(worldbook.id)}
                  type="button"
                >
                  <div>
                    <strong>{worldbook.title}</strong>
                    <span>{[...worldbook.genre, ...worldbook.tone].slice(0, 3).join(' \u00b7 ') || '\u672a\u6807\u6ce8\u98ce\u683c'}</span>
                  </div>
                  <small>{worldbook.locationCount} {'\u4e2a\u573a\u666f'}</small>
                </button>
              );
            })
          ) : (
            <div className="rail-empty">{'\u8fd8\u6ca1\u6709 worldbook\uff0c\u5148\u5bfc\u5165\u4e00\u5957\u4e16\u754c\u89c2\u8bbe\u5b9a\u3002'}</div>
          )}
        </div>
      </section>

      <section className="rail-section">
        <div className="section-heading">
          <span>{'\u89d2\u8272\u8349\u7a3f'}</span>
          <span>{worldbookCharacters.length}</span>
        </div>
        <div className="cast-list">
          {worldbookCharacters.length ? (
            worldbookCharacters.map((character) => (
              <div className="cast-row" key={character.id}>
                <div>
                  <strong>{character.name}</strong>
                  <p>{character.role || '\u89d2\u8272\u672a\u6807\u6ce8\u5b9a\u4f4d'}</p>
                </div>
                <span>{character.personaTags.slice(0, 2).join(' / ') || '\u5f85\u8865\u6807\u7b7e'}</span>
              </div>
            ))
          ) : (
            <div className="rail-empty">{'\u9009\u4e2d\u4e00\u4e2a worldbook \u540e\uff0c\u8fd9\u91cc\u4f1a\u663e\u793a\u53ef\u7528\u89d2\u8272\u5361\u3002'}</div>
          )}
        </div>
        <button className="create-session-button" onClick={onOpenSessionComposer} type="button" disabled={creatingSession || !selectedWorldbookId}>
          {creatingSession ? '\u6b63\u5728\u70b9\u4eae\u7b2c\u4e00\u5e55\u2026' : '\u7b56\u5212\u8fd9\u4e00\u591c\u7684\u5f00\u573a'}
        </button>
      </section>

      <section className="rail-section rail-section--fill">
        <div className="section-heading">
          <span>{'\u4f1a\u8bdd'}</span>
          <span>{sessions.length}</span>
        </div>
        <div className="session-list">
          {sessions.length ? (
            sessions.map((session) => {
              const active = session.id === activeSessionId;
              return (
                <button
                  key={session.id}
                  className={`session-row${active ? ' is-active' : ''}`}
                  onClick={() => onSelectSession(session.id)}
                  type="button"
                >
                  <div>
                    <strong>{session.title}</strong>
                    <p>{session.currentLocationId} {'\u00b7'} {session.status}</p>
                  </div>
                  <span>{session.currentCast.length} {'\u4eba\u5728\u573a'}</span>
                </button>
              );
            })
          ) : (
            <div className="rail-empty rail-empty--session">{'\u8fd8\u6ca1\u6709 session\u3002\u9009\u4e16\u754c\u3001\u770b\u89d2\u8272\uff0c\u7136\u540e\u8ba9\u7b2c\u4e00\u573a\u591c\u665a\u5f00\u59cb\u3002'}</div>
          )}
        </div>
      </section>
    </aside>
  );
}
