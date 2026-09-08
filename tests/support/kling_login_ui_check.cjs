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
        let account = {user_id:'42', username:'测试用户 <img src=x onerror=alert(1)>', credits:'120', membership:'标准会员'};
        let accountFailure = false, capabilityFailure = false, accountCalls = 0;
        let generationCalls = 0;
        await page.route('**/api/canvas-video', async route => {
            generationCalls++;
            assert.equal(authenticated, true, 'only authorized accounts may generate');
            assert.equal(route.request().postDataJSON().provider_id, 'kling-cli');
            await route.fulfill({json:{url:'/kling-fixture.mp4'}});
        });
        await page.route('**/kling-fixture.mp4', route => route.fulfill({body:'', contentType:'video/mp4'}));
        const url = 'https://klingai.com/oauth/authorize?client_id=fixture&state=fixture&redirect_uri=http%3A%2F%2F127.0.0.1%3A9999%2Fcallback&code_challenge=fixture';
        const model = {model:'kling-video-v3_0_omni', arguments:[{name:'duration', default:'5', allowed_values:['3','4','5']}], inputs:[]};
        await page.route('**/api/kling-cli/**', async route => {
            const pathname = new URL(route.request().url()).pathname;
            let body;
            if(pathname.endsWith('/account')){
                accountCalls++;
                if(accountFailure) return route.fulfill({status:502, json:{detail:'读取账号失败，请重试'}});
                body = {account};
            } else if(pathname.endsWith('/install')){
                assert.equal(route.request().postDataJSON().region, 'global');
                installed = true;
                body = {ok:true, installed:true};
            } else if(pathname.endsWith('/login-open')){
                browserOpenCalls++;
                body = {ok:true};
            } else if(pathname.endsWith('/login')){
                loginCalls++;
                authenticated = false;
                status = 'waiting';
                body = {ok:true, status:'starting'};
            } else if(pathname.endsWith('/login-status')){
                body = {status, authorization_url:status === 'waiting' ? url : '', error:status === 'waiting' ? '浏览器未自动打开，请点击“打开授权页面”。' : ''};
            } else {
                if(capabilityFailure) return route.fulfill({status:502, json:{detail:'读取授权状态失败'}});
                body = {installed, authenticated, login_required:installed && !authenticated, generation_enabled:authenticated,
                    can_manage:true, capabilities:authenticated ? {text_to_video:[model], image_to_video:[model]} : {}, error:''};
            }
            await route.fulfill({json:body});
        });
        await page.goto(`${base}/static/canvas.html?id=kling-auth-fixture-${Date.now()}`);
        await page.waitForSelector('.video-provider');
        await page.evaluate(() => {
            apiProviders.push({id:'kling-cli', name:'可灵 CLI', enabled:true, video_models:['kling-v3-omni']});
            render();
        });
        await page.locator('.video-provider').first().selectOption('kling-cli');
        await page.waitForFunction(() => klingCliState.loaded && klingCliState.canManage);
        assert.equal(loginCalls, 0, 'unconfigured region must wait for user selection');
        assert.equal(await page.locator('.kling-connection-actions button').count(), 1, 'logged-out node only shows login');
        await page.locator('[data-kling-login]').first().click();
        await page.locator('.kling-install-region').first().selectOption('global');
        await page.locator('[data-kling-install]').first().click();
        await page.waitForSelector('.kling-connection-actions a');
        assert.equal(loginCalls, 1, 'component preparation must continue to login once');
        assert.equal(await page.evaluate(() => klingSelectedRegion), 'global', 'region selection must survive rerenders');
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
        assert.equal(await page.locator('[data-kling-login]').first().textContent(), '切换授权');
        await page.locator('[data-kling-account]').first().click();
        const dialog = page.locator('#kling-account-dialog');
        await page.waitForFunction(() => !klingAccountState.loading && klingAccountState.account?.credits === '120');
        assert.ok((await dialog.textContent()).includes(account.username));
        assert.equal(await dialog.locator('img').count(), 0, 'account names must be escaped');
        assert.ok((await dialog.textContent()).includes('标准会员'));
        await dialog.screenshot({path:`${output}/account-details.png`});
        account.credits = '0';
        await dialog.locator('[data-account-refresh]').click();
        await page.waitForFunction(() => klingAccountState.account?.credits === '0');
        assert.equal(await dialog.locator('dd').nth(2).textContent(), '0');
        accountFailure = true;
        await dialog.locator('[data-account-refresh]').click();
        await page.waitForFunction(() => Boolean(klingAccountState.error));
        assert.equal(await dialog.locator('dd').count(), 0, 'failed refresh must not show stale credits');
        accountFailure = false;
        account.username = null;
        await dialog.locator('[data-account-refresh]').click();
        await page.waitForFunction(() => !klingAccountState.loading && klingAccountState.account !== null);
        assert.equal(await dialog.locator('dd').first().textContent(), '官方未提供');
        await page.keyboard.press('Escape');
        await page.locator('[data-kling-login]').first().click();
        await page.waitForFunction(() => klingLoginState.status === 'waiting');
        assert.equal(loginCalls, 2);
        assert.equal(await page.evaluate(() => klingCliState.generationEnabled), false, 'switching must disable old credentials');
        assert.equal(await page.evaluate(() => klingAccountState.account), null);
        await page.evaluate(async () => { await Promise.all([startKlingCliLogin(), startKlingCliLogin()]); });
        assert.equal(loginCalls, 2, 'repeated login clicks must be deduplicated');
        status = 'failed';
        await page.waitForFunction(() => !klingLoginState.busy);
        assert.equal(await page.locator('[data-kling-login]').first().textContent(), '登录授权');
        await page.locator('[data-kling-login]').first().click();
        await page.waitForFunction(() => klingLoginState.status === 'waiting');
        assert.equal(loginCalls, 3, 'failed login can be retried');
        account = {user_id:'99', username:'新账号', credits:'30', membership:'普通用户'};
        authenticated = true;
        status = 'succeeded';
        await page.waitForFunction(() => klingCliState.generationEnabled && klingAccountState.account?.user_id === '99');
        await page.locator('[data-kling-account]').first().click();
        await page.waitForFunction(() => !klingAccountState.loading);
        await dialog.screenshot({path:`${output}/account-switched.png`});
        await page.setViewportSize({width:390, height:844});
        const dialogFits = await dialog.evaluate(element => element.scrollWidth <= element.clientWidth + 1 && element.getBoundingClientRect().right <= innerWidth);
        assert.ok(dialogFits, 'account dialog must fit narrow screens');
        await page.keyboard.press('Escape');
        await page.setViewportSize({width:1440, height:1000});
        await page.evaluate(() => {
            const video = nodes.find(isKlingVideoNode);
            video.type = 'film-video';
            render();
        });
        assert.equal(await page.locator('[data-kling-login]').first().textContent(), '切换授权', 'film video must share authorization controls');
        await page.locator('[data-kling-account]').first().click();
        await page.waitForFunction(() => !klingAccountState.loading);
        assert.ok((await dialog.textContent()).includes('新账号'));
        await page.keyboard.press('Escape');
        const generationStatus = await page.evaluate(async () => {
            const node = nodes.find(isKlingVideoNode);
            node.prompt = '授权后生成测试视频';
            await runFilmNode(node.id);
            return node.runStatus;
        });
        assert.equal(generationStatus, 'done', 'authorized video generation must reach the result');
        assert.equal(generationCalls, 1);
        capabilityFailure = true;
        await page.evaluate(() => loadKlingCapabilities());
        assert.equal(await page.evaluate(() => klingCliState.generationEnabled), false, 'query failure must disable stale generation');
        capabilityFailure = false;
        // 已有组件但未登录时必须等待点击，不能自动弹浏览器。
        authenticated = false;
        status = 'idle';
        await page.evaluate(async () => {
            klingCliState.loaded = false;
            await loadKlingCapabilities();
        });
        assert.equal(loginCalls, 3, 'loading logged-out capabilities must not start OAuth');
        assert.equal(await page.locator('.kling-connection-actions button').count(), 1);
        const blocked = await page.evaluate(async () => {
            const node = nodes.find(isKlingVideoNode);
            const messages = [];
            for(const run of [runVideoNode, runFilmNode]){
                try { await run(node.id, {cascade:true}); }
                catch(error) { messages.push(error.message); }
            }
            return messages;
        });
        assert.equal(blocked.length, 2, 'both video paths reject unauthenticated generation');
        assert.equal(generationCalls, 1);
        // 页面侧权限同样必须隐藏授权 URL，避免旧状态切账号后泄漏。
        const remoteHtml = await page.evaluate(() => {
            klingCliState.canManage = false;
            return klingConnectionPanelHtml();
        });
        assert.ok(!remoteHtml.includes(url) && !remoteHtml.includes('data-kling-login'));
        assert.deepEqual(errors, []);
        console.log(JSON.stringify({result:'passed', loginCalls, accountCalls, layout:bounds, browserErrors:errors}));
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
