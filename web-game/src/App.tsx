import {
  startTransition,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FocusEvent as ReactFocusEvent,
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
} from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { AlertCircle, CheckCircle2, Ghost, Pin, PinOff, Send, Sparkles, X, Zap } from 'lucide-react';

import { DialogueStage } from './components/DialogueStage';
import { SceneInspector } from './components/SceneInspector';
import { SeedImportModal } from './components/SeedImportModal';
import { SessionComposerModal } from './components/SessionComposerModal';
import { SessionRail } from './components/SessionRail';
import { TurnSpotlight } from './components/TurnSpotlight';
import { WorldbookPreview } from './components/WorldbookPreview';
import {
  createCharacterCard,
  createSession,
  createWorldbook,
  getSession,
  getWorldbook,
  listCharacters,
  listSessions,
  listWorldbooks,
  sendTurn,
  updateSession,
} from './lib/api';
import { starterCharactersJson, starterPackJsonById, starterPacks, starterWorldbookJson } from './lib/starterPack';
import { validateSeedImportDrafts } from './lib/importValidation';
import {
  readSessionWorkspaceMemory,
  rememberImportLaunchCue,
  rememberSelectedWorldbook,
  rememberSessionActivation,
  resolvePreferredSessionId,
  resolvePreferredWorldbookId,
  sortSessionsByUpdatedAt,
  writeSessionWorkspaceMemory,
} from './lib/sessionWorkspace';
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

const EMPTY_MESSAGE = '试着输入一句带情绪、承诺、试探或试错意味的话，让导演推动这一轮。';
const DEFAULT_COMPOSER = '谢谢你今天愿意陪我在图书馆多待一会儿。';
const DEFAULT_IMPORT_WORLD_DRAFT = starterWorldbookJson;
const DEFAULT_IMPORT_CHARACTER_DRAFT = starterCharactersJson;
const DRAWER_TRANSITION = { duration: 0.2, ease: 'easeOut' } as const;
const PANEL_TRANSITION = { duration: 0.18, ease: 'easeOut' } as const;
const PINNED_DRAWER_MEDIA_QUERY = '(min-width: 1366px)';
const LEFT_DRAWER_KEY = 'rag-web-game:left-drawer-state';
const RIGHT_DRAWER_KEY = 'rag-web-game:right-drawer-state';
const HERO_COPY_KEY = 'rag-web-game:show-hero-copy';
const FEATURE_BAND_KEY = 'rag-web-game:show-feature-band';
const DEFAULT_STARTER_PACK_ID = starterPacks[0]?.id || 'starter';

type DrawerState = 'closed' | 'collapsed' | 'expanded' | 'pinned';
type ComposerState = 'idle' | 'focused' | 'sending' | 'disabled';

function readStoredBoolean(key: string, fallback: boolean) {
  if (typeof window === 'undefined') return fallback;
  const value = window.localStorage.getItem(key);
  if (value === null) return fallback;
  return value === 'true';
}

function normalizeStoredDrawerState(value: string | null, canPinDrawers: boolean): DrawerState {
  if (value === 'closed' || value === 'collapsed' || value === 'expanded') return value;
  if (value === 'pinned') return canPinDrawers ? 'pinned' : 'expanded';
  return 'closed';
}

function isPinnedState(state: DrawerState, canPinDrawers: boolean) {
  return canPinDrawers && state === 'pinned';
}

export default function App() {
  const [worldbooks, setWorldbooks] = useState<WorldbookSummary[]>([]);
  const [knownCharacters, setKnownCharacters] = useState<CharacterCardSummary[]>([]);
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
  const [updatingSessionId, setUpdatingSessionId] = useState('');
  const [submittingTurn, setSubmittingTurn] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [sessionComposerOpen, setSessionComposerOpen] = useState(false);
  const [seedImportOpen, setSeedImportOpen] = useState(false);
  const [importingSeed, setImportingSeed] = useState(false);
  const [seedImportSuccessMessage, setSeedImportSuccessMessage] = useState('');
  const [canPinDrawers, setCanPinDrawers] = useState(
    typeof window !== 'undefined' ? window.matchMedia(PINNED_DRAWER_MEDIA_QUERY).matches : true,
  );
  const [leftDrawerState, setLeftDrawerState] = useState<DrawerState>('closed');
  const [rightDrawerState, setRightDrawerState] = useState<DrawerState>('closed');
  const [showHeroCopy, setShowHeroCopy] = useState(() => readStoredBoolean(HERO_COPY_KEY, false));
  const [showFeatureBand, setShowFeatureBand] = useState(() => readStoredBoolean(FEATURE_BAND_KEY, false));
  const [composerFocused, setComposerFocused] = useState(false);
  const [draftCharacterIds, setDraftCharacterIds] = useState<string[]>([]);
  const [draftLocationId, setDraftLocationId] = useState('');
  const [worldbookDraft, setWorldbookDraft] = useState(DEFAULT_IMPORT_WORLD_DRAFT);
  const [characterDraft, setCharacterDraft] = useState(DEFAULT_IMPORT_CHARACTER_DRAFT);
  const [selectedStarterPackId, setSelectedStarterPackId] = useState(DEFAULT_STARTER_PACK_ID);
  const [workspaceMemory, setWorkspaceMemory] = useState(() => readSessionWorkspaceMemory());
  const [renamingSessionId, setRenamingSessionId] = useState('');
  const [renameDraft, setRenameDraft] = useState('');
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const composerFormRef = useRef<HTMLFormElement | null>(null);
  const isComposingRef = useRef(false);
  const hydratedDrawerStateRef = useRef(false);

  async function refreshLibrary() {
    const [worldbookResp, sessionResp, characterResp] = await Promise.all([listWorldbooks(), listSessions(), listCharacters()]);
    const nextWorldbooks = worldbookResp.items;
    const nextSessions = sessionResp.items;
    const nextKnownCharacters = characterResp.items;
    startTransition(() => {
      setWorldbooks(nextWorldbooks);
      setSessions(nextSessions);
      setKnownCharacters(nextKnownCharacters);
    });
    return { nextWorldbooks, nextSessions, nextKnownCharacters };
  }

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const mediaQuery = window.matchMedia(PINNED_DRAWER_MEDIA_QUERY);
    const syncDrawerCapability = (event?: MediaQueryListEvent) => {
      setCanPinDrawers(event?.matches ?? mediaQuery.matches);
    };

    syncDrawerCapability();
    mediaQuery.addEventListener('change', syncDrawerCapability);
    return () => mediaQuery.removeEventListener('change', syncDrawerCapability);
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined' || hydratedDrawerStateRef.current) return;

    setLeftDrawerState(normalizeStoredDrawerState(window.localStorage.getItem(LEFT_DRAWER_KEY), canPinDrawers));
    setRightDrawerState(normalizeStoredDrawerState(window.localStorage.getItem(RIGHT_DRAWER_KEY), canPinDrawers));
    hydratedDrawerStateRef.current = true;
  }, [canPinDrawers]);

  useEffect(() => {
    if (!hydratedDrawerStateRef.current || typeof window === 'undefined') return;
    window.localStorage.setItem(LEFT_DRAWER_KEY, leftDrawerState);
  }, [leftDrawerState]);

  useEffect(() => {
    if (!hydratedDrawerStateRef.current || typeof window === 'undefined') return;
    window.localStorage.setItem(RIGHT_DRAWER_KEY, rightDrawerState);
  }, [rightDrawerState]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(HERO_COPY_KEY, String(showHeroCopy));
  }, [showHeroCopy]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(FEATURE_BAND_KEY, String(showFeatureBand));
  }, [showFeatureBand]);

  useEffect(() => {
    writeSessionWorkspaceMemory(workspaceMemory);
  }, [workspaceMemory]);

  useEffect(() => {
    if (!seedImportSuccessMessage) return;
    const timeoutId = window.setTimeout(() => setSeedImportSuccessMessage(''), 4200);
    return () => window.clearTimeout(timeoutId);
  }, [seedImportSuccessMessage]);

  useEffect(() => {
    if (canPinDrawers) return;
    setLeftDrawerState((prev) => (prev === 'pinned' ? 'expanded' : prev));
    setRightDrawerState((prev) => (prev === 'pinned' ? 'expanded' : prev));
  }, [canPinDrawers]);

  function applyLoadedSession(nextSession: GameSession, nextScene: SceneSnapshot) {
    setErrorMessage('');
    setWorkspaceMemory((prev) => rememberSessionActivation(prev, nextSession));
    startTransition(() => {
      setActiveSessionId(nextSession.id);
      setActiveSession(nextSession);
      setActiveScene(nextScene);
      setLastTurnResult(null);
      setLastTurnDebug(null);
      setSelectedWorldbookId(nextSession.worldbookId);
    });
  }

  function clearActiveWorkspace() {
    startTransition(() => {
      setActiveSessionId('');
      setActiveSession(null);
      setActiveScene(null);
      setLastTurnResult(null);
      setLastTurnDebug(null);
    });
  }

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      setLoadingBootstrap(true);
      try {
        const { nextWorldbooks, nextSessions } = await refreshLibrary();
        if (cancelled) return;

        const preferredWorldbookId = resolvePreferredWorldbookId({
          worldbooks: nextWorldbooks,
          sessions: nextSessions,
          memory: workspaceMemory,
        });
        if (preferredWorldbookId) {
          setSelectedWorldbookId(preferredWorldbookId);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : '初始化失败');
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
    if (!selectedWorldbookId) {
      setSelectedWorldbook(null);
      setWorldbookCharacters([]);
      setDraftCharacterIds([]);
      setDraftLocationId('');
      return;
    }
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
          setErrorMessage(error instanceof Error ? error.message : '加载世界观失败');
        }
      }
    }

    refreshWorldbookContext();
    return () => {
      cancelled = true;
    };
  }, [selectedWorldbookId]);

  useEffect(() => {
    if (!selectedWorldbookId) return;
    setWorkspaceMemory((prev) =>
      prev.lastSelectedWorldbookId === selectedWorldbookId ? prev : rememberSelectedWorldbook(prev, selectedWorldbookId),
    );
  }, [selectedWorldbookId]);

  const canSendTurn = Boolean(activeSessionId) && activeSession?.status === 'active';

  const composerState: ComposerState = !canSendTurn
    ? 'disabled'
    : submittingTurn
      ? 'sending'
      : composerFocused
        ? 'focused'
        : 'idle';

  useEffect(() => {
    const textarea = composerRef.current;
    if (!textarea) return;

    textarea.style.height = '0px';
    const maxHeight = composerState === 'focused' ? 220 : 132;
    const minHeight = composerState === 'focused' ? 108 : 62;
    const nextHeight = Math.min(textarea.scrollHeight, maxHeight);
    textarea.style.height = `${Math.max(minHeight, nextHeight)}px`;
  }, [composerValue, canSendTurn, composerState]);

  useEffect(() => {
    const hasExpandedOverlay = leftDrawerState === 'expanded' || rightDrawerState === 'expanded' || showFeatureBand;
    if (!hasExpandedOverlay) return;

    function handleEscape(event: KeyboardEvent) {
      if (event.key !== 'Escape') return;
      setLeftDrawerState((prev) => (prev === 'expanded' ? 'closed' : prev));
      setRightDrawerState((prev) => (prev === 'expanded' ? 'closed' : prev));
      setShowFeatureBand(false);
    }

    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [leftDrawerState, rightDrawerState, showFeatureBand]);

  async function openSession(sessionId: string) {
    try {
      const response = await getSession(sessionId);
      applyLoadedSession(response.session, response.scene);
    } catch {
      setErrorMessage('会话加载失败');
    }
  }

  function beginRenameSession(session: GameSessionSummary) {
    setRenamingSessionId(session.id);
    setRenameDraft(session.title);
  }

  function cancelRenameSession() {
    setRenamingSessionId('');
    setRenameDraft('');
  }

  async function handleUpdateSession(sessionId: string, payload: { title?: string; status?: 'active' | 'archived' }) {
    setUpdatingSessionId(sessionId);
    try {
      setErrorMessage('');
      const response = await updateSession(sessionId, payload);
      const { nextSessions } = await refreshLibrary();

      if (activeSessionId === response.session.id) {
        startTransition(() => {
          setActiveSession(response.session);
          setActiveScene(response.scene);
        });
      }

      if (payload.status === 'archived') {
        setSeedImportSuccessMessage(`已归档：${response.session.title}`);
      } else if (payload.status === 'active' && response.session.status === 'active') {
        setSeedImportSuccessMessage(`已恢复：${response.session.title}`);
        void openSession(response.session.id);
      } else if (payload.title) {
        setSeedImportSuccessMessage(`已重命名：${response.session.title}`);
      }

      if (
        payload.status === 'archived' &&
        activeSessionId === response.session.id &&
        !nextSessions.some(
          (session) => session.worldbookId === response.session.worldbookId && session.status === 'active',
        )
      ) {
        startTransition(() => {
          setLastTurnResult(null);
          setLastTurnDebug(null);
        });
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '更新会话失败');
    } finally {
      setUpdatingSessionId('');
    }
  }

  async function submitSessionRename() {
    if (!renamingSessionId) return;
    const nextTitle = renameDraft.trim();
    if (!nextTitle) {
      setErrorMessage('会话名称不能为空');
      return;
    }
    await handleUpdateSession(renamingSessionId, { title: nextTitle });
    cancelRenameSession();
  }

  useEffect(() => {
    if (loadingBootstrap || !selectedWorldbookId) return;

    if (activeSession?.worldbookId === selectedWorldbookId) return;

    const preferredSessionId = resolvePreferredSessionId({
      worldbookId: selectedWorldbookId,
      sessions,
      memory: workspaceMemory,
    });

    if (preferredSessionId) {
      void openSession(preferredSessionId);
      return;
    }

    if (activeSessionId || activeSession || activeScene) {
      clearActiveWorkspace();
    }
  }, [activeScene, activeSession, activeSessionId, loadingBootstrap, selectedWorldbookId, sessions, workspaceMemory]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = composerValue.trim();
    if (!activeSessionId || !content || activeSession?.status !== 'active') return;

    setSubmittingTurn(true);
    try {
      setErrorMessage('');
      const response = await sendTurn(activeSessionId, content);
      setWorkspaceMemory((prev) => rememberSessionActivation(prev, response.session));
      startTransition(() => {
        setActiveSession(response.session);
        setActiveScene(response.scene);
        setLastTurnResult(response.result);
        setLastTurnDebug(response.debug);
      });
      const sessionResp = await listSessions();
      setSessions(sessionResp.items);
    } catch {
      setErrorMessage('发送失败');
    } finally {
      setSubmittingTurn(false);
    }
  }

  async function handleImportSeed() {
    const preflight = validateSeedImportDrafts({
      worldbookDraft,
      characterDraft,
      existingWorldbookIds: worldbooks.map((item) => item.id),
      existingCharacterIds: knownCharacters.map((item) => item.id),
    });

    if (!preflight.canImport || !preflight.worldbook) {
      const firstBlockingIssue = preflight.issues.find((issue) => issue.severity === 'error');
      setErrorMessage(firstBlockingIssue ? `${firstBlockingIssue.path}: ${firstBlockingIssue.message}` : '导入预检未通过');
      return;
    }

    setImportingSeed(true);
    try {
      setErrorMessage('');
      setSeedImportSuccessMessage('');
      const parsedWorldbook = preflight.worldbook;
      const parsedCharacters = preflight.characters;
      await createWorldbook(parsedWorldbook);
      for (const card of parsedCharacters) {
        await createCharacterCard(card);
      }

      const { nextSessions } = await refreshLibrary();
      const hasExistingImportedSessions = nextSessions.some((session) => session.worldbookId === parsedWorldbook.id);
      const launchCue = hasExistingImportedSessions
        ? null
        : {
            worldbookId: parsedWorldbook.id,
            worldbookTitle: parsedWorldbook.title,
            characterCount: parsedCharacters.length,
            importedAt: new Date().toISOString(),
          };

      setWorkspaceMemory((prev) => rememberImportLaunchCue(prev, launchCue));
      startTransition(() => {
        setSelectedWorldbookId(parsedWorldbook.id);
        setSeedImportOpen(false);
        setSessionComposerOpen(false);
        setLeftDrawerState((prev) => (prev === 'closed' ? 'expanded' : prev));
        setSeedImportSuccessMessage(
          hasExistingImportedSessions
            ? `导入完成：${parsedWorldbook.title}，已写入 ${parsedCharacters.length} 张角色卡。`
            : `导入完成：${parsedWorldbook.title}，下一步确认开场地点和阵容，点亮第一幕。`,
        );
      });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '导入设定失败');
    } finally {
      setImportingSeed(false);
    }
  }

  function handleComposerFocusCapture() {
    setComposerFocused(true);
  }

  function handleComposerBlurCapture(event: ReactFocusEvent<HTMLFormElement>) {
    const relatedTarget = event.relatedTarget;
    if (relatedTarget instanceof Node && event.currentTarget.contains(relatedTarget)) return;
    setComposerFocused(false);
  }

  function handleComposerKeyDown(event: ReactKeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== 'Enter') return;
    if (!event.ctrlKey && !event.metaKey) return;
    if (event.shiftKey || isComposingRef.current || event.nativeEvent.isComposing) return;
    event.preventDefault();
    composerFormRef.current?.requestSubmit();
  }

  function openDrawer(side: 'left' | 'right') {
    if (side === 'left') {
      setLeftDrawerState('expanded');
      return;
    }
    setRightDrawerState('expanded');
  }

  function collapseDrawer(side: 'left' | 'right') {
    if (side === 'left') {
      setLeftDrawerState('collapsed');
      return;
    }
    setRightDrawerState('collapsed');
  }

  function closeDrawer(side: 'left' | 'right') {
    if (side === 'left') {
      setLeftDrawerState('closed');
      return;
    }
    setRightDrawerState('closed');
  }

  function togglePinnedDrawer(side: 'left' | 'right') {
    if (side === 'left') {
      setLeftDrawerState((prev) => {
        if (!canPinDrawers) return 'collapsed';
        return prev === 'pinned' ? 'expanded' : 'pinned';
      });
      return;
    }
    setRightDrawerState((prev) => {
      if (!canPinDrawers) return 'collapsed';
      return prev === 'pinned' ? 'expanded' : 'pinned';
    });
  }

  function toggleDrawerFromTopBar(side: 'left' | 'right') {
    const currentState = side === 'left' ? leftDrawerState : rightDrawerState;
    if (currentState === 'closed' || currentState === 'collapsed') {
      openDrawer(side);
      return;
    }
    closeDrawer(side);
  }

  function loadStarterPack(packId: string) {
    const payload = starterPackJsonById[packId];
    if (!payload) return;
    setSelectedStarterPackId(packId);
    setWorldbookDraft(payload.worldbookJson);
    setCharacterDraft(payload.characterJson);
  }

  const scopedSessions = useMemo(
    () => sortSessionsByUpdatedAt(sessions.filter((session) => session.worldbookId === selectedWorldbookId)),
    [selectedWorldbookId, sessions],
  );

  const locationNameById = useMemo(
    () =>
      (selectedWorldbook?.locations || []).reduce<Record<string, string>>((acc, location) => {
        acc[location.id] = location.name;
        return acc;
      }, {}),
    [selectedWorldbook],
  );

  const railSessions = useMemo(
    () =>
      scopedSessions.map((session) => ({
        id: session.id,
        title: session.title,
        status: session.status,
        updatedAt: session.updatedAt,
        currentLocationLabel: locationNameById[session.currentLocationId] || session.currentLocationId || '未设定地点',
        currentCastCount: session.currentCast.length,
        isActive: session.id === activeSessionId,
        summary: session,
      })),
    [activeSessionId, locationNameById, scopedSessions],
  );

  const activeRailSessions = useMemo(
    () => railSessions.filter((session) => session.status === 'active'),
    [railSessions],
  );

  const archivedRailSessions = useMemo(
    () => railSessions.filter((session) => session.status === 'archived'),
    [railSessions],
  );

  const recentSessionId = useMemo(
    () =>
      resolvePreferredSessionId({
        worldbookId: selectedWorldbookId,
        sessions,
        memory: workspaceMemory,
      }),
    [selectedWorldbookId, sessions, workspaceMemory],
  );

  const recentSession = useMemo(
    () => activeRailSessions.find((session) => session.id === recentSessionId) || activeRailSessions[0] || null,
    [activeRailSessions, recentSessionId],
  );

  const importLaunchCue =
    workspaceMemory.importLaunchCue?.worldbookId === selectedWorldbookId ? workspaceMemory.importLaunchCue : null;

  useEffect(() => {
    if (!importLaunchCue || !selectedWorldbook || scopedSessions.length > 0 || sessionComposerOpen) return;
    if (!worldbookCharacters.length || !selectedWorldbook.locations.length) return;
    setSessionComposerOpen(true);
  }, [importLaunchCue, scopedSessions.length, selectedWorldbook, sessionComposerOpen, worldbookCharacters.length]);

  const actorNames = useMemo(
    () =>
      worldbookCharacters.reduce<Record<string, string>>((acc, item) => {
        acc[item.id] = item.name;
        return acc;
      }, {}),
    [worldbookCharacters],
  );

  const sceneLabel = activeScene
    ? `${activeScene.locationName} · ${activeScene.timeBlock}${activeSession?.status === 'archived' ? ' · 已归档' : ''}`
    : '等待剧情开始';
  const hasSession = Boolean(activeSession);
  const showBootstrapSkeleton = loadingBootstrap && !worldbooks.length && !sessions.length && !activeSession;
  const hasExpandedOverlayDrawer = leftDrawerState === 'expanded' || rightDrawerState === 'expanded' || showFeatureBand;
  const leftDrawerPinned = isPinnedState(leftDrawerState, canPinDrawers);
  const rightDrawerPinned = isPinnedState(rightDrawerState, canPinDrawers);
  const hasAnyPinnedDrawer = leftDrawerPinned || rightDrawerPinned;
  const hasAuxPanelsOpen =
    leftDrawerState !== 'closed' || rightDrawerState !== 'closed' || showHeroCopy || showFeatureBand;
  const shellClassName = [
    'app-shell',
    submittingTurn ? 'is-submitting' : '',
    loadingBootstrap ? 'is-bootstrapping' : '',
    hasExpandedOverlayDrawer ? 'has-overlay-drawer' : '',
    hasAnyPinnedDrawer ? 'has-pinned-drawer' : '',
    leftDrawerPinned ? 'has-left-pinned' : '',
    rightDrawerPinned ? 'has-right-pinned' : '',
    composerState === 'focused' ? 'is-composer-focused' : '',
  ]
    .filter(Boolean)
    .join(' ');
  const heroStageClassName = ['hero-stage', !showHeroCopy ? 'is-condensed' : '', hasSession ? 'is-live' : 'is-idle']
    .filter(Boolean)
    .join(' ');
  const composerClassName = ['composer-container', `is-${composerState}`].join(' ');
  const composerInnerClassName = ['composer-inner', `composer-inner--${composerState}`].join(' ');
  const seedImportPreflight = useMemo(
    () =>
      validateSeedImportDrafts({
        worldbookDraft,
        characterDraft,
        existingWorldbookIds: worldbooks.map((item) => item.id),
        existingCharacterIds: knownCharacters.map((item) => item.id),
      }),
    [characterDraft, knownCharacters, worldbookDraft, worldbooks],
  );

  const heroChips = [
    selectedWorldbook?.title || '未选择世界观',
    activeScene?.locationName || '舞台窗口待命',
    lastTurnResult?.eventSeed || '等待新的线索',
  ];

  const renderWindowHeadline = hasSession ? activeScene?.locationName || '场景监视窗' : '待开幕舞台';
  const renderWindowBody = hasSession
    ? lastTurnResult?.primaryReply || activeScene?.locationDescription || '这一轮已经准备好进入更具体的视觉呈现。'
    : '第一幕尚未点亮。先选择世界、角色和开场地点，让导演把这一夜推上舞台。';
  const renderWindowCue = hasSession
    ? lastTurnDebug?.directorNote || '本轮还没有额外的导演提示。'
    : '等待角色入场与第一句台词，舞台会从静态幕布切到演出中状态。';
  const stageCueItems = [
    activeScene?.timeBlock || '开场前',
    lastTurnResult?.eventSeed || '未触发事件 cue',
    hasSession ? '演出中' : '待开幕',
  ];
  const stageStatusLabel = hasSession ? '演出中' : '待接入';
  const composerPlaceholder =
    activeSession?.status === 'archived'
      ? '这条记忆线已经归档。恢复后才能继续输入新的回合。'
      : hasSession
        ? EMPTY_MESSAGE
        : '先开启一场会话，再把第一句台词送上舞台。';
  const composerStatusCopy =
    composerState === 'sending'
      ? '导演回应中'
      : composerState === 'disabled'
        ? activeSession?.status === 'archived'
          ? '当前会话已归档，恢复后可继续推进'
          : '先开启一场会话再继续'
        : sceneLabel;
  const composerStatePill =
    composerState === 'sending'
      ? '发送中'
      : composerState === 'disabled'
        ? '待开场'
        : composerState === 'focused'
          ? '输入中'
          : '就绪';

  return (
    <div className={shellClassName}>
      <div className="app-atmosphere" />

      <AnimatePresence>
        {hasExpandedOverlayDrawer ? (
          <motion.button
            aria-label="关闭展开面板"
            className="drawer-scrim"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => {
              setLeftDrawerState((prev) => (prev === 'expanded' ? 'closed' : prev));
              setRightDrawerState((prev) => (prev === 'expanded' ? 'closed' : prev));
              setShowFeatureBand(false);
            }}
            transition={{ duration: 0.2 }}
            type="button"
          />
        ) : null}
      </AnimatePresence>

      {leftDrawerPinned ? (
        <aside className="workspace-pinned workspace-pinned--left">
          <div className="drawer-chrome drawer-chrome--pinned">
            <div className="drawer-chrome-copy">
              <span className="drawer-label">{'设定工作台'}</span>
              <strong>{'世界观、角色与会话入口'}</strong>
            </div>
            <div className="drawer-actions">
              <button className="ghost-button drawer-action" onClick={() => collapseDrawer('left')} type="button">
                {'收缩'}
              </button>
              <button className="ghost-button drawer-action" onClick={() => togglePinnedDrawer('left')} type="button">
                <PinOff size={14} />
                {'浮动'}
              </button>
            </div>
          </div>
          <SessionRail
            worldbooks={worldbooks}
            selectedWorldbookId={selectedWorldbookId}
            selectedWorldbookTitle={selectedWorldbook?.title || ''}
            onSelectWorldbook={setSelectedWorldbookId}
            worldbookCharacters={worldbookCharacters}
            activeSessions={activeRailSessions}
            archivedSessions={archivedRailSessions}
            recentSession={recentSession}
            renamingSessionId={renamingSessionId}
            renameDraft={renameDraft}
            updatingSessionId={updatingSessionId}
            onRenameDraftChange={setRenameDraft}
            onStartRenameSession={beginRenameSession}
            onCancelRenameSession={cancelRenameSession}
            onSubmitRenameSession={() => {
              void submitSessionRename();
            }}
            onSelectSession={openSession}
            onResumeRecentSession={openSession}
            onArchiveSession={(sessionId) => {
              void handleUpdateSession(sessionId, { status: 'archived' });
            }}
            onRestoreSession={(sessionId) => {
              void handleUpdateSession(sessionId, { status: 'active' });
            }}
            onOpenSessionComposer={() => setSessionComposerOpen(true)}
            onOpenSeedImport={() => setSeedImportOpen(true)}
            creatingSession={creatingSession}
            launchCue={
              importLaunchCue
                ? {
                    worldbookTitle: importLaunchCue.worldbookTitle,
                    characterCount: importLaunchCue.characterCount,
                  }
                : null
            }
          />
        </aside>
      ) : null}

      <AnimatePresence initial={false}>
        {leftDrawerState === 'expanded' ? (
          <motion.div
            className="workspace-drawer workspace-drawer--left"
            initial={{ opacity: 0, x: -40 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -48 }}
            transition={DRAWER_TRANSITION}
          >
            <div className="drawer-chrome">
              <div className="drawer-chrome-copy">
                <span className="drawer-label">{'设定工作台'}</span>
                <strong>{'世界观、角色与会话入口'}</strong>
              </div>
              <div className="drawer-actions">
                <button className="ghost-button drawer-action" onClick={() => collapseDrawer('left')} type="button">
                  {'收缩'}
                </button>
                <button className="ghost-button drawer-action" onClick={() => togglePinnedDrawer('left')} type="button">
                  <Pin size={14} />
                  {canPinDrawers ? '固定' : '停靠'}
                </button>
                <button
                  aria-label="关闭设定面板"
                  className="ghost-button drawer-close"
                  onClick={() => closeDrawer('left')}
                  type="button"
                >
                  <X size={16} />
                </button>
              </div>
            </div>

            <SessionRail
              worldbooks={worldbooks}
              selectedWorldbookId={selectedWorldbookId}
              selectedWorldbookTitle={selectedWorldbook?.title || ''}
              onSelectWorldbook={setSelectedWorldbookId}
              worldbookCharacters={worldbookCharacters}
              activeSessions={activeRailSessions}
              archivedSessions={archivedRailSessions}
              recentSession={recentSession}
              renamingSessionId={renamingSessionId}
              renameDraft={renameDraft}
              updatingSessionId={updatingSessionId}
              onRenameDraftChange={setRenameDraft}
              onStartRenameSession={beginRenameSession}
              onCancelRenameSession={cancelRenameSession}
              onSubmitRenameSession={() => {
                void submitSessionRename();
              }}
              onSelectSession={openSession}
              onResumeRecentSession={openSession}
              onArchiveSession={(sessionId) => {
                void handleUpdateSession(sessionId, { status: 'archived' });
              }}
              onRestoreSession={(sessionId) => {
                void handleUpdateSession(sessionId, { status: 'active' });
              }}
              onOpenSessionComposer={() => setSessionComposerOpen(true)}
              onOpenSeedImport={() => setSeedImportOpen(true)}
              creatingSession={creatingSession}
              launchCue={
                importLaunchCue
                  ? {
                      worldbookTitle: importLaunchCue.worldbookTitle,
                      characterCount: importLaunchCue.characterCount,
                    }
                  : null
              }
            />
          </motion.div>
        ) : null}
      </AnimatePresence>

      {leftDrawerState === 'collapsed' ? (
        <button className="drawer-edge-tab drawer-edge-tab--left" onClick={() => openDrawer('left')} type="button">
          <span>{'设定'}</span>
        </button>
      ) : null}

      <main className="main-stage">
        <header className="top-strip">
          <motion.div className="top-strip-copy" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}>
            <div className="top-strip-brand">
              <p className="eyebrow">
                <Sparkles size={12} className="inline-icon" />
                {'导演编排恋爱沙盒'}
              </p>
              <h1 className="workspace-title">{'雾夜导演台'}</h1>
              <p className="workspace-subtitle">{'主舞台居中，设定与关系退到边缘，所有演出从底部导演台发出。'}</p>
            </div>
          </motion.div>

          <div className="top-strip-actions">
            <div className="layout-controls">
              <button
                className={`ghost-button layout-toggle${leftDrawerState !== 'closed' ? ' is-active' : ''}`}
                onClick={() => toggleDrawerFromTopBar('left')}
                type="button"
              >
                {leftDrawerState === 'closed' || leftDrawerState === 'collapsed' ? '展开设定' : '收起设定'}
              </button>
              <button
                className={`ghost-button layout-toggle${showHeroCopy ? ' is-active' : ''}`}
                onClick={() => setShowHeroCopy((prev) => !prev)}
                type="button"
              >
                {showHeroCopy ? '收起引导' : '展开引导'}
              </button>
              <button
                className={`ghost-button layout-toggle${showFeatureBand ? ' is-active' : ''}`}
                onClick={() => setShowFeatureBand((prev) => !prev)}
                type="button"
              >
                {showFeatureBand ? '收起情报' : '展开情报'}
              </button>
              <button
                className={`ghost-button layout-toggle${rightDrawerState !== 'closed' ? ' is-active' : ''}`}
                onClick={() => toggleDrawerFromTopBar('right')}
                type="button"
              >
                {rightDrawerState === 'closed' || rightDrawerState === 'collapsed' ? '展开关系' : '收起关系'}
              </button>
              <button
                className={`ghost-button layout-toggle layout-toggle--focus${hasAuxPanelsOpen ? ' is-active' : ''}`}
                onClick={() => {
                  if (hasAuxPanelsOpen) {
                    setLeftDrawerState('closed');
                    setRightDrawerState('closed');
                    setShowHeroCopy(false);
                    setShowFeatureBand(false);
                    return;
                  }
                  setLeftDrawerState('expanded');
                  setRightDrawerState('expanded');
                  setShowHeroCopy(true);
                  setShowFeatureBand(true);
                }}
                type="button"
              >
                {hasAuxPanelsOpen ? '仅看主体' : '展开全部'}
              </button>
              {!worldbooks.length ? (
                <button
                  className="ghost-button layout-toggle layout-toggle--action"
                  onClick={() => setSeedImportOpen(true)}
                  type="button"
                >
                  {'导入设定'}
                </button>
              ) : null}
            </div>

            <div className="status-strip">
              <div className="status-badge">
                <span className={`status-dot ${loadingBootstrap ? 'is-loading' : 'is-online'}`} />
                {loadingBootstrap ? '同步中' : '系统在线'}
              </div>
              <span className="session-id-tag">{activeSession ? `会话 ${activeSessionId.slice(0, 8)}` : '待机'}</span>
            </div>
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
          <section className={heroStageClassName}>
            <AnimatePresence initial={false}>
              {showHeroCopy ? (
                <motion.div
                  className="hero-copy"
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -16 }}
                  transition={PANEL_TRANSITION}
                >
                  <h2 className="hero-title">{'把设定、情绪和舞台，收进同一夜里。'}</h2>
                  <p className="hero-support">
                    {'主舞台负责演出，剧情流负责推进，左右抽屉只在你需要上下文时出现，底部导演台始终待命。'}
                  </p>
                  <div className="hero-meta-row">
                    {heroChips.map((chip) => (
                      <span className="hero-chip" key={chip}>
                        {chip}
                      </span>
                    ))}
                  </div>
                </motion.div>
              ) : null}
            </AnimatePresence>

            <motion.section
              className={`scene-canvas${hasSession ? ' is-live' : ' is-idle'}`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={PANEL_TRANSITION}
            >
              <div className="scene-canvas-header">
                <div className="scene-canvas-head">
                  <p className="eyebrow">{'主舞台'}</p>
                  <span className="scene-canvas-caption">{hasSession ? 'Proscenium frame live' : 'Curtain closed'}</span>
                </div>
                <span className="scene-canvas-status">{stageStatusLabel}</span>
              </div>

              <div className={`scene-canvas-screen${hasSession ? ' is-live' : ' is-idle'}`}>
                <div className="scene-canvas-overlay" />
                <div className="scene-canvas-grid" />
                <div className="scene-canvas-proscenium scene-canvas-proscenium--left" />
                <div className="scene-canvas-proscenium scene-canvas-proscenium--right" />
                <div className="scene-canvas-rigging" />
                <div className="scene-canvas-haze" />
                <div className="scene-canvas-floor" />
                <div className="scene-canvas-safezone" />
                <div className="scene-canvas-body">
                  <span className="scene-canvas-kicker">{activeScene?.timeBlock || '等待第一幕'}</span>
                  <h2 className="scene-canvas-headline">{renderWindowHeadline}</h2>
                  <p className="scene-canvas-copy">{renderWindowBody}</p>
                </div>
              </div>

              <div className="scene-canvas-footer">
                <div className="scene-canvas-cues">
                  {stageCueItems.map((item) => (
                    <span className="scene-canvas-cue" key={item}>
                      {item}
                    </span>
                  ))}
                </div>
                <div className="scene-canvas-note">
                  <span className="preview-label">{'导演提示'}</span>
                  <p>{renderWindowCue}</p>
                </div>
              </div>
            </motion.section>
          </section>
        )}

        <AnimatePresence mode="wait" initial={false}>
          {showBootstrapSkeleton ? (
            <motion.section
              key="feature-skeleton"
              className="feature-band feature-band--skeleton"
              aria-hidden="true"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
            >
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
            </motion.section>
          ) : (
            <motion.section
              key="focus-note"
              className="focus-note"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={PANEL_TRANSITION}
            >
              <span className="focus-note-badge">{showFeatureBand ? '情报抽屉已展开' : '主体视图'}</span>
              <p>
                {showFeatureBand
                  ? '情报已经切到独立抽屉里，主舞台和剧情流会保持在原位。'
                  : '当前只保留主舞台、剧情流与底部导演台。设定和关系可以在需要时从边缘呼出。'}
              </p>
            </motion.section>
          )}
        </AnimatePresence>

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
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="dialogue-container"
              transition={PANEL_TRANSITION}
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

      </main>

      <AnimatePresence initial={false}>
        {showFeatureBand && !showBootstrapSkeleton ? (
          <motion.section
            className="workspace-drawer workspace-drawer--feature"
            initial={{ opacity: 0, y: 28 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 24 }}
            transition={DRAWER_TRANSITION}
          >
            <div className="drawer-chrome">
              <div className="drawer-chrome-copy">
                <span className="drawer-label">{'情报抽屉'}</span>
                <strong>{'本回合聚焦与世界预览'}</strong>
              </div>
              <div className="drawer-actions">
                <button className="ghost-button drawer-action" onClick={() => setShowFeatureBand(false)} type="button">
                  {'收起'}
                </button>
                <button
                  aria-label="关闭情报抽屉"
                  className="ghost-button drawer-close"
                  onClick={() => setShowFeatureBand(false)}
                  type="button"
                >
                  <X size={16} />
                </button>
              </div>
            </div>

            <div className="feature-drawer-content">
              <TurnSpotlight result={lastTurnResult} debug={lastTurnDebug} hasSession={hasSession} />
              <WorldbookPreview
                worldbook={selectedWorldbook}
                characters={worldbookCharacters}
                selected={Boolean(selectedWorldbookId)}
                onOpenSeedImport={() => setSeedImportOpen(true)}
              />
            </div>
          </motion.section>
        ) : null}
      </AnimatePresence>

      <form
        ref={composerFormRef}
        className={composerClassName}
        onSubmit={handleSubmit}
        onFocusCapture={handleComposerFocusCapture}
        onBlurCapture={handleComposerBlurCapture}
      >
        <div className={composerInnerClassName}>
          <div className="composer-header">
            <div className="composer-heading">
              <label className="composer-label" htmlFor="turn-input">
                <Ghost size={14} />
                {'玩家输入'}
              </label>
              <span className={`composer-state-badge composer-state-badge--${composerState}`}>{composerStatePill}</span>
            </div>
            <div className="composer-hint">
              {hasSession ? (
                <span className="fade-in">
                  <Zap size={12} />
                  {`${lastTurnDebug?.selectedMemorySummaries.length ?? 0} 条记忆参与中`}
                </span>
              ) : (
                composerStatusCopy
              )}
            </div>
          </div>

          <textarea
            id="turn-input"
            ref={composerRef}
            value={composerValue}
            onChange={(event) => setComposerValue(event.target.value)}
            onCompositionStart={() => {
              isComposingRef.current = true;
            }}
            onCompositionEnd={() => {
              isComposingRef.current = false;
            }}
            onKeyDown={handleComposerKeyDown}
            placeholder={composerPlaceholder}
            rows={2}
            disabled={!canSendTurn || submittingTurn}
          />

          <div className="composer-actions">
            <div className="composer-shortcut-group">
              <span className="composer-context">{composerStatusCopy}</span>
              <span className="composer-shortcut">{'Ctrl/Cmd + Enter'}</span>
            </div>
            <button
              type="submit"
              className="send-button"
              disabled={!canSendTurn || submittingTurn || !composerValue.trim()}
            >
              {submittingTurn ? (
                <span className="loading-text">{'导演回应中...'}</span>
              ) : (
                <>
                  {'发送回合'}
                  <Send size={16} />
                </>
              )}
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

      <AnimatePresence>
        {seedImportSuccessMessage ? (
          <motion.div
            className="success-banner"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 12 }}
          >
            <CheckCircle2 size={16} /> {seedImportSuccessMessage}
          </motion.div>
        ) : null}
      </AnimatePresence>

      {rightDrawerPinned ? (
        <aside className="workspace-pinned workspace-pinned--right">
          <div className="drawer-chrome drawer-chrome--pinned">
            <div className="drawer-chrome-copy">
              <span className="drawer-label">{'关系面板'}</span>
              <strong>{'场景位移与关系态势'}</strong>
            </div>
            <div className="drawer-actions">
              <button className="ghost-button drawer-action" onClick={() => collapseDrawer('right')} type="button">
                {'收缩'}
              </button>
              <button className="ghost-button drawer-action" onClick={() => togglePinnedDrawer('right')} type="button">
                <PinOff size={14} />
                {'浮动'}
              </button>
            </div>
          </div>
          <SceneInspector scene={activeScene} session={activeSession} actorNames={actorNames} lastTurnResult={lastTurnResult} />
        </aside>
      ) : null}

      <AnimatePresence initial={false}>
        {rightDrawerState === 'expanded' ? (
          <motion.div
            className="workspace-drawer workspace-drawer--right"
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 48 }}
            transition={DRAWER_TRANSITION}
          >
            <div className="drawer-chrome">
              <div className="drawer-chrome-copy">
                <span className="drawer-label">{'关系面板'}</span>
                <strong>{'场景位移与关系态势'}</strong>
              </div>
              <div className="drawer-actions">
                <button className="ghost-button drawer-action" onClick={() => collapseDrawer('right')} type="button">
                  {'收缩'}
                </button>
                <button className="ghost-button drawer-action" onClick={() => togglePinnedDrawer('right')} type="button">
                  <Pin size={14} />
                  {canPinDrawers ? '固定' : '停靠'}
                </button>
                <button
                  aria-label="关闭关系面板"
                  className="ghost-button drawer-close"
                  onClick={() => closeDrawer('right')}
                  type="button"
                >
                  <X size={16} />
                </button>
              </div>
            </div>

            <SceneInspector scene={activeScene} session={activeSession} actorNames={actorNames} lastTurnResult={lastTurnResult} />
          </motion.div>
        ) : null}
      </AnimatePresence>

      {rightDrawerState === 'collapsed' ? (
        <button className="drawer-edge-tab drawer-edge-tab--right" onClick={() => openDrawer('right')} type="button">
          <span>{'关系'}</span>
        </button>
      ) : null}

      <SessionComposerModal
        open={sessionComposerOpen}
        worldbook={selectedWorldbook}
        characters={worldbookCharacters}
        existingSessionCount={scopedSessions.length}
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
            setErrorMessage('');
            const response = await createSession({
              worldbookId: selectedWorldbookId,
              characterIds: draftCharacterIds,
              title: `${selectedWorldbook?.title || '新会话'} · 夜${scopedSessions.length + 1}`,
              openingLocationId: draftLocationId,
            });
            applyLoadedSession(response.session, response.scene);
            setSessionComposerOpen(false);
            const list = await listSessions();
            setSessions(list.items);
            setSeedImportSuccessMessage(`第一幕已点亮：${response.session.title}`);
          } finally {
            setCreatingSession(false);
          }
        }}
      />

      <SeedImportModal
        open={seedImportOpen}
        importing={importingSeed}
        worldbookDraft={worldbookDraft}
        characterDraft={characterDraft}
        starterPacks={starterPacks}
        selectedStarterPackId={selectedStarterPackId}
        preflight={seedImportPreflight}
        onClose={() => setSeedImportOpen(false)}
        onChangeWorldbookDraft={setWorldbookDraft}
        onChangeCharacterDraft={setCharacterDraft}
        onLoadStarterKit={() => loadStarterPack(selectedStarterPackId)}
        onSelectStarterPack={loadStarterPack}
        onImport={handleImportSeed}
      />
    </div>
  );
}
