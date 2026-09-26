/** Capture all four guided try-on screens against a running, isolated backend.
 * No network requests are mocked. Reference images are supplied by TRYON_DEMO_ASSET_DIR.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const baseUrl = process.env.TRYON_DEMO_BASE_URL || 'http://127.0.0.1:8766';
const assetDir = process.env.TRYON_DEMO_ASSET_DIR || path.resolve('.codex-tmp/tryon-steps-demo/assets');
const outputDir = process.env.TRYON_DEMO_OUTPUT_DIR || path.resolve('.codex-tmp/tryon-steps-demo/screenshots');
const asset = name => path.join(assetDir,name);

(async () => {
    for(const name of ['model.png','blazer.png','trousers.png','loafers.png','pose.png','blazer-detail.png']) {
        assert.ok(fs.existsSync(asset(name)),`缺少演示素材：${name}`);
    }
    fs.mkdirSync(outputDir,{recursive:true});
    const browser = await chromium.launch({headless:true,channel:'chrome'});
    try {
        const context = await browser.newContext({viewport:{width:1580,height:1250},deviceScaleFactor:1,acceptDownloads:true});
        const account = process.env.TRYON_DEMO_ACCOUNT || `tryondemo${Date.now()}`;
        const password = process.env.TRYON_DEMO_PASSWORD || `Demo-${crypto.randomUUID()}-A9!`;
        const registration = await context.request.post(`${baseUrl}/api/account/register`,{data:{account,password}});
        if(registration.status() === 409 && process.env.TRYON_DEMO_ACCOUNT) {
            const login = await context.request.post(`${baseUrl}/api/account/login`,{data:{account,password}});
            assert.equal(login.status(),200,`演示账号登录失败：${login.status()} ${await login.text()}`);
        } else {
            assert.equal(registration.status(),201,`演示账号注册失败：${registration.status()} ${await registration.text()}`);
        }
        const page = await context.newPage();
        await page.addInitScript(() => localStorage.setItem('studio_theme','dark'));
        const calls = [];
        page.on('response',response => {
            const url = new URL(response.url());
            if(url.pathname === '/api/ai/upload' || url.pathname === '/api/ecommerce/analyze') calls.push({path:url.pathname,status:response.status()});
        });
        await page.goto(`${baseUrl}/static/ecommerce.html`,{waitUntil:'domcontentloaded'});
        await page.locator('[data-operation="try_on"]').click();
        await page.locator('.ec-tryon-stepbar button').first().waitFor();
        const upload = async (cardSelector,fileName) => {
            await page.locator(`${cardSelector} .ec-upload-slot`).click();
            await page.locator('#fileInput').setInputFiles(asset(fileName));
            await page.locator(`${cardSelector} .ec-upload-preview img`).first().waitFor({timeout:30000});
            await page.waitForFunction(selector => {
                const card = document.querySelector(selector);
                return card && !card.querySelector('.uploading,[data-uploading="true"]') && card.querySelector('.ec-upload-preview img')?.complete;
            },cardSelector,{timeout:30000});
        };
        const capture = async (number,label) => {
            await page.evaluate(() => {const mount=document.querySelector('#controlInputMount');if(mount)mount.scrollTop=0;});
            await page.waitForTimeout(350);
            const file = path.join(outputDir,`${number}-${label}.png`);
            await page.screenshot({path:file,fullPage:true});
            assert.equal(await page.locator(`.ec-tryon-stepbar button[data-tryon-step="${number-1}"][aria-current="step"]`).count(),1);
            return file;
        };

        await upload('.ec-tryon-slot-card.is-model','model.png');
        const screenshots = [await capture(1,'model')];
        await page.locator('[data-tryon-step-next]').click();
        await upload('[data-tryon-wardrobe-role="upper_garment"]','blazer.png');
        await upload('[data-tryon-wardrobe-role="lower_garment"]','trousers.png');
        await page.locator('[data-add-tryon-reference]').click();
        await upload('[data-tryon-wardrobe-role="shoes"]','loafers.png');
        screenshots.push(await capture(2,'outfit'));

        await page.locator('[data-tryon-step-next]').click();
        await upload('[data-tryon-wardrobe-role="pose"]','pose.png');
        await upload('.ec-tryon-slot-card.is-fabric-detail','blazer-detail.png');
        const detailTarget = page.locator('[data-tryon-detail-target]');
        if(await detailTarget.locator('option').count()>1) await detailTarget.selectOption({index:1});
        screenshots.push(await capture(3,'details'));

        await page.locator('[data-tryon-step-next]').click();
        const analysisResponsePromise = page.waitForResponse(response => new URL(response.url()).pathname === '/api/ecommerce/analyze',{timeout:60000});
        await page.locator('[data-tryon-plan-prompt]').click();
        const analysisResponse = await analysisResponsePromise;
        const analysis = await analysisResponse.json();
        console.log(`提示词分析：HTTP ${analysisResponse.status()}，状态 ${analysis.status}，长度 ${String(analysis.prompt_preview || '').length}`);
        await page.waitForFunction(() => {
            const status=document.querySelector('[data-tryon-plan-status]')?.textContent || '';
            return !status.includes('正在分析参考图');
        },null,{timeout:20000});
        assert.ok(String(analysis.prompt_preview || '').length>20,'真实分析接口应返回可审阅提示词');
        assert.ok((await page.locator('[data-tryon-plan-result]').textContent()).length>20,'页面应展示分析提示词');
        screenshots.push(await capture(4,'prompt'));
        assert.equal(calls.filter(item=>item.path==='/api/ai/upload'&&item.status===200).length,6);
        assert.ok(calls.some(item=>item.path==='/api/ecommerce/analyze'&&item.status===200));
        const promptText = await page.locator('[data-tryon-plan-result]').textContent();
        fs.writeFileSync(path.join(outputDir,'verification.json'),JSON.stringify({baseUrl,uploads:6,analysisHttpStatus:200,promptLength:promptText.length,screenshots},null,2));
        if(process.env.TRYON_DEMO_ACCOUNT) {
            const seed = await page.evaluate(() => {
                const accountId = window.StudioPageState?.accountId || '';
                const settings = localStorage.getItem(`studio_ecommerce_settings_v2:account:${accountId}`) || localStorage.getItem('studio_ecommerce_settings_v2') || '';
                return {accountId,settings};
            });
            assert.ok(seed.accountId && seed.settings,'无法保存演示账号的页面状态');
            fs.writeFileSync(path.resolve('.codex-tmp/tryon-steps-demo/seed-settings.json'),JSON.stringify(seed));
        }
        await page.waitForTimeout(900);
        console.log(`四步真实页面演示通过：${screenshots.join(', ')}`);
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
