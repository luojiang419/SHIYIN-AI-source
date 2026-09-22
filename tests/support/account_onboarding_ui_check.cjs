const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { chromium } = require('playwright');

(async () => {
  const out = path.resolve('.codex-tmp/account-setup');
  fs.mkdirSync(out, { recursive: true });
  const data = fs.mkdtempSync(path.join(out, 'ui-data-'));
  const port = 39763;
  const origin = `http://127.0.0.1:${port}`;
  const stage = process.env.SHIYIN_UI_STAGE && path.resolve(process.env.SHIYIN_UI_STAGE);
  const executable = stage ? path.join(stage, 'app/backend/canvas-backend/canvas-backend.exe') : 'python';
  const args = stage ? ['--data-dir', data, '--app-root', path.join(stage, 'app'), '--portable-root', stage, '--host', '127.0.0.1', '--port', String(port), '--runtime-mode', 'desktop', '--parent-pid', String(process.pid)] : ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', String(port)];
  const backend = spawn(executable, args, {
    cwd: process.cwd(), windowsHide: true,
    env: { ...process.env, CANVAS_DATA_DIR: data, CANVAS_RUNTIME_MODE: 'desktop', CANVAS_PORT: String(port), CANVAS_DWPOSE_AUTO_DOWNLOAD: '0' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let logs = '';
  backend.stdout.on('data', chunk => logs += chunk.toString());
  backend.stderr.on('data', chunk => logs += chunk.toString());
  let browser;
  try {
    for (let attempt = 0; attempt < 120; attempt++) {
      if (backend.exitCode !== null) throw new Error(logs);
      if (await fetch(`${origin}/api/health`).then(r => r.ok).catch(() => false)) break;
      await new Promise(resolve => setTimeout(resolve, 250));
    }
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: 'dark' });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${origin}/login`);
    await page.getByRole('button', { name: '创建管理员并继续' }).waitFor();
    await page.screenshot({ path: path.join(out, 'account-dark.png'), fullPage: true });
    await page.emulateMedia({ colorScheme: 'light' });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(out, 'account-mobile.png'), fullPage: true });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.locator('#account').fill('界面管理员');
    await page.locator('#password').fill('测试密码123');
    await page.locator('#confirmPassword').fill('不同密码');
    await page.locator('#submit').click();
    await page.getByText('两次输入的密码不一致').waitFor();
    await page.locator('#confirmPassword').fill('测试密码123');
    await page.locator('#submit').click();
    await page.waitForURL(`${origin}/`);
    assert((await (await context.request.get(`${origin}/api/account/me`)).json()).account.is_admin);
    await page.locator('#shiying-api-key-modal:not([hidden])').waitFor();
    if (stage) {
      const assistant = await (await context.request.get(`${origin}/api/onboarding/ai-assistant`)).json();
      assert.notEqual(assistant.status, 'configured');
      const providers = await (await context.request.get(`${origin}/api/providers`)).json();
      assert.deepEqual(providers.providers.filter(provider => provider.has_key).map(provider => provider.id), []);
      await page.locator('#startupAssistantStep').waitFor({ state: 'visible' });
    }
    await page.locator('#studio-boot-screen').waitFor({ state: 'hidden' });
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.screenshot({ path: path.join(out, 'after-account-guide.png'), fullPage: true });
    await context.clearCookies();
    await page.goto(`${origin}/api/auth/bootstrap`);
    assert.equal(new URL(page.url()).pathname, '/');
    assert((await (await context.request.get(`${origin}/api/account/me`)).json()).account.is_admin);
    await context.request.post(`${origin}/api/account/logout`);
    await page.goto(`${origin}/api/auth/bootstrap`);
    assert.equal(new URL(page.url()).pathname, '/login');
    await page.getByRole('button', { name: '登录并进入' }).waitFor();
    await page.getByRole('button', { name: '注册账号', exact: true }).click();
    await page.locator('#account').fill('界面普通用户');
    await page.locator('#password').fill('普通密码');
    await page.locator('#confirmPassword').fill('普通密码');
    await page.locator('#submit').click();
    await page.waitForURL(`${origin}/`);
    assert.equal((await (await context.request.get(`${origin}/api/account/me`)).json()).account.is_admin, false);
    assert.equal((await context.request.get(`${origin}/api/providers`)).status(), 403);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ ok: true, screenshots: out, checks: ['首次管理员注册', '确认密码', '深色/窄屏布局', '进入 API 引导', 'Cookie 丢失恢复', '退出撤销', '普通用户注册及权限'] }));
  } finally {
    if (browser) await browser.close();
    backend.kill();
    fs.writeFileSync(path.join(out, 'ui-backend.log'), logs);
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
