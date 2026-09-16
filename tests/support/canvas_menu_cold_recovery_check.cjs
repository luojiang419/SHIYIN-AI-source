const assert = require('node:assert/strict');
const { chromium } = require('playwright');

const base = process.argv[2] || 'http://127.0.0.1:13158';

(async () => {
    const browser = await chromium.launch({ headless: true, channel: 'msedge' });
    try {
        for (const scenario of [
            { active: false, resource: 'html' },
            { active: false, resource: 'script' },
            { active: true, resource: 'html' },
            { active: true, resource: 'script' },
        ]) {
            const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
            const errors = [];
            let attempts = 0;
            page.on('pageerror', error => errors.push(error.message));
            if (scenario.active) await page.addInitScript(() => localStorage.setItem('studio_active_page', 'canvas'));
            await page.route('**/api/account/me', route => route.fulfill({ json: { account: { id: 'fixture', account: 'fixture', is_admin: false } } }));
            const resource = scenario.resource === 'html' ? '**/static/canvas-list.html*' : '**/static/js/canvas-list.js*';
            await page.route(resource, route => {
                attempts += 1;
                if (attempts === 1) return route.fulfill({ status: 503, body: '', contentType: scenario.resource === 'html' ? 'text/html' : 'application/javascript' });
                return route.continue();
            });

            await page.goto(`${base}/static/index.html`);
            if (!scenario.active) {
                await page.waitForFunction(() => document.getElementById('frame-canvas')?.dataset.frameReadyState === 'error');
                await page.locator('.nav-item[onclick*="canvas"]').click();
            }
            await page.waitForFunction(() => {
                const frame = document.getElementById('frame-canvas');
                return frame?.classList.contains('active') && frame.dataset.frameReadyState === 'ready'
                    && typeof frame.contentWindow?.loadAll === 'function' && !frame.contentWindow.canvasListEntryOverlay;
            }, null, { timeout: 15000 });
            assert.equal(attempts, 2, JSON.stringify(scenario));
            assert.deepEqual(errors, [], JSON.stringify(scenario));
            console.log(JSON.stringify({ ...scenario, attempts, recovered: true }));
            await page.close();
        }

        const manualPage = await browser.newPage({ viewport: { width: 1440, height: 900 } });
        let listAttempts = 0;
        await manualPage.addInitScript(() => localStorage.setItem('studio_active_page', 'canvas'));
        await manualPage.route('**/api/account/me', route => route.fulfill({ json: { account: { id: 'fixture', account: 'fixture', is_admin: false } } }));
        await manualPage.route('**/static/canvas-list.html*', route => {
            listAttempts += 1;
            if (listAttempts <= 3) return route.fulfill({ status: 503, body: '', contentType: 'text/html' });
            return route.continue();
        });
        await manualPage.goto(`${base}/static/index.html`);
        await manualPage.waitForFunction(() => {
            const frame = document.getElementById('frame-canvas');
            return frame?.dataset.canvasRetryAttempts === '2' && frame.dataset.frameReadyState === 'error';
        });
        assert.equal(listAttempts, 3);
        await manualPage.locator('.nav-item[onclick*="canvas"]').click();
        await manualPage.waitForFunction(() => document.getElementById('frame-canvas')?.dataset.frameReadyState === 'ready');
        assert.equal(listAttempts, 4);
        console.log(JSON.stringify({ scenario: 'manual-retry-after-limit', attempts: listAttempts, recovered: true }));
        await manualPage.close();

        const warmPage = await browser.newPage({ viewport: { width: 1440, height: 900 } });
        let editorScriptAttempts = 0;
        await warmPage.route('**/api/account/me', route => route.fulfill({ json: { account: { id: 'fixture', account: 'fixture', is_admin: false } } }));
        await warmPage.route('**/api/projects', route => route.fulfill({ json: { projects: [{ id: 'default', name: 'Default', order: 0 }] } }));
        await warmPage.route('**/api/canvases', route => route.fulfill({ json: { canvases: [{ id: 'warm-fallback', title: 'warm-fallback', project: 'default', updated_at: 1 }] } }));
        await warmPage.route('**/static/js/canvas.js*', route => {
            editorScriptAttempts += 1;
            if (editorScriptAttempts === 1) return route.fulfill({ status: 503, body: '', contentType: 'application/javascript' });
            return route.continue();
        });
        await warmPage.goto(`${base}/static/canvas-list.html`);
        await warmPage.waitForFunction(() => [...document.querySelectorAll('iframe[data-canvas-session-resident]')]
            .some(frame => frame.dataset.frameReady === '0' && frame.src.includes('warm=1')));
        await warmPage.locator('.ws-card[data-canvas-id="warm-fallback"]').click();
        await warmPage.waitForFunction(() => [...document.querySelectorAll('iframe[data-canvas-session-resident]')]
            .some(frame => frame.contentWindow?.CanvasSessionLifecycle?.state().id === 'warm-fallback'));
        assert.equal(editorScriptAttempts, 2);
        console.log(JSON.stringify({ scenario: 'warm-editor-fallback', attempts: editorScriptAttempts, recovered: true }));
        await warmPage.close();
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
