import { startTransition, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { AlertCircle, Ghost, Send, Sparkles, Zap } from 'lucide-react';

import { DialogueStage } from './components/DialogueStage';
import { SceneInspector } from './components/SceneInspector';
import { SessionComposerModal } from './components/SessionComposerModal';
import { SessionRail } from './components/SessionRail';
import { TurnSpotlight } from './components/TurnSpotlight';
import { WorldbookPreview } from './components/WorldbookPreview';
import { createSession, getSession, getWorldbook, listCharacters, listSessions, listWorldbooks, sendTurn } from './lib/api';
import type {
  CharacterCardSummary,
  GameSession,
  GameSessionSummary,
  GameTurnDebug,
  GameTurnResult,
  SceneSnapshot,
  Worldbook,
  WorldbookSummary,
} from './lib/types';

const EMPTY_MESSAGE = '\u8bd5\u7740\u8f93\u5165\u4e00\u53e5\u5e26\u60c5\u7eea\u3001\u627f\u8bfa\u3001\u8bd5\u63a2\u6216\u8bd5\u9519\u610f\u5473\u7684\u8bdd\uff0c\u8ba9\u5bfc\u6f14\u63a8\u52a8\u8fd9\u4e00\u8f6e\u3002';
const DEFAULT_COMPOSER = '\u8c22\u8c22\u4f60\u4eca\u5929\u613f\u610f\u966a\u6211\u5728\u56fe\u4e66\u9986\u591a\u5f85\u4e00\u4f1a\u513f\u3002';

export default function App() {
  const [worldbooks, setWorldbooks] = useState<WorldbookSummary[]>([]);
  const [worldbookCharacters, setWorldbookCharacters] = useState<CharacterCardSummary[]>([]);
  const [selectedWorldbook, setSelectedWorldbook] = useState<Worldbook | null>(null);
  const [sessions, setSessions] = useState<GameSessionSummary[]>([]);
  const [selectedWorldbookId, setSelectedWorldbookId] = useState('');
  const [activeSessionId, setActiveSessionId] = useState('');
  const [activeSession, setActiveSession] = useState<GameSession | null>(null);
  const [activeScene, setActiveScene] = useState<SceneSnapshot | null>(null);
  const [lastTurnResult, setLastTurnResult] = useState<GameTurnResult | null>(null);
  const [lastTurnDebug, setLastTurnDebug] = useState<GameTurnDebug | null>(null);
  const [composerValue, setComposerValue] = useState(DEFAULT_COMPOSER);
  const [loadingBootstrap, setLoadingBootstrap] = useState(true);
  const [creatingSession, setCreatingSession] = useState(false);
  const [submittingTurn, setSubmittingTurn] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [sessionComposerOpen, setSessionComposerOpen] = useState(false);
  const [draftCharacterIds, setDraftCharacterIds] = useState<string[]>([]);
  const [draftLocationId, setDraftLocationId] = useState('');
  const composerRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      setLoadingBootstrap(true);
      try {
        const [worldbookResp, sessionResp] = await Promise.all([listWorldbooks(), listSessions()]);
        if (cancelled) return;

        const nextWorldbooks = worldbookResp.items;
        const nextSessions = sessionResp.items;
        startTransition(() => {
          setWorldbooks(nextWorldbooks);
          setSessions(nextSessions);
        });

        const preferredWorldbookId = nextSessions[0]?.worldbookId || nextWorldbooks[0]?.id || '';
        if (preferredWorldbookId) {
          setSelectedWorldbookId(preferredWorldbookId);
        }
        if (nextSessions[0]?.id) {
          await openSession(nextSessions[0].id);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : '\u521d\u59cb\u5316\u5931\u8d25');
        }
      } finally {
        if (!cancelled) {
          setLoadingBootstrap(false);
        }
      }
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedWorldbookId) return;
    let cancelled = false;

    async function refreshWorldbookContext() {
      try {
        const [worldbook, charactersResponse] = await Promise.all([
          getWorldbook(selectedWorldbookId),
          listCharacters(selectedWorldbookId),
        ]);

        if (!cancelled) {
          startTransition(() => {
            setSelectedWorldbook(worldbook);
            setWorldbookCharacters(charactersResponse.items);
            setDraftCharacterIds(charactersResponse.items.map((item) => item.id));
            setDraftLocationId(worldbook.locations[0]?.id || '');
          });
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : '\u52a0\u8f7d\u4e16\u754c\u89c2\u5931\u8d25');
        }
      }
    }

    refreshWorldbookContext();
    return () => {
      cancelled = true;
    };
  }, [selectedWorldbookId]);

  useEffect(() => {
    const textarea = composerRef.current;
    if (!textarea) return;

    textarea.style.height = '0px';
    const nextHeight = Math.min(textarea.scrollHeight, 220);
    textarea.style.height = `${Math.max(92, nextHeight)}px`;
  }, [composerValue, activeSessionId]);

  async function openSession(sessionId: string) {
    try {
      const response = await getSession(sessionId);
      startTransition(() => {
        setActiveSessionId(response.session.id);
        setActiveSession(response.session);
        setActiveScene(response.scene);
        setLastTurnResult(null);
        setLastTurnDebug(null);
        setSelectedWorldbookId(response.session.worldbookId);
      });
    } catch {
      setErrorMessage('\u4f1a\u8bdd\u52a0\u8f7d\u5931\u8d25');
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = composerValue.trim();
    if (!activeSessionId || !content) return;

    setSubmittingTurn(true);
    try {
      const response = await sendTurn(activeSessionId, content);
      startTransition(() => {
        setActiveSession(response.session);
        setActiveScene(response.scene);
        setLastTurnResult(response.result);
        setLastTurnDebug(response.debug);
      });
      const sessionResp = await listSessions();
      setSessions(sessionResp.items);
    } catch {
      setErrorMessage('\u53d1\u9001\u5931\u8d25');
    } finally {
      setSubmittingTurn(false);
    }
  }

  const actorNames = useMemo(
    () =>
      worldbookCharacters.reduce<Record<string, string>>((acc, item) => {
        acc[item.id] = item.name;
        return acc;
      }, {}),
    [worldbookCharacters],
  );

  const sceneLabel = activeScene ? `${activeScene.locationName} \u00b7 ${activeScene.timeBlock}` : '\u7b49\u5f85\u5267\u60c5\u5f00\u59cb';
  const hasSession = Boolean(activeSession);
  const showBootstrapSkeleton = loadingBootstrap && !worldbooks.length && !sessions.length && !activeSession;
  const shellClassName = ['app-shell', submittingTurn ? 'is-submitting' : '', loadingBootstrap ? 'is-bootstrapping' : '']
    .filter(Boolean)
    .join(' ');

  const heroChips = [
    selectedWorldbook?.title || '\u672a\u9009\u62e9\u4e16\u754c\u89c2',
    activeScene?.locationName || '\u821e\u53f0\u7a97\u53e3\u5f85\u547d',
    lastTurnResult?.eventSeed || '\u7b49\u5f85\u65b0\u7684\u7ebf\u7d22',
  ];

  const renderWindowHeadline = hasSession ? activeScene?.locationName || '\u573a\u666f\u76d1\u89c6\u7a97' : '\u540e\u7eed\u6e32\u67d3\u7a97\u53e3';
  const renderWindowBody = hasSession
    ? lastTurnResult?.primaryReply || activeScene?.locationDescription || '\u8fd9\u4e00\u8f6e\u5df2\u7ecf\u51c6\u5907\u597d\u8fdb\u5165\u66f4\u5177\u4f53\u7684\u89c6\u89c9\u5448\u73b0\u3002'
    : '\u8fd9\u91cc\u9884\u7559\u7ed9\u6587\u751f\u56fe\u7ed3\u679c\u3001\u52a8\u6001\u573a\u666f\u6e32\u67d3\u3001\u7ed3\u6784\u5316\u5361\u7247\uff0c\u6216\u6a21\u578b\u8fd4\u56de\u7684\u53ef\u89c6\u5316\u7247\u6bb5\u3002';
  const renderWindowCue = hasSession
    ? lastTurnDebug?.directorNote || '\u672c\u8f6e\u8fd8\u6ca1\u6709\u989d\u5916\u7684\u5bfc\u6f14\u63d0\u793a\u3002'
    : '\u66f4\u7a33\u7684\u505a\u6cd5\u662f\u8ba9\u6a21\u578b\u8fd4\u56de\u7ed3\u6784\u5316\u6e32\u67d3\u6307\u4ee4\uff0c\u800c\u4e0d\u662f\u76f4\u63a5\u751f\u6210\u524d\u7aef HTML\u3002';

  return (
    <div className={shellClassName}>
      <div className="app-atmosphere" />

      <SessionRail
        worldbooks={worldbooks}
        selectedWorldbookId={selectedWorldbookId}
        onSelectWorldbook={setSelectedWorldbookId}
        worldbookCharacters={worldbookCharacters}
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={openSession}
        onOpenSessionComposer={() => setSessionComposerOpen(true)}
        creatingSession={creatingSession}
      />

      <main className="main-stage">
        <header className="top-strip">
          <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}>
            <p className="eyebrow">
              <Sparkles size={12} className="inline-icon" />
              {'\u5bfc\u6f14\u7f16\u6392\u604b\u7231\u6c99\u76d2'}
            </p>
          </motion.div>
          <div className="status-strip">
            <div className="status-badge">
              <span className={`status-dot ${loadingBootstrap ? 'is-loading' : 'is-online'}`} />
              {loadingBootstrap ? '\u540c\u6b65\u4e2d' : '\u7cfb\u7edf\u5728\u7ebf'}
            </div>
            <span className="session-id-tag">{activeSession ? `\u4f1a\u8bdd ${activeSessionId.slice(0, 8)}` : '\u5f85\u673a'}</span>
          </div>
        </header>

        {showBootstrapSkeleton ? (
          <section className="hero-stage hero-stage--skeleton" aria-hidden="true">
            <div className="surface-skeleton surface-skeleton--hero-copy">
              <span className="skeleton-line skeleton-line--eyebrow" />
              <span className="skeleton-line skeleton-line--headline-lg" />
              <span className="skeleton-line skeleton-line--headline-md" />
              <span className="skeleton-line skeleton-line--body" />
              <span className="skeleton-line skeleton-line--body short" />
            </div>
            <div className="surface-skeleton surface-skeleton--render">
              <div className="skeleton-chip-row">
                <span className="skeleton-chip" />
                <span className="skeleton-chip" />
              </div>
              <span className="skeleton-line skeleton-line--headline-sm" />
              <div className="skeleton-frame" />
              <span className="skeleton-line skeleton-line--body" />
            </div>
          </section>
        ) : (
          <section className="hero-stage">
            <div className="hero-copy">
              <h2 className="hero-title">{'\u628a\u8bbe\u5b9a\u3001\u60c5\u7eea\u548c\u821e\u53f0\uff0c\u6536\u8fdb\u540c\u4e00\u591c\u91cc\u3002'}</h2>
              <p className="hero-support">{'\u5de6\u4fa7\u770b\u4e16\u754c\u89c2\u4e0e\u89d2\u8272\uff0c\u53f3\u4fa7\u770b\u5173\u7cfb\u4e0e\u573a\u666f\u53d8\u5316\uff0c\u4e2d\u95f4\u4fdd\u7559\u4e00\u5757\u771f\u6b63\u7684\u821e\u53f0\u7a97\u53e3\uff0c\u540e\u7eed\u53ef\u4ee5\u63a5\u6587\u751f\u56fe\u3001\u52a8\u6001\u6e32\u67d3\uff0c\u6216\u6a21\u578b\u8fd4\u56de\u7684\u7ed3\u6784\u5316\u5c55\u793a\u3002'}</p>
              <div className="hero-meta-row">
                {heroChips.map((chip) => (
                  <span className="hero-chip" key={chip}>
                    {chip}
                  </span>
                ))}
              </div>
            </div>

            <motion.section
              className="scene-canvas"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.28 }}
            >
              <div className="scene-canvas-header">
                <p className="eyebrow">{'\u821e\u53f0\u7a97\u53e3'}</p>
                <span className="scene-canvas-status">{hasSession ? '\u5b9e\u65f6\u9884\u7559' : '\u5f85\u63a5\u5165'}</span>
              </div>
              <div className="scene-canvas-screen">
                <div className="scene-canvas-overlay" />
                <div className="scene-canvas-body">
                  <strong>{renderWindowHeadline}</strong>
                  <p>{renderWindowBody}</p>
                </div>
              </div>
              <div className="scene-canvas-footer">
                <div>
                  <span className="preview-label">{'\u6e32\u67d3\u63d0\u793a'}</span>
                  <p>{renderWindowCue}</p>
                </div>
                <div className="scene-canvas-badges">
                  <span>{'\u6587\u751f\u56fe\u5165\u53e3'}</span>
                  <span>{'\u7ed3\u6784\u5316\u5c55\u793a\u5165\u53e3'}</span>
                </div>
              </div>
            </motion.section>
          </section>
        )}

        {showBootstrapSkeleton ? (
          <section className="feature-band feature-band--skeleton" aria-hidden="true">
            <div className="surface-skeleton">
              <span className="skeleton-line skeleton-line--eyebrow" />
              <span className="skeleton-line skeleton-line--headline-sm" />
              <span className="skeleton-line skeleton-line--body" />
              <span className="skeleton-line skeleton-line--body short" />
            </div>
            <div className="surface-skeleton">
              <span className="skeleton-line skeleton-line--eyebrow" />
              <span className="skeleton-line skeleton-line--headline-sm" />
              <span className="skeleton-line skeleton-line--body" />
              <span className="skeleton-line skeleton-line--body short" />
            </div>
          </section>
        ) : (
          <section className="feature-band">
            <TurnSpotlight result={lastTurnResult} debug={lastTurnDebug} hasSession={hasSession} />
            <WorldbookPreview worldbook={selectedWorldbook} characters={worldbookCharacters} selected={Boolean(selectedWorldbookId)} />
          </section>
        )}

        {showBootstrapSkeleton ? (
          <section className="dialogue-container dialogue-container--skeleton" aria-hidden="true">
            <div className="surface-skeleton surface-skeleton--dialogue">
              <div className="skeleton-chip-row">
                <span className="skeleton-chip" />
                <span className="skeleton-chip" />
              </div>
              <span className="skeleton-line skeleton-line--headline-md" />
              <span className="skeleton-line skeleton-line--body" />
              <div className="skeleton-dialogue">
                <div className="skeleton-bubble skeleton-bubble--wide" />
                <div className="skeleton-bubble skeleton-bubble--reply" />
                <div className="skeleton-bubble skeleton-bubble--wide" />
              </div>
            </div>
          </section>
        ) : (
          <AnimatePresence mode="wait">
            <motion.div
              key={activeSessionId || 'idle-stage'}
              initial={{ opacity: 0, scale: 0.985 }}
              animate={{ opacity: 1, scale: 1 }}
              className="dialogue-container"
            >
              <DialogueStage
                session={activeSession}
                activeSceneLabel={sceneLabel}
                actorNames={actorNames}
                lastTurnResult={lastTurnResult}
                pending={submittingTurn}
              />
            </motion.div>
          </AnimatePresence>
        )}

        <form className="composer-container" onSubmit={handleSubmit}>
          <div className="composer-inner">
            <div className="composer-header">
              <label className="composer-label">
                <Ghost size={14} />
                {'\u73a9\u5bb6\u8f93\u5165'}
              </label>
              <div className="composer-hint">
                {hasSession ? (
                  <span className="fade-in">
                    <Zap size={12} />
                    {`${lastTurnDebug?.selectedMemorySummaries.length ?? 0} \u6761\u8bb0\u5fc6\u53c2\u4e0e\u4e2d`}
                  </span>
                ) : (
                  '\u5148\u5f00\u542f\u4e00\u573a\u4f1a\u8bdd\u518d\u7ee7\u7eed'
                )}
              </div>
            </div>
            <textarea
              id="turn-input"
              ref={composerRef}
              value={composerValue}
              onChange={(e) => setComposerValue(e.target.value)}
              placeholder={EMPTY_MESSAGE}
              rows={3}
              disabled={!hasSession || submittingTurn}
            />
            <div className="composer-actions">
              <button
                type="submit"
                className="send-button"
                disabled={!activeSessionId || submittingTurn || !composerValue.trim()}
              >
                {submittingTurn ? <span className="loading-text">{'\u5bfc\u6f14\u56de\u5e94\u4e2d...'}</span> : <>{'\u53d1\u9001\u56de\u5408'}<Send size={16} /></>}
              </button>
            </div>
          </div>
        </form>

        <AnimatePresence>
          {errorMessage ? (
            <motion.div className="error-banner" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              <AlertCircle size={16} /> {errorMessage}
            </motion.div>
          ) : null}
        </AnimatePresence>
      </main>

      <SceneInspector scene={activeScene} session={activeSession} actorNames={actorNames} lastTurnResult={lastTurnResult} />

      <SessionComposerModal
        open={sessionComposerOpen}
        worldbook={selectedWorldbook}
        characters={worldbookCharacters}
        selectedCharacterIds={draftCharacterIds}
        selectedLocationId={draftLocationId}
        creating={creatingSession}
        onClose={() => setSessionComposerOpen(false)}
        onToggleCharacter={(id) =>
          setDraftCharacterIds((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]))
        }
        onSelectLocation={setDraftLocationId}
        onConfirm={async () => {
          setCreatingSession(true);
          try {
            const response = await createSession({
              worldbookId: selectedWorldbookId,
              characterIds: draftCharacterIds,
              title: `${selectedWorldbook?.title || '\u65b0\u4f1a\u8bdd'} \u00b7 \u591c\u4e00`,
              openingLocationId: draftLocationId,
            });
            setActiveSessionId(response.session.id);
            setActiveSession(response.session);
            setActiveScene(response.scene);
            setSessionComposerOpen(false);
            const list = await listSessions();
            setSessions(list.items);
          } finally {
            setCreatingSession(false);
          }
        }}
      />
    </div>
  );
}
