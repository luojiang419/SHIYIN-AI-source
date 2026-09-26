const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
    const browser = await chromium.launch({headless:true,channel:'chrome'});
    try {
        for(const {step,width,height} of [
            {step:1,width:1500,height:900},{step:2,width:1500,height:900},
            {step:3,width:1500,height:900},{step:4,width:1500,height:900},
            {step:2,width:1920,height:900},{step:2,width:606,height:900},
            {step:2,width:390,height:844},
        ]) {
            const context = await browser.newContext({viewport:{width,height}});
            const page = await context.newPage();
            if(step === 2) {
                await page.route('**/api/account/me',async route => {
                    await new Promise(resolve => setTimeout(resolve,500));
                    await route.continue();
                });
            }
            await page.goto(`http://127.0.0.1:8767/?step=${step}`);
            const demo = page.frameLocator('#ecommerceDemo');
            await demo.locator('.ec-tryon-stepbar button[aria-current="step"]').waitFor({timeout:15000});
            assert.equal(await demo.locator('form').filter({hasText:'登录并进入'}).count(),0,'新浏览器应自动进入隔离演示，不出现缩小的登录页');
            const current = await demo.locator('.ec-tryon-stepbar button[aria-current="step"]').textContent();
            assert.ok(current.includes(`0${step}`),current);
            assert.equal(await page.locator('nav,#steps').count(),0,'框架外不应有额外导航');
            assert.equal(await demo.locator('#operationTabs,.ec-tryon-stepbar').count(),2);
            assert.equal(await demo.locator('.ec-tryon-look-model').count(),1);
            const layout = await page.evaluate(() => {
                const frame = document.querySelector('#fitFrame').getBoundingClientRect();
                return {bodyScroll:document.documentElement.scrollHeight-innerHeight,frameLeft:frame.left,frameTop:frame.top,frameRight:frame.right,frameBottom:frame.bottom,width:innerWidth,height:innerHeight};
            });
            assert.ok(layout.bodyScroll <= 1 && layout.frameLeft >= 0 && layout.frameTop >= 0 && layout.frameRight <= layout.width && layout.frameBottom <= layout.height,JSON.stringify(layout));
            const scroll = await demo.locator('html').evaluate(element => {
                const left=document.querySelector('#controlInputMount');
                const right=document.querySelector('.ec-result-panel');
                return {page:element.scrollHeight-element.clientHeight,left:left?.scrollHeight-left?.clientHeight,right:right?.scrollHeight-right?.clientHeight};
            });
            assert.ok(scroll.page <= 1 && scroll.left <= 1 && scroll.right <= 1,`第 ${step} 步不应需要滚轮浏览其他区域：${JSON.stringify(scroll)}`);
            await context.close();
        }
        console.log('real e-commerce try-on demo entry passed');
    } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
