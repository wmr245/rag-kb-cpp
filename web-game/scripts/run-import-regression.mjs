import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const DEFAULT_URLS = ['http://127.0.0.1:5173', 'http://127.0.0.1:5174'];
const OUTPUT_DIR = process.env.WEB_GAME_REGRESSION_DIR || path.resolve('output/import-regression');

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

async function main() {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const baseUrl = await resolveBaseUrl();
  const consoleErrors = [];

  const browser = await chromium.launch({
    headless: true,
    args: ['--use-gl=angle', '--use-angle=swiftshader'],
  });

  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push({ type: 'console.error', text: msg.text() });
    }
  });
  page.on('pageerror', (error) => {
    consoleErrors.push({ type: 'pageerror', text: String(error) });
  });

  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(700);

  await page.getByRole('button', { name: /展开设定|收起设定/ }).first().click();
  await page.waitForTimeout(450);

  const openImportButton = page.getByRole('button', { name: /导入设定|再导入一套设定|导入第一套设定/ }).first();
  await openImportButton.click();

  await page.getByText('设定导入').waitFor({ state: 'visible' });
  await page.getByText('导入前预检').waitFor({ state: 'visible' });

  const statusLabel = await page.locator('.seed-import-preflight-copy strong').first().innerText();
  const canImport = await page.getByRole('button', { name: /导入设定并刷新舞台|先修复预检问题/ }).first().isEnabled();
  const issueTexts = await page.locator('.seed-import-issue').evaluateAll((nodes) =>
    nodes.map((node) => node.textContent?.trim() || '').filter(Boolean),
  );

  await page.screenshot({
    path: path.join(OUTPUT_DIR, 'seed-import-modal.png'),
    fullPage: true,
  });

  fs.writeFileSync(
    path.join(OUTPUT_DIR, 'summary.json'),
    JSON.stringify(
      {
        baseUrl,
        statusLabel,
        canImport,
        issueCount: issueTexts.length,
        issues: issueTexts,
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
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
