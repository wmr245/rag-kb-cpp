import { AnimatePresence, motion } from 'motion/react';
import type { CharacterCardSummary, Worldbook } from '../lib/types';

interface SessionComposerModalProps {
  open: boolean;
  worldbook: Worldbook | null;
  characters: CharacterCardSummary[];
  existingSessionCount: number;
  selectedCharacterIds: string[];
  selectedLocationId: string;
  creating: boolean;
  onClose: () => void;
  onToggleCharacter: (characterId: string) => void;
  onSelectLocation: (locationId: string) => void;
  onConfirm: () => void;
}

export function SessionComposerModal({
  open,
  worldbook,
  characters,
  existingSessionCount,
  selectedCharacterIds,
  selectedLocationId,
  creating,
  onClose,
  onToggleCharacter,
  onSelectLocation,
  onConfirm,
}: SessionComposerModalProps) {
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="session-composer-overlay"
          data-testid="session-composer-modal"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.22 }}
        >
          <motion.div
            className="session-composer-modal"
            initial={{ opacity: 0, y: 28, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 18, scale: 0.985 }}
            transition={{ duration: 0.28 }}
          >
            <div className="session-composer-header">
              <div>
                <p className="eyebrow">{'对话片段编排'}</p>
                <h3>{worldbook ? `为「${worldbook.title}」准备一段新的助手对话` : '先选择一个背景设定'}</h3>
              </div>
              <button className="ghost-button" onClick={onClose} type="button">{'关闭'}</button>
            </div>

            {worldbook ? (
              <>
                <div className="session-composer-grid">
                  <section className="session-composer-block">
                    <span className="preview-label">{'起始上下文'}</span>
                    <div className="location-option-list">
                      {worldbook.locations.map((location) => {
                        const active = location.id === selectedLocationId;
                        return (
                          <button
                            key={location.id}
                            className={`location-option${active ? ' is-active' : ''}`}
                            onClick={() => onSelectLocation(location.id)}
                            type="button"
                          >
                            <strong>{location.name}</strong>
                            <span>{location.description || location.sceneHints[0] || '等待场景说明'}</span>
                          </button>
                        );
                      })}
                    </div>
                  </section>

                  <section className="session-composer-block">
                    <span className="preview-label">{'参与角色'}</span>
                    <div className="cast-option-list">
                      {characters.map((character) => {
                        const active = selectedCharacterIds.includes(character.id);
                        return (
                          <button
                            key={character.id}
                            className={`cast-option${active ? ' is-active' : ''}`}
                            onClick={() => onToggleCharacter(character.id)}
                            type="button"
                          >
                            <div>
                              <strong>{character.name}</strong>
                              <p>{character.role || '角色未标注定位'}</p>
                            </div>
                            <span>{character.personaTags.slice(0, 2).join(' · ') || '待补标签'}</span>
                          </button>
                        );
                      })}
                    </div>
                  </section>
                </div>

                <div className="session-composer-footer">
                  <div>
                    <span className="preview-label">{'片段简报'}</span>
                    <p>
                      {selectedCharacterIds.length} 位角色将以
                      {' '}
                      {worldbook.locations.find((item) => item.id === selectedLocationId)?.name || '未选择地点'}
                      {' '}
                      作为起始上下文。
                      {existingSessionCount > 0
                        ? ` 这会成为该助手的第 ${existingSessionCount + 1} 段对话快照。`
                        : ' 这会成为该助手的第一段对话快照。'}
                    </p>
                  </div>
                  <button
                    className="primary-button"
                    data-testid="confirm-session-composer"
                    onClick={onConfirm}
                    type="button"
                    disabled={creating || !selectedLocationId || selectedCharacterIds.length === 0}
                  >
                    {creating ? '正在准备对话片段…' : '确认并开始对话'}
                  </button>
                </div>
              </>
            ) : (
              <div className="rail-empty">{'还没有可用背景设定，先在左侧选择或导入一套 worldbook。'}</div>
            )}
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
