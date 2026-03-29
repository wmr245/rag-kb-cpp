import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const DEFAULT_URLS = ['http://127.0.0.1:5173', 'http://127.0.0.1:5174', 'http://127.0.0.1:5175'];
const OUTPUT_DIR = process.env.WEB_GAME_REGRESSION_DIR || path.resolve('output/assistant-workspace-regression');
const FIXTURE_WORLD_ID = 'campus_romance_01';
const FIXTURE_CHARACTER_ID = 'assistant_regression_anchor';
const FIXTURE_ASSISTANT_ID = `assistant:${FIXTURE_CHARACTER_ID}`;
const FIXTURE_NAME = 'Assistant Regression Anchor';
const FIXTURE_USER_SCOPE = 'default_player';

function buildFixtureWorldbook() {
  return {
    id: FIXTURE_WORLD_ID,
    version: '1.0.0',
    title: '校园暧昧',
    genre: ['romance', 'slice_of_life'],
    tone: ['gentle', 'quiet'],
    era: 'modern',
    locale: 'campus_library',
    author: 'assistant-regression',
    tags: ['assistant', 'regression'],
    worldRules: ['故事发生在安静校园场景内。'],
    hardConstraints: ['未解锁秘密不会被主动透露。'],
    socialNorms: ['私人场景中的对话更容易沉淀长期记忆。'],
    narrativeBoundaries: ['不进入战斗和政治阴谋线。'],
    factions: [],
    locations: [
      {
        id: 'library',
        name: '图书馆',
        description: '安静、适合长期对话与回忆召回。',
        tags: ['quiet', 'memory'],
        sceneHints: ['rain', 'after_school'],
      },
      {
        id: 'rooftop',
        name: '天台',
        description: '适合风声与迟疑感更强的回应。',
        tags: ['wind', 'emotion'],
        sceneHints: ['sunset', 'confession'],
      },
    ],
    eventSeeds: ['雨天借伞', '失踪的情书', '黄昏天台的误会'],
    defaultScenePatterns: ['慢节奏陪伴式对话'],
    mapAssets: [],
  };
}

function buildFixtureCharacter() {
  return {
    id: FIXTURE_CHARACTER_ID,
    worldbookId: FIXTURE_WORLD_ID,
    name: FIXTURE_NAME,
    role: 'memory_companion',
    tags: ['quiet', 'observant'],
    appearanceHints: ['抱着书', '说话很轻'],
    personaTags: ['quiet', 'observant', 'gentle'],
    coreTraits: ['细腻', '克制', '耐心'],
    emotionalStyle: 'slow_warmup',
    socialStyle: 'private_over_public',
    innerConflict: '想靠近，但不想让回应太冒进。',
    speechStyle: {
      tone: 'soft',
      verbosity: 'short',
      habitPhrases: [],
      avoidPhrases: ['激烈否定'],
      cadenceHints: ['先观察再回答', '偶尔带一点留白'],
    },
    likes: ['雨声', '旧书', '守约'],
    dislikes: ['被逼问', '失约'],
    softSpots: ['温和安抚', '被认真记住'],
    tabooTopics: ['公开施压'],
    publicFacts: ['经常待在图书馆', '擅长听别人慢慢说完'],
    privateFacts: ['会偷偷记住那些被认真说出口的话'],
    unlockableSecrets: [
      {
        id: 'assistant_regression_anchor_secret',
        summary: '她其实很在意被人记住和回想起。',
        unlockCondition: 'trust_ge_20',
      },
    ],
    knowledgeBoundaries: ['不主动透露未解锁秘密'],
    scenePreferences: ['library', 'rooftop'],
    eventHooks: ['雨天借伞', '黄昏天台的误会'],
    entryConditions: ['after_school'],
    exitConditions: ['public_pressure'],
    safetyRules: ['never reveal privateFacts before unlock'],
    behaviorConstraints: ['不会在低信任阶段直接表露依赖'],
    disclosureRules: ['only reveal unlockableSecrets when unlockCondition is met'],
    relationshipDefaults: {
      trust: 10,
      affection: 5,
      tension: 0,
      familiarity: 1,
      stage: 'stranger',
    },
  };
}

async function resolveBaseUrl() {
  const explicitUrl = process.env.WEB_GAME_URL;
  const candidates = explicitUrl ? [explicitUrl] : DEFAULT_URLS;

  for (const candidate of candidates) {
    try {
      const response = await fetch(candidate, { method: 'GET' });
      if (response.ok) return candidate;
    } catch {
      continue;
    }
  }

  throw new Error(`No reachable web-game URL found. Tried: ${candidates.join(', ')}`);
}

async function request(baseUrl, pathname, init = {}) {
  return fetch(`${baseUrl}${pathname}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers || {}),
    },
  });
}

async function requestJson(baseUrl, pathname, init = {}) {
  const response = await request(baseUrl, pathname, init);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.json();
}

async function requestJsonOrNull(baseUrl, pathname, init = {}) {
  const response = await request(baseUrl, pathname, init);
  if (response.status === 404) return null;
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.json();
}

async function openLeftRail(page) {
  const assistantList = page.getByTestId('assistant-list').first();
  if (await assistantList.isVisible().catch(() => false)) return;
  await dismissDrawerScrim(page);
  const toggle = page.getByTestId('toggle-left-drawer').first();
  if (await toggle.isVisible().catch(() => false)) {
    await toggle.click({ force: true });
  } else {
    await page.getByTestId('left-drawer-edge').first().click({ force: true });
  }

  try {
    await assistantList.waitFor({ state: 'visible', timeout: 3000 });
  } catch {
    await page.getByTestId('left-drawer-edge').first().click({ force: true });
    await assistantList.waitFor({ state: 'visible' });
  }
  await page.waitForTimeout(250);
}

async function openRightDrawer(page) {
  const drawer = page.getByTestId('right-drawer').first();
  if (await drawer.isVisible().catch(() => false)) return;
  await dismissDrawerScrim(page);
  await page.getByTestId('toggle-right-drawer').first().click({ force: true });
  await drawer.waitFor({ state: 'visible' });
  await page.waitForTimeout(250);
}

async function dismissDrawerScrim(page) {
  const scrim = page.locator('.drawer-scrim').first();
  if (!(await scrim.isVisible().catch(() => false))) return;
  await scrim.click({ force: true });
  await page.waitForTimeout(250);
}

async function ensureDemoWorldbook(baseUrl) {
  const worldbook = await requestJsonOrNull(baseUrl, `/game/worldbooks/${FIXTURE_WORLD_ID}`);
  if (worldbook) {
    return false;
  }

  await requestJson(baseUrl, '/game/worldbooks', {
    method: 'POST',
    body: JSON.stringify({ worldbook: buildFixtureWorldbook() }),
  });
  return true;
}

async function ensureFixtureCharacter(baseUrl) {
  const existing = await requestJsonOrNull(baseUrl, `/game/character-cards/${FIXTURE_CHARACTER_ID}`);
  if (existing) {
    return false;
  }

  await requestJson(baseUrl, '/game/character-cards', {
    method: 'POST',
    body: JSON.stringify({ characterCard: buildFixtureCharacter() }),
  });
  return true;
}

async function ensureFixtureAssistant(baseUrl) {
  const assistants = await requestJson(baseUrl, '/game/assistants');
  if (assistants.items?.some((assistant) => assistant.id === FIXTURE_ASSISTANT_ID && assistant.source === 'assistant')) {
    return false;
  }

  await requestJson(baseUrl, '/game/assistants', {
    method: 'POST',
    body: JSON.stringify({
      name: FIXTURE_NAME,
      worldbookId: FIXTURE_WORLD_ID,
      characterId: FIXTURE_CHARACTER_ID,
      userScope: FIXTURE_USER_SCOPE,
      summary: 'Regression-only assistant fixture for end-to-end testing.',
    }),
  });
  return true;
}

async function resetFixture(baseUrl, purgeLegacyGeneratedData = false) {
  return requestJson(baseUrl, '/game/testing/reset-assistant-fixture', {
    method: 'POST',
    body: JSON.stringify({
      assistantId: FIXTURE_ASSISTANT_ID,
      characterId: FIXTURE_CHARACTER_ID,
      purgeLegacyGeneratedData,
    }),
  });
}

async function selectFixtureAssistant(page) {
  await openLeftRail(page);
  const row = page.getByTestId(`assistant-row-${FIXTURE_ASSISTANT_ID}`).first();
  await row.waitFor({ state: 'visible' });
  const selectButton = page.getByTestId(`assistant-select-${FIXTURE_ASSISTANT_ID}`).first();
  await selectButton.click();
  await page.waitForTimeout(250);
  return (await selectButton.locator('strong').first().innerText()).trim();
}

async function createConversationSegment(page) {
  await openLeftRail(page);
  await page.getByTestId('open-session-composer').click();
  await page.getByTestId('session-composer-modal').waitFor({ state: 'visible' });

  const activeLocation = page.locator('.location-option.is-active').first();
  if ((await activeLocation.count()) === 0) {
    await page.locator('.location-option').first().click();
  }

  const activeCast = page.locator('.cast-option.is-active');
  if ((await activeCast.count()) === 0) {
    await page.locator('.cast-option').first().click();
  }

  await page.getByTestId('confirm-session-composer').click();
  await page.getByTestId('assistant-message-input').waitFor({ state: 'visible' });
  await page.waitForTimeout(700);
}

async function sendMessageAndWait(page, message) {
  await page.getByTestId('assistant-message-input').fill(message);
  await page.getByTestId('assistant-send-button').click();
  await page.waitForFunction(() => document.querySelectorAll('.dialogue-line--speech').length >= 2);
  await page.waitForTimeout(900);
}

async function archiveActiveSession(page) {
  await openLeftRail(page);
  const activeTitle = await page.locator('.session-row.is-active strong').first().innerText();
  await page.locator('[data-testid^="session-archive-"]').first().click();
  await page.waitForFunction(() => {
    const successBanner = document.querySelector('.success-banner');
    if (successBanner?.textContent?.includes('已归档：')) return true;
    return Boolean(document.querySelector('[data-testid="archived-snapshot-group"]'));
  });
  await page.waitForTimeout(500);
  return activeTitle;
}

async function main() {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const baseUrl = await resolveBaseUrl();
  const consoleErrors = [];

  const importedSeed = await ensureDemoWorldbook(baseUrl);
  const createdFixtureCharacter = await ensureFixtureCharacter(baseUrl);
  const createdFixtureAssistant = await ensureFixtureAssistant(baseUrl);
  const resetResult = await resetFixture(baseUrl, false);

  const browser = await chromium.launch({
    headless: true,
    args: ['--use-gl=angle', '--use-angle=swiftshader'],
  });

  const page = await browser.newPage({ viewport: { width: 1280, height: 1180 } });
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push({ type: 'console.error', text: msg.text() });
    }
  });
  page.on('pageerror', (error) => {
    consoleErrors.push({ type: 'pageerror', text: String(error) });
  });

  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1000);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(900);

  const assistantName = await selectFixtureAssistant(page);

  await createConversationSegment(page);
  const createdFirstSession = true;
  await sendMessageAndWait(page, '今天的雨声让人有点想把话慢慢说完。');
  const renderedNarration = (await page.locator('.dialogue-line--narration').count()) > 0;

  await openRightDrawer(page);
  await page.getByTestId('long-memory-block').waitFor({ state: 'visible' });
  const longMemoryVisibleAfterFirstTurn = await page.getByTestId('long-memory-block').isVisible();

  const archivedFirstSessionTitle = await archiveActiveSession(page);
  await openLeftRail(page);
  const archivedSnapshotVisible = await page.getByTestId('archived-snapshot-group').isVisible().catch(() => false);

  await createConversationSegment(page);
  const createdSecondSession = true;
  await sendMessageAndWait(page, '你还记得刚才那场雨里，我们提到图书馆和慢慢说完的话吗？');

  await openRightDrawer(page);
  const longMemoryEntries = await page.getByTestId('long-memory-block').locator('.memory-entry').count();
  const longMemoryVisibleAfterRecall = longMemoryEntries > 0;

  await page.screenshot({
    path: path.join(OUTPUT_DIR, 'assistant-workspace.png'),
    fullPage: true,
  });

  fs.writeFileSync(
    path.join(OUTPUT_DIR, 'summary.json'),
    JSON.stringify(
      {
        baseUrl,
        importedSeed,
        createdFixtureCharacter,
        createdFixtureAssistant,
        reusedFixture: resetResult.reusedFixture,
        activatedAssistant: assistantName,
        createdFirstSession,
        messageSent: true,
        renderedNarration,
        longMemoryVisibleAfterFirstTurn,
        archivedFirstSession: archivedFirstSessionTitle,
        archivedSnapshotVisible,
        createdSecondSession,
        longMemoryVisibleAfterRecall,
        longMemoryEntryCount: longMemoryEntries,
        resetResult,
        consoleErrors,
      },
      null,
      2,
    ),
  );

  await browser.close();

  if (consoleErrors.length) {
    throw new Error(`Console errors detected during regression: ${consoleErrors.length}`);
  }
  if (!createdFirstSession || !createdSecondSession) {
    throw new Error('Conversation segment creation did not complete.');
  }
  if (!longMemoryVisibleAfterRecall) {
    throw new Error('Expected long-memory entries after recall turn.');
  }
  if (!archivedSnapshotVisible) {
    throw new Error('Expected archived snapshot group to remain visible.');
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
