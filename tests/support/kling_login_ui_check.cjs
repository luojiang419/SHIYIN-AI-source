// 先启动 canvas_startup_fixture.py；所有可灵请求由本测试模拟，不访问真实账号。
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
    const base = process.argv[2] || 'http://127.0.0.1:3127';
    const output = process.argv[3] || '.build/kling-cli-task/ui';
    fs.mkdirSync(output, {recursive:true});
    const browser = await chromium.launch({headless:true, channel:'chrome'});
    try {
        const page = await browser.newPage({viewport:{width:1440, height:1000}});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        let installed = false, authenticated = false, status = 'idle', loginCalls = 0, browserOpenCalls = 0;
        const url = 'https://klingai.com/oauth/authorize?client_id=fixture&state=fixture&redirect_uri=http%3A%2F%2F127.0.0.1%3A9999%2Fcallback&code_challenge=fixture';
        const model = {model:'kling-video-v3_0_omni', arguments:[{name:'duration', default:'5', allowed_values:['3','4','5']}], inputs:[]};
        await page.route('**/api/kling-cli/**', async route => {
            const pathname = new URL(route.request().url()).pathname;
            let body;
            if(pathname.endsWith('/install')){
                assert.equal(route.request().postDataJSON().region, 'global');
                installed = true;
                body = {ok:true, installed:true};
            } else if(pathname.endsWith('/login-open')){
                browserOpenCalls++;
                body = {ok:true};
            } else if(pathname.endsWith('/login')){
                loginCalls++;
                status = 'waiting';
                body = {ok:true, status:'starting'};
            } else if(pathname.endsWith('/login-status')){
                body = {status, authorization_url:status === 'waiting' ? url : '', error:status === 'waiting' ? '浏览器未自动打开，请点击“打开授权页面”。' : ''};
            } else {
                body = {installed, authenticated, login_required:installed && !authenticated, generation_enabled:authenticated,
                    can_manage:true, capabilities:authenticated ? {text_to_video:[model], image_to_video:[model]} : {}, error:''};
            }
            await route.fulfill({json:body});
        });
        await page.goto(`${base}/static/canvas.html?id=kling-auth-fixture`);
        await page.waitForSelector('.video-provider');
        await page.evaluate(() => {
            apiProviders.push({id:'kling-cli', name:'可灵 CLI', enabled:true, video_models:['kling-v3-omni']});
            render();
        });
        await page.locator('.video-provider').first().selectOption('kling-cli');
        await page.waitForFunction(() => klingCliState.loaded && klingCliState.canManage);
        assert.equal(loginCalls, 0, 'unconfigured region must wait for user selection');
        await page.locator('.kling-install-region').first().selectOption('global');
        await page.locator('[data-kling-install]').first().click();
        await page.waitForSelector('.kling-connection-actions a');
        assert.equal(loginCalls, 1, 'component preparation must continue to login once');
        assert.equal(await page.locator('.kling-install-region').first().inputValue(), 'global', 'region selection must survive rerenders');
        assert.equal(await page.locator('.kling-connection-actions a').first().getAttribute('href'), url);
        assert.equal(await page.locator('[data-kling-login]').first().isDisabled(), true);
        await page.locator('[data-kling-open]').first().click();
        await page.waitForFunction(() => klingLoginState.error.includes('已请求系统浏览器'));
        assert.equal(browserOpenCalls, 1, 'desktop fallback must invoke system browser');
        const bounds = await page.locator('.kling-connection-panel').first().evaluate(panel => {
            const rect = panel.getBoundingClientRect();
            return {width:panel.clientWidth, scroll:panel.scrollWidth, buttons:[...panel.querySelectorAll('button,a,select')].every(element => {
                const box = element.getBoundingClientRect();
                return box.left >= rect.left && box.right <= rect.right + 1;
            })};
        });
        assert.ok(bounds.buttons && bounds.scroll <= bounds.width + 1, 'authorization controls must fit node');
        await page.locator('.kling-connection-panel').first().screenshot({path:`${output}/authorization-waiting.png`});
        authenticated = true;
        status = 'succeeded';
        await page.waitForFunction(() => klingCliState.authenticated && klingCliState.generationEnabled);
        assert.equal(loginCalls, 1);
        assert.equal(await page.locator('.kling-connection-actions a').count(), 0, 'finished authorization URL must be cleared');
        // 重新加载后，已有组件但未登录时自动发起授权；普通节点和影视节点共享连接流程。
        authenticated = false;
        status = 'idle';
        await page.evaluate(async () => {
            klingAutoLoginAttempted = false;
            klingCliState.loaded = false;
            await loadKlingCapabilities();
        });
        await page.waitForFunction(() => klingLoginState.status === 'waiting');
        assert.equal(loginCalls, 2);
        await page.evaluate(async () => { await Promise.all([startKlingCliLogin(), startKlingCliLogin()]); });
        assert.equal(loginCalls, 2, 'repeated login clicks must be deduplicated');
        // 页面侧权限同样必须隐藏授权 URL，避免旧状态切账号后泄漏。
        const remoteHtml = await page.evaluate(() => {
            klingCliState.canManage = false;
            return klingConnectionPanelHtml();
        });
        assert.ok(!remoteHtml.includes(url) && !remoteHtml.includes('data-kling-login'));
        assert.deepEqual(errors, []);
        console.log(JSON.stringify({result:'passed', loginCalls, layout:bounds, browserErrors:errors}));
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
