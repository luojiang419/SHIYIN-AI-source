const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');

(async()=>{
    const browser=await chromium.launch({headless:true,channel:'chrome'});
    try{
        const page=await browser.newPage();
        const errors=[];
        page.on('pageerror',error=>errors.push(error.message));
        await page.setContent('<div id="node"><button data-linkfox-balance></button></div>');
        await page.addStyleTag({content:':root{--line:#dadde2;--card-solid:#fff;--text:#20242a;--muted:#66717d;--soft:#f3f5f8;--strong:#20242a;--strong-text:#fff}'});
        await page.addStyleTag({path:path.resolve(__dirname,'../../static/css/canvas-linkfox-video.css')});
        await page.evaluate(()=>{
            window.linkfoxTest={configured:false,pointsAvailable:false,slowBalance:false,saves:[],balanceCalls:0};
            window.fetch=async(url,options={})=>{
                const state=window.linkfoxTest;
                if(url==='/api/linkfox-config' && options.method==='PUT'){
                    state.saves.push(JSON.parse(options.body));
                    state.configured=true;
                    return {ok:true,json:async()=>({configured:true})};
                }
                if(url==='/api/linkfox-config') return {ok:true,json:async()=>({configured:state.configured,tool_gateway:'https://tool-gateway.linkfox.com'})};
                if(url==='/api/linkfox/balance'){
                    state.balanceCalls++;
                    if(state.slowBalance) await new Promise(resolve=>setTimeout(resolve,3200));
                    return {ok:true,json:async()=>state.pointsAvailable?{available:true,remaining_points:1420480}:{available:false,error:'密钥或网络错误'}};
                }
                throw new Error(`Unexpected request: ${url}`);
            };
        });
        await page.addScriptTag({path:path.resolve(__dirname,'../../static/js/canvas-linkfox-video.js')});
        await page.evaluate(()=>window.CanvasLinkfoxVideo.bindUnified(document.getElementById('node'),{id:'video',model:'seedance2.0mini'},()=>{}));
        const dialog=page.locator('.linkfox-key-setup');
        await dialog.waitFor();
        const shot=path.resolve(__dirname,'../../.codex-tmp/linkfox-key-setup-dialog.png');
        fs.mkdirSync(path.dirname(shot),{recursive:true});
        await page.screenshot({path:shot});
        assert.equal(await dialog.locator('[data-linkfox-setup-confirm]').textContent(),'确定并查询积分');
        await dialog.locator('input').fill('dummy-test-key');
        await dialog.locator('[data-linkfox-setup-confirm]').click();
        await dialog.locator('.linkfox-setup-line.error').waitFor();
        assert.equal(await dialog.locator('input').inputValue(),'dummy-test-key');
        await page.evaluate(()=>{window.linkfoxTest.pointsAvailable=true;window.linkfoxTest.slowBalance=true;});
        await dialog.locator('[data-linkfox-setup-confirm]').click();
        await dialog.getByText(/仍在查询积分/).waitFor();
        await dialog.locator('[data-linkfox-setup-confirm]').getByText('确定，进入画布').waitFor();
        assert.equal(await page.locator('[data-linkfox-balance]').textContent(),'LinkFox 剩余积分：1,420,480');
        assert.equal(await dialog.locator('.linkfox-setup-line.ok').count(),3);
        await dialog.locator('[data-linkfox-setup-confirm]').click();
        assert.equal(await dialog.count(),0);
        const result=await page.evaluate(()=>window.linkfoxTest);
        assert.equal(result.saves.length,2);
        assert.equal(result.saves[0].api_key,'dummy-test-key');
        assert.equal(result.balanceCalls,2);
        await page.evaluate(()=>window.CanvasLinkfoxVideo.bindUnified(document.getElementById('node'),{id:'video',model:'seedance2.0mini'},()=>{}));
        assert.equal(await dialog.count(),0);
        assert.deepEqual(errors,[]);
        console.log('LinkFox 首次密钥弹窗、失败重试、积分确认和复用验证通过');
    }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
