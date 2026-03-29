import { memo } from 'react';
import type { GameSession, GameTurnResult } from '../lib/types';

interface DialogueStageProps {
  session: GameSession | null;
  assistantName: string;
  activeSceneLabel: string;
  actorNames: Record<string, string>;
  lastTurnResult: GameTurnResult | null;
  pending: boolean;
}

function resolveActorName(actorType: string, actorId: string, actorNames: Record<string, string>) {
  if (actorType === 'player') return '玩家';
  return actorNames[actorId] || actorId;
}

export const DialogueStage = memo(function DialogueStage({
  session,
  assistantName,
  activeSceneLabel,
  actorNames,
  lastTurnResult,
  pending,
}: DialogueStageProps) {
  const highlightedTurnIds = new Set(lastTurnResult?.turns.map((turn) => turn.turnId) ?? []);
  const castNames = (session?.runtimeState.currentCast ?? []).map((id) => actorNames[id] || id);
  const visibleTurns = (session?.recentTurns ?? []).filter((turn) => turn.actorType !== 'director');

  return (
    <section className="dialogue-stage">
      <div className="stage-hero">
        <div className="stage-headline">
          <p className="eyebrow">{'持续对话'}</p>
          <h2>{activeSceneLabel}</h2>
          <p className="stage-copy">
            {session
              ? `${assistantName || '助手'} 会在这里用台词和低频旁白回应你，场景与记忆只作为轻上下文存在。`
              : '还没有持续对话。先选定一个助手并发出第一句消息，这里就会变成正式的会话窗口。'}
          </p>
        </div>
        <div className="stage-side">
          <div className="stage-badge-group">
            <span>{session?.runtimeState.timeBlock || '待连接'}</span>
            <span>{`第 ${session?.runtimeState.dayIndex || 1} 天`}</span>
            {pending ? <span className="pending-dot">{'回应中'}</span> : null}
          </div>
          <div className="stage-cast-strip">
            {castNames.length ? castNames.map((name) => <span key={name}>{name}</span>) : <span>{'等待助手接入'}</span>}
          </div>
        </div>
      </div>

      <div className="dialogue-scroll">
        {visibleTurns.length ? (
          visibleTurns.map((turn) => {
            const highlighted = highlightedTurnIds.has(turn.turnId);
            const presentationType = turn.presentationType || 'speech';
            const actorName = resolveActorName(turn.actorType, turn.actorId, actorNames);
            return (
              <article
                key={turn.turnId}
                className={`dialogue-line dialogue-line--${turn.actorType} dialogue-line--${presentationType}${highlighted ? ' is-highlighted' : ''}`}
              >
                <div className="dialogue-meta">
                  <span>{presentationType === 'narration' ? `${actorName} · 低频旁白` : actorName}</span>
                  <small>{turn.sceneId || 'scene'}</small>
                </div>
                <p>{turn.text}</p>
              </article>
            );
          })
        ) : (
          <div className="dialogue-empty">
            <div className="dialogue-empty-plate">
              <p className="eyebrow">{'对话空白'}</p>
              <h3>{session ? '助手的回应还没有出现' : '先开启一段对话'}</h3>
              <p>
                {session
                  ? '输入一句话，让回应、低频旁白和记忆从这里继续积累。'
                  : '选一个助手，再开启一段对话片段，中间区域就会真正转成持续聊天窗口。'}
              </p>
            </div>
          </div>
        )}
      </div>
    </section>
  );
});
