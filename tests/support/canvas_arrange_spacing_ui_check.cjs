// 使用隔离 canvas_startup_fixture.py，不连接用户数据。
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
    const base = process.argv[2] || 'http://127.0.0.1:3017';
    const artifacts = process.argv[3] || '测试/自动整理间距-20260908';
    fs.mkdirSync(artifacts, {recursive:true});
    const browser = await chromium.launch({headless:true, channel:'chrome'});
    try {
        const context = await browser.newContext({viewport:{width:1100,height:1000}});
        const page = await context.newPage();
        let state = {canvas_arrange_spacing:56, canvas_group_arrange_spacing:28};
        let fail = false;
        const writes = [];
        await context.route('**/api/app-settings', async route => {
            if(route.request().method() === 'PUT'){
                await new Promise(resolve => setTimeout(resolve, 120));
                if(fail) return route.fulfill({status:500,json:{detail:'fixture save failure'}});
                const payload = route.request().postDataJSON();
                writes.push(payload);
                state = {...state,...payload};
            }
            await route.fulfill({json:state});
        });
        await page.goto(`${base}/static/app-settings.html`);
        await page.waitForFunction(() => !document.getElementById('arrangeSpacing').disabled);
        const change = async (id,value,commit=true) => page.locator(`#${id}`).evaluate((el,{value,commit}) => {
            el.value=String(value);
            el.dispatchEvent(new Event('input',{bubbles:true}));
            if(commit) el.dispatchEvent(new Event('change',{bubbles:true}));
        },{value,commit});
        await change('arrangeSpacing',80,false);
        assert.equal(await page.locator('#arrangeSpacingValue').textContent(),'80 px');
        assert.deepEqual(await page.locator('#arrangeSpacingPreview').evaluate(el=>{
            const css=getComputedStyle(el); return [css.columnGap,css.rowGap];
        }),['16px','16px']);
        assert.equal(writes.length,0,'preview must not save before commit');
        await change('arrangeSpacing',80);
        await change('arrangeSpacing',120);
        await change('groupArrangeSpacing',36);
        await page.waitForFunction(() => document.getElementById('arrangeSpacingStatus').textContent==='已保存' && document.getElementById('groupArrangeSpacingStatus').textContent==='已保存');
        assert.equal(state.canvas_arrange_spacing,120);
        assert.equal(state.canvas_group_arrange_spacing,36);
        await page.reload();
        await page.waitForFunction(() => document.getElementById('arrangeSpacing').value==='120');
        const canvas = await context.newPage();
        await canvas.goto(`${base}/static/canvas.html?id=spacing-ui-fixture`);
        await canvas.waitForFunction(() => window.CanvasArrangeSpacing?.gap()===120);
        await page.bringToFront();
        await change('arrangeSpacing',0);
        await page.waitForFunction(() => document.getElementById('arrangeSpacingStatus').textContent==='已保存');
        assert.equal(await canvas.evaluate(()=>window.CanvasArrangeSpacing.gap()),0,'open canvas must observe saved zero gap');
        assert.equal(await canvas.evaluate(()=>window.CanvasArrangeSpacing.groupGap()),36);
        fail=true;
        await change('arrangeSpacing',240);
        await page.waitForFunction(() => document.getElementById('arrangeSpacingStatus').textContent.includes('保存失败'));
        assert.equal(await page.locator('#arrangeSpacing').inputValue(),'0','failed save must restore saved value');
        fail=false;
        await page.locator('#arrangeSpacingReset').click();
        await page.waitForFunction(() => document.getElementById('arrangeSpacingStatus').textContent==='已保存');
        assert.equal(state.canvas_arrange_spacing,56);
        const card=page.locator('section[aria-labelledby="arrangeSpacingTitle"]');
        await card.screenshot({path:`${artifacts}/settings-light.png`});
        await page.evaluate(()=>document.documentElement.classList.add('studio-theme-dark'));
        await card.screenshot({path:`${artifacts}/settings-dark.png`});
        for(const id of ['arrangeSpacing','groupArrangeSpacing']){
            await page.locator(`#${id}`).focus();
            const colors = await page.locator(`#${id}`).evaluate(el => [
                getComputedStyle(el).backgroundColor,
                getComputedStyle(el).outlineColor,
                getComputedStyle(el,'::-webkit-slider-runnable-track').backgroundColor,
                getComputedStyle(el,'::-webkit-slider-thumb').backgroundColor,
            ]);
            for(const color of colors){
                const [r,g,b] = (color.match(/[\d.]+/g) || []).map(Number);
                assert.ok(!(b>r+12 && b>g+12), `blue theme residue: ${id} ${color}`);
            }
        }
        await page.setViewportSize({width:390,height:900});
        await card.screenshot({path:`${artifacts}/settings-mobile.png`});
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile layout must not overflow');
        console.log('PASS: pixel preview, independent persistence, queued saves, reload, open-canvas sync, zero gap, failed-save rollback, reset and responsive layouts');
    } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
