import { memo, useState } from 'react';
import { motion } from 'motion/react';
import type { GameSession, GameTurnResult, LongMemoryItem, LongMemoryState, MemoryProfile, SceneSnapshot } from '../lib/types';

interface SceneInspectorProps {
  scene: SceneSnapshot | null;
  session: GameSession | null;
  longMemory: LongMemoryState | null;
  actorNames: Record<string, string>;
  assistantName: string;
  assistantRole: string;
  assistantTags: string[];
  backgroundTitle: string;
  primaryCharacterId: string;
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
  if (!profile) return '还没有累积到可读的关系记忆。';
  return profile.playerImageSummary || profile.relationshipSummary || '暂无简要';
}

function memoryIdentity(entry: LongMemoryItem) {
  return `${entry.memoryType}::${entry.locationId || ''}::${entry.retrievalSummary.replace(/\s+/g, '')}`;
}

function relatedLongMemoryItems(longMemory: LongMemoryState | null, characterId: string) {
  const items = (longMemory?.recentItems ?? []).filter((entry) => entry.characterIds.includes(characterId) || entry.responderId === characterId);
  const deduped: LongMemoryItem[] = [];
  const seen = new Set<string>();
  for (const item of items) {
    const key = memoryIdentity(item);
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(item);
  }
  return deduped;
}

function includesAny(text: string, keywords: string[]) {
  return keywords.some((keyword) => text.includes(keyword));
}

function classifyStageTone(stage: string): StageTone {
  const normalized = stage.toLowerCase();
  if (includesAny(normalized, ['danger', 'volatile', 'tense', 'obsession', '危险', '失控', '对峙', '紧张', '拉扯'])) return 'volatile';
  if (includesAny(normalized, ['close', 'warm', 'romance', '靠近', '暧昧', '亲密', '升温', '心动'])) return 'warm';
  if (includesAny(normalized, ['guarded', 'distant', 'stranger', '疏离', '戒备', '路人', '警惕'])) return 'guarded';
  return 'neutral';
}

export const SceneInspector = memo(function SceneInspector({
  scene,
  session,
  longMemory,
  actorNames,
  assistantName,
  assistantRole,
  assistantTags,
  backgroundTitle,
  primaryCharacterId,
  lastTurnResult,
}: SceneInspectorProps) {
  const [expandedCards, setExpandedCards] = useState<Record<string, boolean>>({});
  const relationshipEntries = Object.entries(session?.runtimeState.relationshipStates ?? {}).sort(([leftId], [rightId]) => {
    if (leftId === primaryCharacterId) return -1;
    if (rightId === primaryCharacterId) return 1;
    return leftId.localeCompare(rightId, 'zh-CN');
  });
  const latestDiff = lastTurnResult?.stateDiff;
  const memoryTimeline = [...(session?.memoryEntries ?? [])].slice(-6).reverse();
  const longMemoryTimeline = [...(longMemory?.recentItems ?? [])].slice(0, 6);
  const primarySessionProfile = primaryCharacterId ? session?.memoryProfiles[primaryCharacterId] : undefined;
  const primaryLongProfile = primaryCharacterId ? longMemory?.profiles[primaryCharacterId] : undefined;

  return (
    <aside className="scene-inspector" data-testid="scene-inspector">
      <motion.section className="inspector-block inspector-block--hero" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.28 }}>
        <p className="eyebrow">{'助手资料'}</p>
        <h3>{assistantName || '未选择助手'}</h3>
        <p className="scene-copy">
          {assistantName
            ? `${assistantRole || '助手人格'}，绑定背景「${backgroundTitle || '未指定背景'}」。${primaryLongProfile?.displaySummary || profileSummary(primarySessionProfile)}`
            : '选中一个助手后，这里会显示它的人格摘要、长期印象和当前背景。'}
        </p>
        <div className="tag-cluster">
          {(assistantTags.length ? assistantTags : scene?.moodHints ?? []).slice(0, 4).map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </div>
      </motion.section>

      <section className="inspector-block">
        <p className="eyebrow">{'背景上下文'}</p>
        <div className="shift-line">
          <span>{'背景'}</span>
          <strong>{backgroundTitle || '未绑定背景'}</strong>
        </div>
        <div className="shift-line">
          <span>{'当前地点'}</span>
          <strong>{scene?.locationName || '还未进入上下文'}</strong>
        </div>
        <p className="scene-copy">{scene?.locationDescription || '开启一段对话后，这里会显示当前背景与地点描述。'}</p>
      </section>

      <section className="inspector-block">
        <p className="eyebrow">{'最近位移'}</p>
        {latestDiff ? (
          <>
            <div className="shift-line"><span>{'上下文'}</span><strong>{latestDiff.previousSceneId} {'→'} {latestDiff.newSceneId}</strong></div>
            <div className="shift-line"><span>{'回合'}</span><strong>{latestDiff.recentTurnCountBefore} {'→'} {latestDiff.recentTurnCountAfter}</strong></div>
            <div className="shift-list">
              {latestDiff.activeEventsAdded.map((item) => <span key={item}>{item}</span>)}
              {latestDiff.newMemorySummaries.map((item) => <span key={item}>{item}</span>)}
            </div>
          </>
        ) : (
          <p className="scene-copy">{'一旦这轮互动真正发生推进，这里会显示上下文位移和新增记忆。'}</p>
        )}
      </section>

      <section className="inspector-block">
        <p className="eyebrow">{'工作记忆'}</p>
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
          <p className="scene-copy">{'还没有落盘的工作记忆。开始几轮互动后，这里会形成最近对话摘要。'}</p>
        )}
      </section>

      <section className="inspector-block" data-testid="long-memory-block">
        <p className="eyebrow">{'长期记忆'}</p>
        {longMemoryTimeline.length ? (
          <div className="memory-timeline">
            {longMemoryTimeline.map((entry) => (
              <article className="memory-entry" key={entry.id}>
                <div className="memory-entry-meta">
                  <span>{entry.memoryType}</span>
                  <small>{entry.createdAt.replace('T', ' ').slice(0, 16)}</small>
                </div>
                <p className="memory-entry-copy">{entry.displaySummary}</p>
              </article>
            ))}
          </div>
        ) : (
          <p className="scene-copy">{'还没有沉淀到跨片段的长期记忆。'}</p>
        )}
      </section>

      <section className="inspector-block inspector-block--stretch">
        <p className="eyebrow">{'参与者印象'}</p>
        <div className="relation-list">
          {relationshipEntries.length ? (
            relationshipEntries.map(([characterId, relation]) => {
              const stageTone = classifyStageTone(relation.stage);
              const longProfile = longMemory?.profiles[characterId];
              const relatedItems = relatedLongMemoryItems(longMemory, characterId).slice(0, 2);
              const expanded = Boolean(expandedCards[characterId]);
              const isPrimary = primaryCharacterId === characterId;
              return (
                <div className="relation-sheet" key={characterId}>
                  <div className="relation-header">
                    <strong>{`${actorNames[characterId] || characterId}${isPrimary ? ' · 当前助手' : ''}`}</strong>
                    <span className={`relationship-stage-badge relationship-stage-badge--${stageTone}`}>{relation.stage}</span>
                  </div>
                  {relationMeter('信任', relation.trust, 'trust')}
                  {relationMeter('好感', relation.affection, 'affection')}
                  {relationMeter('张力', relation.tension, 'tension')}
                  {relationMeter('熟悉', relation.familiarity, 'familiarity')}
                  <p className="profile-copy">{profileSummary(session?.memoryProfiles[characterId])}</p>
                  <div className="relation-memory-panel">
                    <div className="relation-memory-header">
                      <span className="eyebrow">{isPrimary ? '助手长期印象' : '相关长期印象'}</span>
                      {longProfile ? (
                        <button
                          className="relation-memory-toggle"
                          type="button"
                          onClick={() => setExpandedCards((current) => ({ ...current, [characterId]: !current[characterId] }))}
                        >
                          {expanded ? '收起' : '展开'}
                        </button>
                      ) : null}
                    </div>
                    {longProfile ? (
                      <>
                        <p className="profile-copy profile-copy--teaser">{longProfile.displayTeaser || '暂无长期印象'}</p>
                        {expanded ? (
                          <div className="relation-memory-expanded">
                            {longProfile.displaySummary && longProfile.displaySummary !== longProfile.displayTeaser ? (
                              <p className="profile-copy">{longProfile.displaySummary}</p>
                            ) : null}
                            {relatedItems.length ? (
                              <div className="relation-memory-list">
                                {relatedItems.map((entry) => (
                                  <p className="relation-memory-item" key={entry.id}>
                                    {entry.displaySummary}
                                  </p>
                                ))}
                              </div>
                            ) : (
                              <p className="scene-copy">{'还没有可展开的长期记忆片段。'}</p>
                            )}
                          </div>
                        ) : null}
                      </>
                    ) : (
                      <p className="scene-copy">{'还没有沉淀成跨片段的长期印象。'}</p>
                    )}
                  </div>
                </div>
              );
            })
          ) : (
            <div className="rail-empty">{'还没有激活中的参与者状态，进入对话后这里会出现可读的印象面板。'}</div>
          )}
        </div>
      </section>
    </aside>
  );
});
