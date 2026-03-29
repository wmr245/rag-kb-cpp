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
        <p className="eyebrow">{'背景设定预览'}</p>
        <h3>{'先选一个背景'}</h3>
        <p>{'左侧选中助手后，这里会展示它绑定的背景规则、场景数量和相关角色。'}</p>
        <button className="ghost-button preview-cta" onClick={onOpenSeedImport} type="button">
          {'先导入一套背景设定与人格卡'}
        </button>
      </section>
    );
  }

  const moodLine = [...worldbook.genre, ...worldbook.tone].slice(0, 4).join(' · ');
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
          <p className="eyebrow">{'背景设定预览'}</p>
          <h3>{worldbook.title}</h3>
        </div>
        <span className="preview-era">{worldbook.era}</span>
      </div>

      <p className="preview-copy">{moodLine || '未标注风格'}，共有 {worldbook.locations.length} 个场景，{worldbook.factions.length} 个阵营，{characters.length} 个相关角色。</p>

      <div className="preview-grid">
        <div className="preview-column">
          <span className="preview-label">{'背景规则'}</span>
          <ul>
            {worldbook.worldRules.slice(0, 3).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div className="preview-column">
          <span className="preview-label">{'事件线索'}</span>
          <ul>
            {seedLine.length ? seedLine.map((item) => <li key={item}>{item}</li>) : <li>{'暂无线索'}</li>}
          </ul>
        </div>
      </div>

      <div className="preview-footer">
        <div className="preview-avatars">
          {characters.slice(0, 4).map((character) => (
            <span key={character.id}>{character.name}</span>
          ))}
        </div>
        <div className="preview-meta">{worldbook.locale || '未设置地域'} {'·'} v{worldbook.version}</div>
      </div>
    </motion.section>
  );
});
