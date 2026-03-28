import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const DEFAULT_URLS = ['http://127.0.0.1:5173', 'http://127.0.0.1:5174', 'http://127.0.0.1:5175'];
const OUTPUT_DIR = process.env.WEB_GAME_REGRESSION_DIR || path.resolve('output/session-workspace-regression');

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

async function ensureSeedContent(page) {
  const openSettingsButton = page.getByRole('button', { name: /展开设定|收起设定/ }).first();
  await openSettingsButton.click();
  await page.waitForTimeout(500);

  const worldbookButtons = page.locator('.worldbook-pill');
  if ((await worldbookButtons.count()) > 0) return false;

  await page.getByRole('button', { name: '导入设定' }).first().click();
  await page.getByText('设定导入').waitFor({ state: 'visible' });
  await page.getByRole('button', { name: '导入设定并刷新舞台' }).click();
  await page.getByText('导入完成').waitFor({ state: 'visible' });
  return true;
}

async function ensureSessionExists(page) {
  const sessionRows = page.locator('.session-row');
  if ((await sessionRows.count()) > 0) return { created: false };

  const launchButton = page
    .getByRole('button', { name: /现在开场|策划这一夜的开场/ })
    .first();
  await launchButton.click();

  await page.getByText('开场编排').waitFor({ state: 'visible' });

  const selectedLocation = page.locator('.location-option.is-active').first();
  if ((await selectedLocation.count()) === 0) {
    await page.locator('.location-option').first().click();
  }

  const activeCast = page.locator('.cast-option.is-active');
  if ((await activeCast.count()) === 0) {
    await page.locator('.cast-option').first().click();
  }

  await page.getByRole('button', { name: '确认并开始这场夜晚' }).click();
  await page.locator('.session-row').first().waitFor({ state: 'visible' });
  return { created: true };
}

async function getActiveSessionShell(page) {
  let activeShell = page.locator('.session-row-shell', {
    has: page.locator('.session-row.is-active'),
  }).first();

  if ((await activeShell.count()) === 0) {
    const firstSessionRow = page.locator('.session-row').first();
    await firstSessionRow.click();
    await page.waitForTimeout(400);
    activeShell = page.locator('.session-row-shell', {
      has: page.locator('.session-row.is-active'),
    }).first();
  }

  return activeShell;
}

async function main() {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const baseUrl = await resolveBaseUrl();
  const consoleErrors = [];

  const browser = await chromium.launch({
    headless: true,
    args: ['--use-gl=angle', '--use-angle=swiftshader'],
  });

  const page = await browser.newPage({ viewport: { width: 1500, height: 1160 } });
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push({ type: 'console.error', text: msg.text() });
    }
  });
  page.on('pageerror', (error) => {
    consoleErrors.push({ type: 'pageerror', text: String(error) });
  });

  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(900);

  const importedSeed = await ensureSeedContent(page);
  await page.waitForTimeout(700);
  const { created: createdSession } = await ensureSessionExists(page);

  const activeShell = await getActiveSessionShell(page);
  const currentSessionTitle = await activeShell.locator('.session-row strong').first().innerText();
  const renamedTitle = `回归记忆线 ${Date.now().toString().slice(-6)}`;

  await activeShell.getByRole('button', { name: '重命名' }).click();
  await page.locator('.session-rename-input').fill(renamedTitle);
  await page.getByRole('button', { name: '保存' }).click();
  await page.getByText(`已重命名：${renamedTitle}`).waitFor({ state: 'visible' });

  const renamedShell = await getActiveSessionShell(page);
  await renamedShell.getByRole('button', { name: '归档' }).click();
  await page.getByText(`已归档：${renamedTitle}`).waitFor({ state: 'visible' });

  const archivedShell = page.locator('.session-group').filter({ hasText: '已归档记忆线' }).locator('.session-row-shell', {
    has: page.getByText(renamedTitle),
  }).first();
  await archivedShell.getByRole('button', { name: '恢复' }).click();
  await page.getByText(`已恢复：${renamedTitle}`).waitFor({ state: 'visible' });

  const restoredShell = await getActiveSessionShell(page);
  const restoredTitleBeforeReload = await restoredShell.locator('.session-row strong').first().innerText();
  const restoreCardTitle = await page.locator('.session-restore-card strong').first().innerText();
  const initialSessionTag = await page.locator('.session-id-tag').first().innerText();

  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1100);

  const restoredSessionTitle = await page.locator('.session-row.is-active strong').first().innerText();
  const restoredSessionTag = await page.locator('.session-id-tag').first().innerText();

  await page.screenshot({
    path: path.join(OUTPUT_DIR, 'session-workspace.png'),
    fullPage: true,
  });

  fs.writeFileSync(
    path.join(OUTPUT_DIR, 'summary.json'),
    JSON.stringify(
      {
        baseUrl,
        importedSeed,
        createdSession,
        currentSessionTitle,
        renamedTitle,
        restoredTitleBeforeReload,
        restoreCardTitle,
        initialSessionTag,
        restoredSessionTitle,
        restoredSessionTag,
        sessionRestored: renamedTitle === restoredSessionTitle,
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

  if (renamedTitle !== restoredSessionTitle) {
    throw new Error(`Expected restored session "${renamedTitle}" but got "${restoredSessionTitle}"`);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
