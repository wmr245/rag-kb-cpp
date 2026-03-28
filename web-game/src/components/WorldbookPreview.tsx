import { memo } from 'react';
import { motion } from 'motion/react';
import type { CharacterCardSummary, Worldbook } from '../lib/types';

interface WorldbookPreviewProps {
  worldbook: Worldbook | null;
  characters: CharacterCardSummary[];
  selected: boolean;
  onOpenSeedImport: () => void;
}

export const WorldbookPreview = memo(function WorldbookPreview({ worldbook, characters, selected, onOpenSeedImport }: WorldbookPreviewProps) {
  if (!worldbook) {
    return (
      <section className="worldbook-preview worldbook-preview--empty">
        <p className="eyebrow">{'\u4e16\u754c\u89c2\u9884\u89c8'}</p>
        <h3>{'\u5148\u9009\u4e00\u4e2a\u4e16\u754c'}</h3>
        <p>{'\u5de6\u4fa7\u9009\u4e2d worldbook \u540e\uff0c\u8fd9\u91cc\u4f1a\u5c55\u793a\u4e16\u754c\u89c4\u5219\u3001\u573a\u666f\u6570\u91cf\u548c\u89d2\u8272\u6c14\u8d28\u3002'}</p>
        <button className="ghost-button preview-cta" onClick={onOpenSeedImport} type="button">
          {'先导入一套 worldbook 与角色卡'}
        </button>
      </section>
    );
  }

  const moodLine = [...worldbook.genre, ...worldbook.tone].slice(0, 4).join(' \u00b7 ');
  const seedLine = worldbook.eventSeeds.slice(0, 3);

  return (
    <motion.section
      className={`worldbook-preview${selected ? ' is-selected' : ''}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28 }}
    >
      <div className="preview-header">
        <div className="preview-heading">
          <p className="eyebrow">{'\u4e16\u754c\u89c2\u9884\u89c8'}</p>
          <h3>{worldbook.title}</h3>
        </div>
        <span className="preview-era">{worldbook.era}</span>
      </div>

      <p className="preview-copy">{moodLine || '\u672a\u6807\u6ce8\u98ce\u683c'}{'\uff0c\u5171\u6709 '}{worldbook.locations.length}{' \u4e2a\u573a\u666f\uff0c'}{worldbook.factions.length}{' \u4e2a\u9635\u8425\uff0c'}{characters.length}{' \u4e2a\u89d2\u8272\u5165\u573a\u3002'}</p>

      <div className="preview-grid">
        <div className="preview-column">
          <span className="preview-label">{'\u4e16\u754c\u89c4\u5219'}</span>
          <ul>
            {worldbook.worldRules.slice(0, 3).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div className="preview-column">
          <span className="preview-label">{'\u4e8b\u4ef6\u79cd\u5b50'}</span>
          <ul>
            {seedLine.length ? seedLine.map((item) => <li key={item}>{item}</li>) : <li>{'\u6682\u65e0\u79cd\u5b50'}</li>}
          </ul>
        </div>
      </div>

      <div className="preview-footer">
        <div className="preview-avatars">
          {characters.slice(0, 4).map((character) => (
            <span key={character.id}>{character.name}</span>
          ))}
        </div>
        <div className="preview-meta">{worldbook.locale || '\u672a\u8bbe\u7f6e\u5730\u57df'} {'\u00b7'} v{worldbook.version}</div>
      </div>
    </motion.section>
  );
});
