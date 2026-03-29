import { memo } from 'react';
import { motion } from 'motion/react';
import type { GameTurnResult } from '../lib/types';

interface TurnSpotlightProps {
  result: GameTurnResult | null;
  hasSession: boolean;
}

export const TurnSpotlight = memo(function TurnSpotlight({ result, hasSession }: TurnSpotlightProps) {
  if (result) {
    const primarySpeech = result.primaryDialogue || result.primaryReply;
    return (
      <section className="turn-spotlight">
        <div className="spotlight-background" />
        <motion.div className="spotlight-card" initial={{ opacity: 0.96, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.16 }}>
          <div className="spotlight-header">
            <div className="spotlight-heading">
              <p className="eyebrow">{'当前回应聚焦'}</p>
              <h3>{result.responderName}</h3>
            </div>
            <div className="spotlight-pills">
              {result.eventSeed ? <span>{result.eventSeed}</span> : null}
              <span>{result.sceneGoal}</span>
            </div>
          </div>

          {primarySpeech ? <p className="spotlight-quote">{primarySpeech}</p> : null}

          <div className="spotlight-support">
            {result.primaryNarration ? (
              <div className="spotlight-support-block">
                <span className="preview-label">{'低频旁白'}</span>
                <p>{result.primaryNarration}</p>
              </div>
            ) : null}
            <div className="spotlight-support-block">
              <span className="preview-label">{'上下文'}</span>
              <p>{result.stateDiff.newSceneId}</p>
            </div>
          </div>
        </motion.div>
      </section>
    );
  }

  return (
    <section className="turn-spotlight">
      <div className="spotlight-background" />
      <div className="spotlight-card spotlight-card--empty">
        <p className="eyebrow">{'当前回应聚焦'}</p>
        <h3>{hasSession ? '助手还在积累上下文' : '先开启一段对话'}</h3>
        <p>
          {hasSession
            ? '这里会在 recent turns 被推进后，抓出这一轮最值得被看见的回应与低频旁白。'
            : '先开启与助手的第一段对话，中间会话窗口和这里的聚焦卡片才会一起亮起来。'}
        </p>
      </div>
    </section>
  );
});
