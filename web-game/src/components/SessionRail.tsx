import { memo, type FormEvent } from 'react';
import { Archive, PencilLine, RotateCcw, Save, X } from 'lucide-react';
import type { GameSessionSummary } from '../lib/types';

interface RailWorldbook {
  id: string;
  title: string;
  version: string;
  genre: string[];
  tone: string[];
  locationCount: number;
}

interface RailCharacter {
  id: string;
  name: string;
  role: string;
  personaTags: string[];
}

interface RailSessionItem {
  id: string;
  title: string;
  status: string;
  updatedAt: string;
  currentLocationLabel: string;
  currentCastCount: number;
  isActive: boolean;
  summary: GameSessionSummary;
}

interface SessionRailProps {
  worldbooks: RailWorldbook[];
  selectedWorldbookId: string;
  selectedWorldbookTitle: string;
  onSelectWorldbook: (worldbookId: string) => void;
  worldbookCharacters: RailCharacter[];
  activeSessions: RailSessionItem[];
  archivedSessions: RailSessionItem[];
  recentSession: RailSessionItem | null;
  renamingSessionId: string;
  renameDraft: string;
  updatingSessionId: string;
  onRenameDraftChange: (value: string) => void;
  onStartRenameSession: (session: GameSessionSummary) => void;
  onCancelRenameSession: () => void;
  onSubmitRenameSession: () => void;
  onSelectSession: (sessionId: string) => void;
  onResumeRecentSession: (sessionId: string) => void;
  onArchiveSession: (sessionId: string) => void;
  onRestoreSession: (sessionId: string) => void;
  onOpenSessionComposer: () => void;
  onOpenSeedImport: () => void;
  creatingSession: boolean;
  launchCue:
    | {
        worldbookTitle: string;
        characterCount: number;
      }
    | null;
}

const relativeFormatter = new Intl.RelativeTimeFormat('zh-CN', { numeric: 'auto' });

function formatSessionRecency(timestamp: string) {
  const targetTime = new Date(timestamp).getTime();
  if (Number.isNaN(targetTime)) return '刚刚更新';

  const deltaMs = targetTime - Date.now();
  const minutes = Math.round(deltaMs / 60000);
  if (Math.abs(minutes) < 60) {
    return relativeFormatter.format(minutes, 'minute');
  }

  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) {
    return relativeFormatter.format(hours, 'hour');
  }

  const days = Math.round(hours / 24);
  return relativeFormatter.format(days, 'day');
}

function SessionRow(props: {
  session: RailSessionItem;
  renaming: boolean;
  renameDraft: string;
  updatingSessionId: string;
  onRenameDraftChange: (value: string) => void;
  onStartRenameSession: (session: GameSessionSummary) => void;
  onCancelRenameSession: () => void;
  onSubmitRenameSession: () => void;
  onSelectSession: (sessionId: string) => void;
  onArchiveSession: (sessionId: string) => void;
  onRestoreSession: (sessionId: string) => void;
}) {
  const {
    session,
    renaming,
    renameDraft,
    updatingSessionId,
    onRenameDraftChange,
    onStartRenameSession,
    onCancelRenameSession,
    onSubmitRenameSession,
    onSelectSession,
    onArchiveSession,
    onRestoreSession,
  } = props;

  function handleRenameSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmitRenameSession();
  }

  const busy = updatingSessionId === session.id;

  return (
    <div className={`session-row-shell${session.isActive ? ' is-active' : ''}${busy ? ' is-busy' : ''}`}>
      {renaming ? (
        <form className="session-rename-form" onSubmit={handleRenameSubmit}>
          <input
            className="session-rename-input"
            value={renameDraft}
            onChange={(event) => onRenameDraftChange(event.target.value)}
            placeholder="给这条记忆线起个名字"
            autoFocus
          />
          <div className="session-row-actions">
            <button className="ghost-button session-action-button" type="submit" disabled={!renameDraft.trim() || busy}>
              <Save size={14} />
              {'保存'}
            </button>
            <button className="ghost-button session-action-button" type="button" onClick={onCancelRenameSession} disabled={busy}>
              <X size={14} />
              {'取消'}
            </button>
          </div>
        </form>
      ) : (
        <>
          <button className={`session-row${session.isActive ? ' is-active' : ''}`} onClick={() => onSelectSession(session.id)} type="button">
            <div className="session-row-copy">
              <strong>{session.title}</strong>
              <p>{`${session.currentLocationLabel} · ${session.status}`}</p>
            </div>
            <div className="session-row-meta">
              <span>{`${session.currentCastCount} 人在场`}</span>
              <small>{formatSessionRecency(session.updatedAt)}</small>
            </div>
          </button>
          <div className="session-row-actions">
            <button
              className="ghost-button session-action-button"
              onClick={() => onStartRenameSession(session.summary)}
              type="button"
              disabled={busy}
            >
              <PencilLine size={14} />
              {'重命名'}
            </button>
            {session.status === 'archived' ? (
              <button
                className="ghost-button session-action-button"
                onClick={() => onRestoreSession(session.id)}
                type="button"
                disabled={busy}
              >
                <RotateCcw size={14} />
                {'恢复'}
              </button>
            ) : (
              <button
                className="ghost-button session-action-button"
                onClick={() => onArchiveSession(session.id)}
                type="button"
                disabled={busy}
              >
                <Archive size={14} />
                {'归档'}
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export const SessionRail = memo(function SessionRail({
  worldbooks,
  selectedWorldbookId,
  selectedWorldbookTitle,
  onSelectWorldbook,
  worldbookCharacters,
  activeSessions,
  archivedSessions,
  recentSession,
  renamingSessionId,
  renameDraft,
  updatingSessionId,
  onRenameDraftChange,
  onStartRenameSession,
  onCancelRenameSession,
  onSubmitRenameSession,
  onSelectSession,
  onResumeRecentSession,
  onArchiveSession,
  onRestoreSession,
  onOpenSessionComposer,
  onOpenSeedImport,
  creatingSession,
  launchCue,
}: SessionRailProps) {
  const hasSelectedWorldbook = Boolean(selectedWorldbookId);
  const sessionCount = activeSessions.length + archivedSessions.length;

  return (
    <aside className="session-rail">
      <div className="rail-brand">
        <p className="eyebrow">{'雾夜档案'}</p>
        <h1>{'雾夜恋爱档案室'}</h1>
        <p className="brand-copy">{'一边看世界设定，一边让导演与角色在同一个夜色舞台里醒过来。'}</p>
      </div>

      {launchCue ? (
        <section className="rail-section rail-section--callout">
          <div className="session-restore-card session-restore-card--launch">
            <span className="preview-label">{'导入完成后的下一步'}</span>
            <strong>{`先为「${launchCue.worldbookTitle}」点亮第一幕`}</strong>
            <p>{`${launchCue.characterCount} 张角色卡已经写入。先确认开场地点和阵容，再让这一夜开始累积长期记忆。`}</p>
            <button className="primary-button rail-card-button" onClick={onOpenSessionComposer} type="button">
              {'现在开场'}
            </button>
          </div>
        </section>
      ) : null}

      {recentSession ? (
        <section className="rail-section rail-section--callout">
          <div className="session-restore-card">
            <div className="session-restore-copy">
              <span className="preview-label">{'继续最近一局'}</span>
              <strong>{recentSession.title}</strong>
              <p>{`${recentSession.currentLocationLabel} · ${formatSessionRecency(recentSession.updatedAt)}`}</p>
            </div>
            <button
              className="ghost-button rail-card-button"
              onClick={() => onResumeRecentSession(recentSession.id)}
              type="button"
            >
              {recentSession.isActive ? '回到当前会话' : '恢复导演台'}
            </button>
          </div>
        </section>
      ) : null}

      <section className="rail-section">
        <div className="section-heading">
          <span>{'世界观'}</span>
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
                    <span>{[...worldbook.genre, ...worldbook.tone].slice(0, 3).join(' · ') || '未标注风格'}</span>
                  </div>
                  <small>{worldbook.locationCount} {'个场景'}</small>
                </button>
              );
            })
          ) : (
            <div className="rail-empty">{'还没有 worldbook，先导入一套世界观设定。'}</div>
          )}
        </div>
        <button className="ghost-button rail-secondary-button" onClick={onOpenSeedImport} type="button">
          {worldbooks.length ? '再导入一套设定' : '导入第一套设定'}
        </button>
      </section>

      <section className="rail-section">
        <div className="section-heading">
          <span>{'角色草稿'}</span>
          <span>{worldbookCharacters.length}</span>
        </div>
        <div className="cast-list">
          {worldbookCharacters.length ? (
            worldbookCharacters.map((character) => (
              <div className="cast-row" key={character.id}>
                <div>
                  <strong>{character.name}</strong>
                  <p>{character.role || '角色未标注定位'}</p>
                </div>
                <span>{character.personaTags.slice(0, 2).join(' / ') || '待补标签'}</span>
              </div>
            ))
          ) : (
            <div className="rail-empty">{'选中一个 worldbook 后，这里会显示可用角色卡。'}</div>
          )}
        </div>
        <button className="create-session-button" onClick={onOpenSessionComposer} type="button" disabled={creatingSession || !selectedWorldbookId}>
          {creatingSession ? '正在点亮第一幕…' : '策划这一夜的开场'}
        </button>
      </section>

      <section className="rail-section rail-section--fill">
        <div className="section-heading">
          <span>{hasSelectedWorldbook ? `${selectedWorldbookTitle || '当前世界'}的会话` : '会话'}</span>
          <span>{sessionCount}</span>
        </div>
        <div className="session-list">
          {activeSessions.length ? (
            <section className="session-group">
              <div className="session-group-heading">
                <span>{'进行中的记忆线'}</span>
                <small>{activeSessions.length}</small>
              </div>
              <div className="session-group-list">
                {activeSessions.map((session) => (
                  <SessionRow
                    key={session.id}
                    session={session}
                    renaming={renamingSessionId === session.id}
                    renameDraft={renameDraft}
                    updatingSessionId={updatingSessionId}
                    onRenameDraftChange={onRenameDraftChange}
                    onStartRenameSession={onStartRenameSession}
                    onCancelRenameSession={onCancelRenameSession}
                    onSubmitRenameSession={onSubmitRenameSession}
                    onSelectSession={onSelectSession}
                    onArchiveSession={onArchiveSession}
                    onRestoreSession={onRestoreSession}
                  />
                ))}
              </div>
            </section>
          ) : null}

          {archivedSessions.length ? (
            <section className="session-group">
              <div className="session-group-heading">
                <span>{'已归档记忆线'}</span>
                <small>{archivedSessions.length}</small>
              </div>
              <div className="session-group-list">
                {archivedSessions.map((session) => (
                  <SessionRow
                    key={session.id}
                    session={session}
                    renaming={renamingSessionId === session.id}
                    renameDraft={renameDraft}
                    updatingSessionId={updatingSessionId}
                    onRenameDraftChange={onRenameDraftChange}
                    onStartRenameSession={onStartRenameSession}
                    onCancelRenameSession={onCancelRenameSession}
                    onSubmitRenameSession={onSubmitRenameSession}
                    onSelectSession={onSelectSession}
                    onArchiveSession={onArchiveSession}
                    onRestoreSession={onRestoreSession}
                  />
                ))}
              </div>
            </section>
          ) : null}

          {!sessionCount ? (
            <div className="rail-empty rail-empty--session">
              {hasSelectedWorldbook
                ? '这个世界还没有会话。先策划开场，让第一条记忆线开始积累。'
                : '还没有 session。先选世界、看角色，然后让第一场夜晚开始。'}
            </div>
          ) : null}
        </div>
      </section>
    </aside>
  );
});
