const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const account = process.env.TRYON_DEMO_ACCOUNT;
const password = process.env.TRYON_DEMO_PASSWORD;
if(!account || !password) throw new Error('需要 TRYON_DEMO_ACCOUNT 和 TRYON_DEMO_PASSWORD');

(async () => {
    const browser = await chromium.launch({headless:true,channel:'chrome'});
    try {
        for(const step of [1,2,3,4]) {
            const context = await browser.newContext({viewport:{width:1500,height:900}});
            const login = await context.request.post('http://127.0.0.1:8766/api/account/login',{data:{account,password}});
            assert.equal(login.status(),200);
            const page = await context.newPage();
            if(step === 2) {
                await page.route('**/api/account/me',async route => {
                    await new Promise(resolve => setTimeout(resolve,500));
                    await route.continue();
                });
            }
            await page.goto(`http://127.0.0.1:8767/?step=${step}`);
            await page.waitForURL('**/static/ecommerce.html',{timeout:15000});
            await page.locator('.ec-tryon-stepbar button[aria-current="step"]').waitFor({timeout:15000});
            const current = await page.locator('.ec-tryon-stepbar button[aria-current="step"]').textContent();
            assert.ok(current.includes(`0${step}`),current);
            assert.equal(await page.locator('#steps').count(),0,'不应存在截图画廊的额外步骤栏');
            assert.equal(await page.locator('#operationTabs,.ec-tryon-stepbar').count(),2);
            assert.equal(await page.locator('.ec-tryon-look-model').count(),1);
            await context.close();
        }
        console.log('real e-commerce try-on demo entry passed');
    } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
