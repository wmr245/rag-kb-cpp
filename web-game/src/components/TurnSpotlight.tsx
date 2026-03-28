import { motion } from 'motion/react';
import type { GameTurnDebug, GameTurnResult } from '../lib/types';

interface TurnSpotlightProps {
  result: GameTurnResult | null;
  debug: GameTurnDebug | null;
  hasSession: boolean;
}

export function TurnSpotlight({ result, debug, hasSession }: TurnSpotlightProps) {
  if (result) {
    return (
      <section className="turn-spotlight">
        <div className="spotlight-background" />
        <motion.div className="spotlight-card" initial={{ opacity: 0.96 }} animate={{ opacity: 1 }} transition={{ duration: 0.14 }}>
          <div className="spotlight-header">
            <div>
              <p className="eyebrow">{'\u672c\u8f6e\u805a\u5149'}</p>
              <h3>{result.responderName}</h3>
            </div>
            <div className="spotlight-pills">
              {result.eventSeed ? <span>{result.eventSeed}</span> : null}
              <span>{result.sceneGoal}</span>
            </div>
          </div>

          <p className="spotlight-quote">{result.primaryReply}</p>

          <div className="spotlight-support">
            <div>
              <span className="preview-label">{'\u5bfc\u6f14\u63d0\u793a'}</span>
              <p>{debug?.directorNote || '\u8fd8\u6ca1\u6709\u989d\u5916\u63d0\u793a\u3002'}</p>
            </div>
            <div>
              <span className="preview-label">{'\u573a\u666f'}</span>
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
        <p className="eyebrow">{'\u672c\u8f6e\u805a\u5149'}</p>
        <h3>{hasSession ? '\u8fd9\u4e00\u591c\u8fd8\u5728\u84c4\u529b' : '\u5148\u5f00\u542f\u4e00\u4e2a\u5267\u672c'}</h3>
        <p>
          {hasSession
            ? '\u8fd9\u4e00\u5757\u4f1a\u5728 recent turns \u88ab\u63a8\u8fdb\u540e\uff0c\u6293\u51fa\u6700\u503c\u5f97\u88ab\u770b\u89c1\u7684\u53f0\u8bcd\u548c\u5bfc\u6f14\u7ebf\u7d22\u3002'
            : '\u5148\u5f00\u542f session\uff0c\u4e2d\u95f4\u821e\u53f0\u624d\u4f1a\u771f\u6b63\u51fa\u73b0\u3002'}
        </p>
      </div>
    </section>
  );
}
