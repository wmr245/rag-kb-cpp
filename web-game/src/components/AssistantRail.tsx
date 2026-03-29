import { memo, type FormEvent } from 'react';
import { Archive, PencilLine, RotateCcw, Save, Trash2, X } from 'lucide-react';
import type { AssistantSummary, GameSessionSummary, WorldbookSummary } from '../lib/types';

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

interface AssistantRailProps {
  assistants: AssistantSummary[];
  selectedAssistantId: string;
  selectedAssistant: AssistantSummary | null;
  activatingAssistantId: string;
  selectedWorldbook: WorldbookSummary | null;
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
  onActivateAssistant: (assistant: AssistantSummary) => void;
  onSelectAssistant: (assistantId: string) => void;
  onSelectSession: (sessionId: string) => void;
  onResumeRecentSession: (sessionId: string) => void;
  onArchiveSession: (sessionId: string) => void;
  onRestoreSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
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
  onDeleteSession: (sessionId: string) => void;
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
    onDeleteSession,
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
            placeholder="给这段对话快照起个名字"
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
          <button
            className={`session-row${session.isActive ? ' is-active' : ''}`}
            data-testid={`session-open-${session.id}`}
            onClick={() => onSelectSession(session.id)}
            type="button"
          >
            <div className="session-row-copy">
              <strong>{session.title}</strong>
              <p>{`${session.currentLocationLabel} · ${session.status}`}</p>
            </div>
            <div className="session-row-meta">
              <span>{`${session.currentCastCount} 位参与者`}</span>
              <small>{formatSessionRecency(session.updatedAt)}</small>
            </div>
          </button>
          <div className="session-row-actions">
            <button
              className="ghost-button session-action-button"
              data-testid={`session-rename-${session.id}`}
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
                data-testid={`session-restore-${session.id}`}
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
                data-testid={`session-archive-${session.id}`}
                onClick={() => onArchiveSession(session.id)}
                type="button"
                disabled={busy}
              >
                <Archive size={14} />
                {'归档'}
              </button>
            )}
            <button
              className="ghost-button session-action-button"
              data-testid={`session-delete-${session.id}`}
              onClick={() => onDeleteSession(session.id)}
              type="button"
              disabled={busy}
            >
              <Trash2 size={14} />
              {'删除'}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export const AssistantRail = memo(function AssistantRail({
  assistants,
  selectedAssistantId,
  selectedAssistant,
  activatingAssistantId,
  selectedWorldbook,
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
  onActivateAssistant,
  onSelectAssistant,
  onSelectSession,
  onResumeRecentSession,
  onArchiveSession,
  onRestoreSession,
  onDeleteSession,
  onOpenSessionComposer,
  onOpenSeedImport,
  creatingSession,
  launchCue,
}: AssistantRailProps) {
  const sessionCount = activeSessions.length + archivedSessions.length;
  const supportingCharacters = worldbookCharacters.filter((character) => character.id !== selectedAssistant?.characterId);
  const selectedAssistantReady = selectedAssistant?.source === 'assistant';

  return (
    <aside className="session-rail assistant-rail">
      <div className="rail-brand">
        <p className="eyebrow">{'个人助手工作台'}</p>
        <h1>{'雾夜助手'}</h1>
        <p className="brand-copy">{'背景设定、人格卡、持续对话和长期记忆都围绕同一个助手慢慢积累，历史快照退到次级入口。'}</p>
      </div>

      {launchCue ? (
        <section className="rail-section rail-section--callout">
          <div className="session-restore-card session-restore-card--launch">
            <span className="preview-label">{'导入完成后的下一步'}</span>
            <strong>{`先把「${launchCue.worldbookTitle}」收成一个助手`}</strong>
            <p>{`${launchCue.characterCount} 张角色卡已经写入。先选定人格与背景，再开始第一段持续对话。`}</p>
            <button
              className="primary-button rail-card-button"
              data-testid="assistant-primary-action"
              onClick={() => {
                if (selectedAssistant && selectedAssistant.source !== 'assistant') {
                  onActivateAssistant(selectedAssistant);
                  return;
                }
                onOpenSessionComposer();
              }}
              type="button"
            >
              {selectedAssistantReady ? '开始第一段对话' : '先启用当前助手'}
            </button>
          </div>
        </section>
      ) : null}

      {recentSession ? (
        <section className="rail-section rail-section--callout">
          <div className="session-restore-card">
            <div className="session-restore-copy">
              <span className="preview-label">{'继续最近对话'}</span>
              <strong>{recentSession.title}</strong>
              <p>{`${recentSession.currentLocationLabel} · ${formatSessionRecency(recentSession.updatedAt)}`}</p>
            </div>
            <button
              className="ghost-button rail-card-button"
              onClick={() => onResumeRecentSession(recentSession.id)}
              type="button"
            >
              {recentSession.isActive ? '回到当前对话' : '恢复这段快照'}
            </button>
          </div>
        </section>
      ) : null}

      <section className="rail-section">
        <div className="section-heading">
          <span>{'助手列表'}</span>
          <span>{assistants.length}</span>
        </div>
        <div className="worldbook-list" data-testid="assistant-list">
          {assistants.length ? (
            assistants.map((assistant) => {
              const selected = assistant.id === selectedAssistantId;
              const activating = activatingAssistantId === assistant.id;
              const ready = assistant.source === 'assistant';
              return (
                <div
                  className={`session-row-shell${selected ? ' is-active' : ''}`}
                  data-testid={`assistant-row-${assistant.id}`}
                  key={assistant.id}
                >
                  <button
                    className={`worldbook-pill${selected ? ' is-selected' : ''}`}
                    data-testid={`assistant-select-${assistant.id}`}
                    onClick={() => onSelectAssistant(assistant.id)}
                    type="button"
                  >
                    <div>
                      <strong>{assistant.name}</strong>
                      <span>{assistant.summary}</span>
                    </div>
                    <small>{ready ? `${assistant.worldbookTitle} · 已启用` : `${assistant.worldbookTitle} · 待启用`}</small>
                  </button>
                  {!ready ? (
                    <div className="session-row-actions">
                      <button
                        className="ghost-button session-action-button"
                        data-testid={`assistant-activate-${assistant.id}`}
                        onClick={() => onActivateAssistant(assistant)}
                        type="button"
                        disabled={activating}
                      >
                        {activating ? '启用中…' : '启用助手'}
                      </button>
                    </div>
                  ) : null}
                </div>
              );
            })
          ) : (
            <div className="rail-empty">{'还没有可用助手。先导入 worldbook 与角色卡。'}</div>
          )}
        </div>
      </section>

      <section className="rail-section">
        <div className="section-heading">
          <span>{'背景设定'}</span>
          <span>{selectedWorldbook ? 1 : 0}</span>
        </div>
        {selectedWorldbook ? (
          <div className="cast-list">
            <div className="cast-row">
              <div>
                <strong>{selectedWorldbook.title}</strong>
                <p>{[...selectedWorldbook.genre, ...selectedWorldbook.tone].slice(0, 3).join(' · ') || '未标注风格'}</p>
              </div>
              <span>{`${selectedWorldbook.locationCount} 个场景`}</span>
            </div>
          </div>
        ) : (
          <div className="rail-empty">{'选中一个助手后，这里会显示它绑定的背景设定。'}</div>
        )}
        <button className="ghost-button rail-secondary-button" onClick={onOpenSeedImport} type="button">
          {selectedWorldbook ? '导入更多背景设定' : '导入第一套设定'}
        </button>
      </section>

      <section className="rail-section">
        <div className="section-heading">
          <span>{'人格与陪聊角色'}</span>
          <span>{worldbookCharacters.length}</span>
        </div>
        <div className="cast-list">
          {selectedAssistant ? (
            <>
              <div className="cast-row">
                <div>
                  <strong>{selectedAssistant.name}</strong>
                  <p>{selectedAssistant.characterRole || '当前助手人格'}</p>
                </div>
                <span>{selectedAssistant.personaTags.slice(0, 2).join(' / ') || '待补标签'}</span>
              </div>
              {supportingCharacters.slice(0, 4).map((character) => (
                <div className="cast-row" key={character.id}>
                  <div>
                    <strong>{character.name}</strong>
                    <p>{character.role || '辅助角色'}</p>
                  </div>
                  <span>{character.personaTags.slice(0, 2).join(' / ') || '待补标签'}</span>
                </div>
              ))}
            </>
          ) : (
            <div className="rail-empty">{'先选定一个助手人格，这里会显示它和当前背景里的其他角色。'}</div>
          )}
        </div>
        <button
          className="create-session-button"
          data-testid="open-session-composer"
          onClick={() => {
            if (selectedAssistant && selectedAssistant.source !== 'assistant') {
              onActivateAssistant(selectedAssistant);
              return;
            }
            onOpenSessionComposer();
          }}
          type="button"
          disabled={creatingSession || !selectedAssistant || activatingAssistantId === selectedAssistant.id}
        >
          {creatingSession
            ? '正在准备对话片段…'
            : !selectedAssistant
              ? '先选择一个助手'
              : selectedAssistant.source === 'assistant'
                ? '开启新的对话片段'
                : activatingAssistantId === selectedAssistant.id
                  ? '正在启用助手…'
                  : '先启用当前助手'}
        </button>
      </section>

      <section className="rail-section rail-section--fill" data-testid="assistant-snapshot-list">
        <div className="section-heading">
          <span>{selectedAssistant ? `${selectedAssistant.name} 的对话快照` : '对话快照'}</span>
          <span>{sessionCount}</span>
        </div>
        <div className="session-list">
          {activeSessions.length ? (
            <section className="session-group">
              <div className="session-group-heading">
                <span>{'进行中的片段'}</span>
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
                    onDeleteSession={onDeleteSession}
                  />
                ))}
              </div>
            </section>
          ) : null}

          {archivedSessions.length ? (
            <section className="session-group" data-testid="archived-snapshot-group">
              <div className="session-group-heading">
                <span>{'历史快照'}</span>
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
                    onDeleteSession={onDeleteSession}
                  />
                ))}
              </div>
            </section>
          ) : null}

          {!sessionCount ? (
            <div className="rail-empty rail-empty--session">
              {selectedAssistant
                ? selectedAssistant.source === 'assistant'
                  ? '这个助手还没有对话快照。先开启第一段对话，让长期记忆开始积累。'
                  : '这个人格还处在待启用状态。先启用助手，再开始第一段对话。'
                : '还没有选定助手。先导入设定并选中一个人格。'}
            </div>
          ) : null}
        </div>
      </section>
    </aside>
  );
});
