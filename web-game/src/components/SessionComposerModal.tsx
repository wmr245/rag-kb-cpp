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
                <p className="eyebrow">{'\u5f00\u573a\u7f16\u6392'}</p>
                <h3>{worldbook ? `\u4e3a\u300c${worldbook.title}\u300d\u5b89\u6392\u7b2c\u4e00\u665a` : '\u5148\u9009\u62e9\u4e00\u4e2a worldbook'}</h3>
              </div>
              <button className="ghost-button" onClick={onClose} type="button">{'\u5173\u95ed'}</button>
            </div>

            {worldbook ? (
              <>
                <div className="session-composer-grid">
                  <section className="session-composer-block">
                    <span className="preview-label">{'\u5f00\u573a\u5730\u70b9'}</span>
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
                            <span>{location.description || location.sceneHints[0] || '\u7b49\u5f85\u573a\u666f\u8bf4\u660e'}</span>
                          </button>
                        );
                      })}
                    </div>
                  </section>

                  <section className="session-composer-block">
                    <span className="preview-label">{'\u89d2\u8272\u9635\u5bb9'}</span>
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
                              <p>{character.role || '\u89d2\u8272\u672a\u6807\u6ce8\u5b9a\u4f4d'}</p>
                            </div>
                            <span>{character.personaTags.slice(0, 2).join(' \u00b7 ') || '\u5f85\u8865\u6807\u7b7e'}</span>
                          </button>
                        );
                      })}
                    </div>
                  </section>
                </div>

                <div className="session-composer-footer">
                  <div>
                    <span className="preview-label">{'\u5f00\u573a\u7b80\u62a5'}</span>
                    <p>
                      {selectedCharacterIds.length} {'\u4f4d\u89d2\u8272\u5c06\u5728 '}
                      {worldbook.locations.find((item) => item.id === selectedLocationId)?.name || '\u672a\u9009\u62e9\u5730\u70b9'}
                      {' \u51fa\u573a\uff0c\u7cfb\u7edf\u4f1a\u4ee5\u8be5\u5730\u70b9\u4f5c\u4e3a\u7b2c\u4e00\u5e55\u7684 scene \u8d77\u70b9\u3002'}
                      {existingSessionCount > 0
                        ? ` \u8fd9\u4f1a\u4f5c\u4e3a\u8be5\u4e16\u754c\u7684\u7b2c ${existingSessionCount + 1} \u6761\u72ec\u7acb\u8bb0\u5fc6\u7ebf\u3002`
                        : ' \u8fd9\u4f1a\u6210\u4e3a\u8fd9\u4e2a\u4e16\u754c\u7684\u7b2c\u4e00\u6761\u72ec\u7acb\u8bb0\u5fc6\u7ebf\u3002'}
                    </p>
                  </div>
                  <button
                    className="primary-button"
                    onClick={onConfirm}
                    type="button"
                    disabled={creating || !selectedLocationId || selectedCharacterIds.length === 0}
                  >
                    {creating ? '\u6b63\u5728\u70b9\u4eae\u7b2c\u4e00\u5e55\u2026' : '\u786e\u8ba4\u5e76\u5f00\u59cb\u8fd9\u573a\u591c\u665a'}
                  </button>
                </div>
              </>
            ) : (
              <div className="rail-empty">{'\u8fd8\u6ca1\u6709\u53ef\u7528 worldbook\uff0c\u5148\u5728\u5de6\u4fa7\u9009\u62e9\u4e00\u4e2a\u4e16\u754c\u89c2\u3002'}</div>
            )}
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
