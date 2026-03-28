import { memo } from 'react';
import { motion } from 'motion/react';
import type { GameSession, GameTurnResult, MemoryProfile, SceneSnapshot } from '../lib/types';

interface SceneInspectorProps {
  scene: SceneSnapshot | null;
  session: GameSession | null;
  actorNames: Record<string, string>;
  lastTurnResult: GameTurnResult | null;
}

type MeterTone = 'trust' | 'affection' | 'tension' | 'familiarity';
type StageTone = 'warm' | 'volatile' | 'guarded' | 'neutral';

function relationMeter(label: string, value: number, tone: MeterTone) {
  return (
    <div className={`meter-row meter-row--${tone}`} key={label}>
      <span>{label}</span>
      <div className={`meter-track meter-track--${tone}`}>
        <div className={`meter-bar meter-bar--${tone}`} style={{ width: `${Math.max(6, Math.min(100, value))}%` }} />
      </div>
      <strong className="meter-value">{value}</strong>
    </div>
  );
}

function profileSummary(profile?: MemoryProfile) {
  if (!profile) return '\u8fd8\u6ca1\u6709\u7d2f\u79ef\u5230\u53ef\u8bfb\u7684\u5173\u7cfb\u8bb0\u5fc6\u3002';
  return profile.relationshipSummary || profile.playerImageSummary || '\u6682\u65e0\u7b80\u8981';
}

function includesAny(text: string, keywords: string[]) {
  return keywords.some((keyword) => text.includes(keyword));
}

function classifyStageTone(stage: string): StageTone {
  const normalized = stage.toLowerCase();
  if (includesAny(normalized, ['danger', 'volatile', 'tense', 'obsession', '\u5371\u9669', '\u5931\u63a7', '\u5bf9\u5cd9', '\u7d27\u5f20', '\u62c9\u626f'])) return 'volatile';
  if (includesAny(normalized, ['close', 'warm', 'romance', '\u9760\u8fd1', '\u66a7\u6627', '\u4eb2\u5bc6', '\u5347\u6e29', '\u5fc3\u52a8'])) return 'warm';
  if (includesAny(normalized, ['guarded', 'distant', 'stranger', '\u758f\u79bb', '\u622a\u6b62', '\u8def\u4eba', '\u8b66\u60d5'])) return 'guarded';
  return 'neutral';
}

export const SceneInspector = memo(function SceneInspector({ scene, session, actorNames, lastTurnResult }: SceneInspectorProps) {
  const relationshipEntries = Object.entries(session?.runtimeState.relationshipStates ?? {});
  const latestDiff = lastTurnResult?.stateDiff;
  const memoryTimeline = [...(session?.memoryEntries ?? [])].slice(-6).reverse();

  return (
    <aside className="scene-inspector">
      <motion.section className="inspector-block inspector-block--hero" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.28 }}>
        <p className="eyebrow">{'\u573a\u666f\u8d26\u672c'}</p>
        <h3>{scene?.locationName || '\u672a\u8fdb\u5165\u573a\u666f'}</h3>
        <p className="scene-copy">{scene?.locationDescription || '\u9009\u62e9\u6216\u521b\u5efa\u4e00\u4e2a\u4f1a\u8bdd\u540e\uff0c\u8fd9\u91cc\u4f1a\u663e\u793a\u5f53\u524d\u573a\u666f\u63cf\u8ff0\u3002'}</p>
        <div className="tag-cluster">
          {(scene?.moodHints.length ? scene.moodHints : scene?.activeEvents ?? []).slice(0, 4).map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </div>
      </motion.section>

      <section className="inspector-block">
        <p className="eyebrow">{'\u672c\u8f6e\u4f4d\u79fb'}</p>
        {latestDiff ? (
          <>
            <div className="shift-line"><span>{'\u573a\u666f'}</span><strong>{latestDiff.previousSceneId} {'\u2192'} {latestDiff.newSceneId}</strong></div>
            <div className="shift-line"><span>{'\u56de\u5408'}</span><strong>{latestDiff.recentTurnCountBefore} {'\u2192'} {latestDiff.recentTurnCountAfter}</strong></div>
            <div className="shift-list">
              {latestDiff.activeEventsAdded.map((item) => <span key={item}>{item}</span>)}
              {latestDiff.newMemorySummaries.map((item) => <span key={item}>{item}</span>)}
            </div>
          </>
        ) : (
          <p className="scene-copy">{'\u4e00\u65e6\u672c\u8f6e\u771f\u6b63\u53d1\u751f\u63a8\u8fdb\uff0c\u8fd9\u91cc\u4f1a\u7528\u53ef\u626b\u8bfb\u7684\u65b9\u5f0f\u663e\u793a scene shift \u548c\u65b0\u589e\u8bb0\u5fc6\u3002'}</p>
        )}
      </section>

      <section className="inspector-block">
        <p className="eyebrow">{'\u8bb0\u5fc6\u65f6\u95f4\u7ebf'}</p>
        {memoryTimeline.length ? (
          <div className="memory-timeline">
            {memoryTimeline.map((entry) => (
              <article className="memory-entry" key={entry.id}>
                <div className="memory-entry-meta">
                  <span>{entry.type}</span>
                  <small>{entry.createdAt.replace('T', ' ').slice(0, 16)}</small>
                </div>
                <p className="memory-entry-copy">{entry.summary}</p>
              </article>
            ))}
          </div>
        ) : (
          <p className="scene-copy">{'\u8fd8\u6ca1\u6709\u843d\u76d8\u7684\u8bb0\u5fc6\u7247\u6bb5\u3002\u5f00\u59cb\u51e0\u8f6e\u540e\uff0c\u8fd9\u91cc\u4f1a\u53d8\u6210\u8fd9\u6761\u8bb0\u5fc6\u7ebf\u7684\u7f29\u5f71\u3002'}</p>
        )}
      </section>

      <section className="inspector-block inspector-block--stretch">
        <p className="eyebrow">{'\u5173\u7cfb\u7f51\u683c'}</p>
        <div className="relation-list">
          {relationshipEntries.length ? (
            relationshipEntries.map(([characterId, relation]) => {
              const stageTone = classifyStageTone(relation.stage);
              return (
                <div className="relation-sheet" key={characterId}>
                  <div className="relation-header">
                    <strong>{actorNames[characterId] || characterId}</strong>
                    <span className={`relationship-stage-badge relationship-stage-badge--${stageTone}`}>{relation.stage}</span>
                  </div>
                  {relationMeter('\u4fe1\u4efb', relation.trust, 'trust')}
                  {relationMeter('\u597d\u611f', relation.affection, 'affection')}
                  {relationMeter('\u5f20\u529b', relation.tension, 'tension')}
                  {relationMeter('\u719f\u6089', relation.familiarity, 'familiarity')}
                  <p className="profile-copy">{profileSummary(session?.memoryProfiles[characterId])}</p>
                </div>
              );
            })
          ) : (
            <div className="rail-empty">{'\u8fd8\u6ca1\u6709\u6fc0\u6d3b\u4e2d\u7684\u5173\u7cfb\u72b6\u6001\uff0c\u8fdb\u5165\u4f1a\u8bdd\u540e\u8fd9\u91cc\u4f1a\u53d8\u6210\u771f\u6b63\u7684\u5173\u7cfb\u9762\u677f\u3002'}</div>
          )}
        </div>
      </section>
    </aside>
  );
});
