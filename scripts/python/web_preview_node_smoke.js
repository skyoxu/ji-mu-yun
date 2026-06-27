const { chromium } = require('playwright');

function parseArgs(argv) {
  const args = {
    url: '',
    timeoutMs: 60000,
    settleMs: 15000,
    expectText: [],
    afterClickExpectText: [],
    clickCanvas: false,
    allowConsoleErrors: false,
    mobileCheck: false,
    expectPreviewId: '',
    expectPackageFile: '',
    expectPackageSha256: ''
  };
  for (let index = 2; index < argv.length; index += 1) {
    const value = argv[index];
    if (!args.url && !value.startsWith('--')) {
      args.url = value;
    } else if (value === '--click-canvas') {
      args.clickCanvas = true;
    } else if (value === '--allow-console-errors') {
      args.allowConsoleErrors = true;
    } else if (value === '--mobile-check') {
      args.mobileCheck = true;
    } else if (value === '--timeout-ms') {
      args.timeoutMs = Number(argv[++index] || args.timeoutMs);
    } else if (value.startsWith('--timeout-ms=')) {
      args.timeoutMs = Number(value.slice('--timeout-ms='.length));
    } else if (value === '--settle-ms') {
      args.settleMs = Number(argv[++index] || args.settleMs);
    } else if (value.startsWith('--settle-ms=')) {
      args.settleMs = Number(value.slice('--settle-ms='.length));
    } else if (value === '--expect-text') {
      args.expectText.push(argv[++index] || '');
    } else if (value.startsWith('--expect-text=')) {
      args.expectText.push(value.slice('--expect-text='.length));
    } else if (value === '--after-click-expect-text') {
      args.afterClickExpectText.push(argv[++index] || '');
    } else if (value.startsWith('--after-click-expect-text=')) {
      args.afterClickExpectText.push(value.slice('--after-click-expect-text='.length));
    } else if (value === '--expect-preview-id') {
      args.expectPreviewId = argv[++index] || '';
    } else if (value.startsWith('--expect-preview-id=')) {
      args.expectPreviewId = value.slice('--expect-preview-id='.length);
    } else if (value === '--expect-package-file') {
      args.expectPackageFile = argv[++index] || '';
    } else if (value.startsWith('--expect-package-file=')) {
      args.expectPackageFile = value.slice('--expect-package-file='.length);
    } else if (value === '--expect-package-sha256') {
      args.expectPackageSha256 = argv[++index] || '';
    } else if (value.startsWith('--expect-package-sha256=')) {
      args.expectPackageSha256 = value.slice('--expect-package-sha256='.length);
    }
  }
  return args;
}

async function waitForLoadedPreview(page, viewport, timeoutMs) {
  await page.waitForFunction(
    ({ width, height }) => {
      const canvas = document.querySelector('canvas');
      if (!canvas) return false;
      const loading = document.querySelector('#phasea-loading-estimate');
      const loadingHidden = !loading ||
        loading.style.display === 'none' ||
        loading.style.visibility === 'hidden' ||
        !loading.textContent ||
        loading.offsetParent === null;
      const canvasSized = canvas.clientWidth >= Math.floor(width * 0.75) &&
        canvas.clientHeight >= Math.floor(height * 0.5);
      return loadingHidden && canvasSized;
    },
    viewport,
    { timeout: timeoutMs }
  ).catch(() => {});
}

function isSha256(value) {
  return typeof value === 'string' && /^[0-9a-f]{64}$/i.test(value);
}

function previewContractGuideCoherent(contract) {
  if (!contract.game_type_guide) return true;
  return typeof contract.game_type_id === 'string' &&
    contract.game_type_id.length > 0 &&
    typeof contract.game_type_guide === 'string' &&
    contract.game_type_guide.startsWith('docs/game-type-guides/') &&
    contract.game_type_guide.endsWith('.md');
}

function previewIdFromUrl(url) {
  const parts = new URL(url).pathname.split('/').filter(Boolean).map((part) => decodeURIComponent(part));
  const index = parts.indexOf('web-previews');
  return index >= 0 && index + 1 < parts.length ? parts[index + 1] : '';
}

async function fetchPreviewContract(page) {
  return await page.evaluate(async () => {
    const url = new URL('preview-contract.json', window.location.href).href;
    try {
      const response = await fetch(url, { cache: 'no-store' });
      const contentType = response.headers.get('content-type') || '';
      const text = await response.text();
      let body = null;
      try { body = text ? JSON.parse(text) : null; } catch {}
      return { url, status: response.status, contentType, body, text };
    } catch (error) {
      return { url, status: 0, contentType: '', body: null, text: String(error) };
    }
  });
}

async function check(args, label, viewport) {
  const failures = [];
  const assets = [];
  const consoleMessages = [];
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport });
  page.on('console', (msg) => consoleMessages.push({ type: msg.type(), text: msg.text() }));
  page.on('pageerror', (error) => failures.push({ type: 'pageerror', text: String(error) }));
  page.on('requestfailed', (request) => failures.push({
    type: 'requestfailed',
    url: request.url(),
    failure: request.failure()?.errorText || ''
  }));
  page.on('response', (response) => {
    const responseUrl = response.url();
    if (['index.js', 'index.wasm', 'index.pck', 'worker', 'worklet'].some((token) => responseUrl.includes(token))) {
      assets.push({ url: responseUrl, status: response.status(), cache: response.headers()['cache-control'] || '' });
    }
  });

  await page.goto(args.url, { waitUntil: 'domcontentloaded', timeout: args.timeoutMs });
  await page.waitForSelector('canvas', { timeout: args.timeoutMs });
  await page.waitForTimeout(args.settleMs);
  await waitForLoadedPreview(page, viewport, args.timeoutMs);
  const previewContract = await fetchPreviewContract(page);
  const beforeClickText = await page.locator('body').innerText({ timeout: args.timeoutMs });
  const canvasBox = await page.locator('canvas').boundingBox({ timeout: args.timeoutMs });
  if (args.clickCanvas && canvasBox) {
    await page.mouse.click(canvasBox.x + canvasBox.width / 2, canvasBox.y + canvasBox.height / 2);
    await page.waitForTimeout(1000);
  }
  const afterClickText = await page.locator('body').innerText({ timeout: args.timeoutMs });
  const result = await page.evaluate(() => {
    const canvas = document.querySelector('canvas');
    const gl = canvas && (
      canvas.getContext('webgl') ||
      canvas.getContext('experimental-webgl') ||
      canvas.getContext('webgl2')
    );
    const loading = document.querySelector('#phasea-loading-estimate');
    let dataUrlLength = 0;
    try {
      dataUrlLength = canvas ? canvas.toDataURL('image/png').length : 0;
    } catch {
      dataUrlLength = -1;
    }
    let localStorageReadable = true;
    try { window.localStorage.getItem('phaseAAccessToken'); } catch { localStorageReadable = false; }
    return {
      title: document.title,
      canvas: canvas ? {
        width: canvas.width,
        height: canvas.height,
        clientWidth: canvas.clientWidth,
        clientHeight: canvas.clientHeight,
        dataUrlLength
      } : null,
      webgl: !!gl,
      loadingText: loading?.textContent || '',
      loadingDisplay: loading?.style.display || '',
      loadingVisible: !!loading && loading.style.display !== 'none' && loading.offsetParent !== null,
      localStorageReadable,
      bodyText: document.body?.innerText || ''
    };
  });
  await browser.close();

  const missingAssets = ['index.js', 'index.wasm', 'index.pck']
    .filter((name) => !assets.some((item) => item.url.includes(name) && item.status === 200));
  const canvas = result.canvas || {};
  const contractBody = previewContract.body || {};
  const urlPreviewId = previewIdFromUrl(args.url);
  const checks = {
    hasCanvas: !!result.canvas,
    canvasHasClientSize: (canvas.clientWidth || 0) > 0 && (canvas.clientHeight || 0) > 0,
    canvasHasLoadedSize: (canvas.clientWidth || 0) >= Math.floor(viewport.width * 0.75) &&
      (canvas.clientHeight || 0) >= Math.floor(viewport.height * 0.5),
    canvasSnapshotReadable: (canvas.dataUrlLength || 0) > 100,
    hasWebGl: !!result.webgl,
    loadingComplete: !result.loadingVisible,
    noRequestFailures: failures.length === 0,
    requiredAssetsLoaded: missingAssets.length === 0,
    localStorageBlocked: result.localStorageReadable === false,
    expectedTextPresent: args.expectText.every((text) => result.bodyText.includes(text)),
    afterClickExpectedTextPresent: args.afterClickExpectText.every((text) => afterClickText.includes(text)),
    noConsoleErrors: args.allowConsoleErrors || !consoleMessages.some((item) => item.type === 'error'),
    previewContractLoaded: previewContract.status === 200,
    previewContractSchema: contractBody.schema_version === 'phasea-web-preview-contract-v1',
    previewContractPackagePresent: !!contractBody.package_file,
    previewContractPackageShaPresent: isSha256(contractBody.package_sha256),
    previewContractModePresent: !!contractBody.mode,
    previewContractGuideCoherent: previewContractGuideCoherent(contractBody),
    previewContractPreviewIdMatchesUrl: !!urlPreviewId && contractBody.preview_id === urlPreviewId,
    previewContractExpectedPreviewId: !args.expectPreviewId || contractBody.preview_id === args.expectPreviewId,
    previewContractExpectedPackageFile: !args.expectPackageFile || contractBody.package_file === args.expectPackageFile,
    previewContractExpectedPackageSha256: !args.expectPackageSha256 || contractBody.package_sha256 === args.expectPackageSha256.toLowerCase()
  };
  return { label, ok: Object.values(checks).every(Boolean), checks, missingAssets, result, previewContract, beforeClickText, afterClickText, failures, assets, consoleTail: consoleMessages.slice(-20) };
}

(async () => {
  const args = parseArgs(process.argv);
  if (!args.url) {
    console.error(JSON.stringify({ ok: false, error: 'url_required' }, null, 2));
    process.exit(2);
  }
  const checks = [await check(args, 'desktop', { width: 1280, height: 720 })];
  if (args.mobileCheck) {
    checks.push(await check(args, 'mobile', { width: 390, height: 844 }));
  }
  const output = { ok: checks.every((item) => item.ok), checks };
  console.log(JSON.stringify(output, null, 2));
  process.exit(output.ok ? 0 : 1);
})().catch((error) => {
  console.error(JSON.stringify({ ok: false, error: String(error), stack: error.stack }, null, 2));
  process.exit(1);
});
