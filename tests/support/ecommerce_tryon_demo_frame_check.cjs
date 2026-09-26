const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
    const browser = await chromium.launch({headless:true,channel:'chrome'});
    try {
        const page = await browser.newPage();
        const url = pathToFileURL(path.resolve('开发任务/223-自由换衣步骤演示/index.html')).href;
        for(const viewport of [{width:1920,height:900},{width:1280,height:720},{width:390,height:844}]) {
            await page.setViewportSize(viewport);
            await page.goto(`${url}?step=2`);
            await page.locator('#preview').evaluate(image => image.decode());
            const metrics = await page.evaluate(() => {
                const frame = document.querySelector('.preview-scroll');
                const footer = document.querySelector('footer').getBoundingClientRect();
                const caption = document.querySelector('figcaption').getBoundingClientRect();
                return {
                    documentHeight:document.documentElement.scrollHeight,
                    documentWidth:document.documentElement.scrollWidth,
                    viewportHeight:innerHeight,
                    viewportWidth:innerWidth,
                    frameClientHeight:frame.clientHeight,
                    frameScrollHeight:frame.scrollHeight,
                    footerBottom:footer.bottom,
                    captionBottom:caption.bottom,
                    redundantButtons:document.querySelectorAll('#previous,#next,.controls').length,
                };
            });
            assert.ok(metrics.documentHeight <= metrics.viewportHeight + 1,`${viewport.width}px 外层页面不应竖向滚动：${JSON.stringify(metrics)}`);
            assert.ok(metrics.documentWidth <= metrics.viewportWidth + 1,`${viewport.width}px 外层页面不应横向滚动`);
            assert.equal(metrics.redundantButtons,0,'演示页底部不应出现重复的上一步/下一步按钮');
            assert.ok(metrics.footerBottom <= viewport.height && metrics.captionBottom <= viewport.height,`${viewport.width}px 说明应固定在视口内`);
            if(viewport.width >= 1280) {
                assert.ok(metrics.frameScrollHeight > metrics.frameClientHeight,`${viewport.width}px 截图应只在框架内滚动`);
                await page.locator('#previewScroll').evaluate(frame => {frame.scrollTop = frame.scrollHeight;});
                assert.ok(await page.locator('#previewScroll').evaluate(frame => frame.scrollTop > 0));
                assert.equal(await page.evaluate(() => window.scrollY),0);
                await page.locator('nav button[data-index="3"]').click();
                assert.equal(await page.locator('#previewScroll').evaluate(frame => frame.scrollTop),0,'切换步骤后框内滚动位置应复位');
            }
        }
        console.log('try-on demo frame scrolling passed');
    } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
