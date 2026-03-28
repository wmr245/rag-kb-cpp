import { memo } from 'react';
import type { GameSession, GameTurnResult } from '../lib/types';

interface DialogueStageProps {
  session: GameSession | null;
  activeSceneLabel: string;
  actorNames: Record<string, string>;
  lastTurnResult: GameTurnResult | null;
  pending: boolean;
}

function resolveActorName(actorType: string, actorId: string, actorNames: Record<string, string>) {
  if (actorType === 'player') return '\u73a9\u5bb6';
  if (actorType === 'director') return '\u5bfc\u6f14';
  return actorNames[actorId] || actorId;
}

export const DialogueStage = memo(function DialogueStage({ session, activeSceneLabel, actorNames, lastTurnResult, pending }: DialogueStageProps) {
  const highlightedTurnIds = new Set(lastTurnResult?.turns.map((turn) => turn.turnId) ?? []);
  const castNames = (session?.runtimeState.currentCast ?? []).map((id) => actorNames[id] || id);

  return (
    <section className="dialogue-stage">
      <div className="stage-hero">
        <div className="stage-headline">
          <p className="eyebrow">{'\u5f53\u524d\u821e\u53f0'}</p>
          <h2>{activeSceneLabel}</h2>
          <p className="stage-copy">
            {session
              ? '\u4e0b\u9762\u662f recent turns \u7684\u5267\u60c5\u6d41\uff0c\u53ef\u4ee5\u76f4\u63a5\u89c2\u5bdf scene \u600e\u4e48\u88ab\u5bfc\u6f14\u63a8\u8fdb\u3002'
              : '\u8fd8\u6ca1\u6709\u5267\u60c5\u6d41\u3002\u5148\u5f00\u542f\u4e00\u573a\u4f1a\u8bdd\uff0c\u8fd9\u5757\u533a\u57df\u624d\u4f1a\u53d8\u6210\u6b63\u5f0f\u7684\u5bf9\u8bdd\u821e\u53f0\u3002'}
          </p>
        </div>
        <div className="stage-side">
          <div className="stage-badge-group">
            <span>{session?.runtimeState.timeBlock || '\u5f00\u573a'}</span>
            <span>{`\u7b2c ${session?.runtimeState.dayIndex || 1} \u5929`}</span>
            {pending ? <span className="pending-dot">{'\u63a8\u8fdb\u4e2d'}</span> : null}
          </div>
          <div className="stage-cast-strip">
            {castNames.length ? castNames.map((name) => <span key={name}>{name}</span>) : <span>{'\u7b49\u5f85\u89d2\u8272\u5165\u573a'}</span>}
          </div>
        </div>
      </div>

      <div className="dialogue-scroll">
        {session?.recentTurns.length ? (
          session.recentTurns.map((turn) => {
            const highlighted = highlightedTurnIds.has(turn.turnId);
            return (
              <article
                key={turn.turnId}
                className={`dialogue-line dialogue-line--${turn.actorType}${highlighted ? ' is-highlighted' : ''}`}
              >
                <div className="dialogue-meta">
                  <span>{resolveActorName(turn.actorType, turn.actorId, actorNames)}</span>
                  <small>{turn.sceneId || 'scene'}</small>
                </div>
                <p>{turn.text}</p>
              </article>
            );
          })
        ) : (
          <div className="dialogue-empty">
            <div className="dialogue-empty-plate">
              <p className="eyebrow">{'\u821e\u53f0\u7a7a\u767d'}</p>
              <h3>{session ? '\u8fd9\u4e00\u573a\u7684\u53f0\u8bcd\u8fd8\u6ca1\u51fa\u73b0' : '\u5148\u5f00\u542f\u4e00\u4e2a\u4f1a\u8bdd'}</h3>
              <p>
                {session
                  ? '\u8f93\u5165\u4e00\u53e5\u8bdd\uff0c\u8ba9\u5bfc\u6f14\u548c\u89d2\u8272\u4ece\u8fd9\u91cc\u7ee7\u7eed\u63a8\u52a8 cue \u4e0e\u56de\u5e94\u3002'
                  : '\u9009\u4e00\u4e2a worldbook\uff0c\u518d\u521b\u5efa session\uff0c\u4e2d\u95f4\u821e\u53f0\u5c31\u4f1a\u771f\u6b63\u4eae\u8d77\u6765\u3002'}
              </p>
            </div>
          </div>
        )}
      </div>
    </section>
  );
});
