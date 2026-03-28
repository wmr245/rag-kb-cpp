import { AnimatePresence, motion } from 'motion/react';
import { AlertCircle, CheckCircle2 } from 'lucide-react';
import type { SeedImportPreflight } from '../lib/importValidation';
import type { StarterPackDefinition } from '../lib/starterPack';

interface SeedImportModalProps {
  open: boolean;
  importing: boolean;
  worldbookDraft: string;
  characterDraft: string;
  starterPacks: StarterPackDefinition[];
  selectedStarterPackId: string;
  preflight: SeedImportPreflight;
  onClose: () => void;
  onChangeWorldbookDraft: (value: string) => void;
  onChangeCharacterDraft: (value: string) => void;
  onLoadStarterKit: () => void;
  onSelectStarterPack: (packId: string) => void;
  onImport: () => void;
}

export function SeedImportModal({
  open,
  importing,
  worldbookDraft,
  characterDraft,
  starterPacks,
  selectedStarterPackId,
  preflight,
  onClose,
  onChangeWorldbookDraft,
  onChangeCharacterDraft,
  onLoadStarterKit,
  onSelectStarterPack,
  onImport,
}: SeedImportModalProps) {
  const visibleIssues = preflight.issues.slice(0, 6);
  const statusLabel = preflight.canImport
    ? '预检通过'
    : preflight.errorCount
      ? `${preflight.errorCount} 个阻塞问题`
      : '等待补全导入内容';

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
            className="session-composer-modal seed-import-modal"
            initial={{ opacity: 0, y: 24, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.985 }}
            transition={{ duration: 0.26 }}
          >
            <div className="session-composer-header">
              <div>
                <p className="eyebrow">{'设定导入'}</p>
                <h3>{'先把 worldbook 和角色卡带进这片夜色里'}</h3>
              </div>
              <button className="ghost-button" onClick={onClose} type="button">
                {'关闭'}
              </button>
            </div>

            <div className="seed-import-body">
              <div className="seed-import-guide">
                <div className="seed-import-note">
                  <span className="preview-label">{'为什么先做这里'}</span>
                  <p>{'第一阶段的真正阻塞点是内容输入。先能导入 worldbook 和角色卡，后面的 session、scene、turn 才有稳定地基。'}</p>
                </div>
                <div className="seed-import-actions">
                  <button className="ghost-button" onClick={onLoadStarterKit} type="button">
                    {'填入示例设定包'}
                  </button>
                  <span className="seed-import-hint">{'角色卡区域支持 JSON 数组，一次可以导入多张。'}</span>
                </div>
              </div>

              <section className="seed-import-library">
                <div className="seed-import-library-header">
                  <span className="preview-label">{'最小示例库'}</span>
                  <span className="seed-import-hint">{'先选一套，再按“填入示例设定包”即可覆盖编辑区。'}</span>
                </div>
                <div className="seed-import-pack-list">
                  {starterPacks.map((pack) => (
                    <button
                      className={`seed-import-pack${pack.id === selectedStarterPackId ? ' is-selected' : ''}`}
                      key={pack.id}
                      onClick={() => onSelectStarterPack(pack.id)}
                      type="button"
                    >
                      <strong>{pack.name}</strong>
                      <span>{pack.summary}</span>
                    </button>
                  ))}
                </div>
              </section>

              <div className="seed-import-grid">
                <section className="session-composer-block seed-import-block">
                  <div className="seed-import-block-header">
                    <span className="preview-label">{'worldbook JSON'}</span>
                    <span className="seed-import-counter">{`${worldbookDraft.trim().length} chars`}</span>
                  </div>
                  <div className="seed-import-editor-shell">
                    <textarea
                      className="seed-import-textarea"
                      value={worldbookDraft}
                      onChange={(event) => onChangeWorldbookDraft(event.target.value)}
                      spellCheck={false}
                      placeholder={'粘贴一个完整 worldbook JSON'}
                    />
                  </div>
                </section>

                <section className="session-composer-block seed-import-block">
                  <div className="seed-import-block-header">
                    <span className="preview-label">{'character cards JSON'}</span>
                    <span className="seed-import-counter">{`${characterDraft.trim().length} chars`}</span>
                  </div>
                  <div className="seed-import-editor-shell">
                    <textarea
                      className="seed-import-textarea"
                      value={characterDraft}
                      onChange={(event) => onChangeCharacterDraft(event.target.value)}
                      spellCheck={false}
                      placeholder={'粘贴角色卡 JSON 数组'}
                    />
                  </div>
                </section>
              </div>

              <section className={`seed-import-preflight${preflight.canImport ? ' is-ready' : ''}`}>
                <div className="seed-import-preflight-header">
                  <div className="seed-import-preflight-copy">
                    <span className="preview-label">{'导入前预检'}</span>
                    <strong>{statusLabel}</strong>
                  </div>
                  <span className={`seed-import-preflight-badge${preflight.canImport ? ' is-ready' : ''}`}>
                    {preflight.canImport ? (
                      <>
                        <CheckCircle2 size={14} />
                        {'可以导入'}
                      </>
                    ) : (
                      <>
                        <AlertCircle size={14} />
                        {'需要修复'}
                      </>
                    )}
                  </span>
                </div>

                <div className="seed-import-preflight-summary">
                  <span>{preflight.summary.worldbookTitle || '未识别 worldbook 标题'}</span>
                  <span>{`${preflight.summary.locationCount} 个场景`}</span>
                  <span>{`${preflight.summary.eventSeedCount} 个事件种子`}</span>
                  <span>{`${preflight.summary.characterCount} 张角色卡`}</span>
                </div>

                {visibleIssues.length ? (
                  <ul className="seed-import-issue-list">
                    {visibleIssues.map((issue) => (
                      <li className={`seed-import-issue seed-import-issue--${issue.severity}`} key={issue.id}>
                        <strong>{issue.path}</strong>
                        <span>
                          {issue.message}
                          {issue.line ? ` · 第 ${issue.line} 行` : ''}
                          {issue.column ? `, 第 ${issue.column} 列` : ''}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="seed-import-preflight-empty">{'当前没有发现阻塞问题，直接导入即可。'}</p>
                )}
              </section>
            </div>

            <div className="session-composer-footer">
              <div>
                <span className="preview-label">{'导入顺序'}</span>
                <p>{'会先创建 worldbook，再顺序写入角色卡。成功后前端会自动刷新目录并选中这个世界。'}</p>
              </div>
              <button className="primary-button" disabled={importing || !preflight.canImport} onClick={onImport} type="button">
                {importing ? '导入中...' : preflight.canImport ? '导入设定并刷新舞台' : '先修复预检问题'}
              </button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
