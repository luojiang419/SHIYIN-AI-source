// 浏览器行为回归：只运行本地脚本和模拟响应，不调用生成 API。
const {chromium} = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const quick = fs.readFileSync(path.join(root, 'static/js/quick-save.js'), 'utf8');
const canvas = fs.readFileSync(path.join(root, 'static/js/canvas.js'), 'utf8');
const slice = (a, b) => canvas.slice(canvas.indexOf(a), canvas.indexOf(b, canvas.indexOf(a)));

(async () => {
    const browser = await chromium.launch({headless:true, channel:'msedge'});
    try {
        for(const desktop of [false, true]){
            const page = await browser.newPage({acceptDownloads:true});
            const posts = [];
            await page.route('http://download.test/**', async route => {
                const req = route.request();
                if(req.url().includes('/api/app-settings/quick-save')){
                    if(req.method() === 'POST') posts.push(req.postData());
                    return route.fulfill({json:req.method() === 'POST' ? {saved:true, name:'test.txt'} : {mode:'silent', directory:'C:/Downloads'}});
                }
                if(req.url().includes('/api/download-output')) return route.fulfill({body:'download bytes', headers:{'content-type':'application/octet-stream', 'content-disposition':'attachment; filename="test.txt"'}});
                return route.fulfill({contentType:'text/html', body:'<html><body></body></html>'});
            });
            await page.goto('http://download.test/');
            if(desktop) await page.evaluate(() => { window.__TAURI_INTERNALS__ = {invoke:() => {}}; });
            for(const framed of [false, true]){
                if(framed){
                    await page.evaluate(() => { const f = document.createElement('iframe'); f.src = '/frame'; document.body.append(f); });
                    await page.waitForFunction(() => document.querySelector('iframe')?.contentDocument?.readyState === 'complete');
                }
                const target = framed ? page.frames().find(f => f !== page.mainFrame()) : page;
                await target.addScriptTag({content:quick});
                assert.equal(await target.evaluate(async () => (await ShiyinQuickSave.getState()).mode), desktop ? 'silent' : 'manual');
                await target.evaluate(() => window.postMessage({type:'quick-save-settings:changed', mode:'silent', directory:'C:/Server'}, location.origin));
                const start = posts.length;
                if(desktop){
                    await target.evaluate(() => ShiyinQuickSave.saveAll([{url:'/output/test.txt', name:'test.txt'}]));
                    assert.equal(posts.length, start + 1);
                } else {
                    const download = page.waitForEvent('download');
                    await target.evaluate(() => ShiyinQuickSave.saveAll([{blob:new Blob(['browser bytes']), name:'local.txt'}]));
                    assert.equal((await download).suggestedFilename(), 'local.txt');
                    assert.equal(await target.evaluate(() => ShiyinQuickSave.isSilent()), false);
                }
                await target.evaluate(() => { const a = document.createElement('a'); a.href='/api/download-output?url=test'; a.download='test.txt'; a.textContent='下载'; a.id='download'; document.body.append(a); });
                if(desktop){
                    await target.locator('#download').click();
                    await target.waitForFunction(() => !!document.getElementById('shiyinQuickSaveToast')?.textContent.includes('已保存'));
                    assert.equal(posts.length, start + 2);
                } else {
                    const download = page.waitForEvent('download');
                    await target.locator('#download').click();
                    assert.equal((await download).suggestedFilename(), 'test.txt');
                    assert.equal(posts.length, 0);
                }
            }
            await page.close();
        }
        const page = await browser.newPage();
        await page.addStyleTag({path:path.join(root, 'static/css/canvas.css')});
        await page.addScriptTag({content:`
            let nodes=[]; let serial=0;
            const uid=()=>String(++serial);
            const outputImageUrls=n=>n.images;
            const outputImageName=u=>u;
            const mediaKindForNode=()=> 'image';
            const scheduleSave=()=>{};
            const scheduleClassicNodeRectMeasure=()=>{};
            const defaultNodeSize=type=>type==='image'?{w:260,h:336}:{w:260,h:180};
            ${slice('function createInputGroupFromOutput(', 'function convertOutputNodeToInputGroup(')}
            ${slice('const CLASSIC_VIDEO_NODE_MIN_WIDTH', 'function renderNode(node)')}
            window.checkLayout=()=>{
                const group=createInputGroupFromOutput({images:['a','b','c','d','e']},{x:0,y:0});
                for(const n of nodes.filter(n=>n.type==='image')){
                    const el=document.createElement('div'); el.className='node image-node sized has-image';
                    normalizeClassicNodeLayout(n);
                    syncClassicMediaNodeOrientation(el,n,{naturalWidth:800,naturalHeight:1200});
                    n.natural_w=800; n.natural_h=1200;
                    const restored=JSON.parse(JSON.stringify(n));
                    normalizeClassicNodeLayout(restored);
                    el.style.width=restored.w+'px'; el.style.height=restored.h+'px'; document.body.append(el);
                    if(restored.w!==260 || restored.h!==336 || el.getBoundingClientRect().width!==260) throw Error('图片尺寸改变');
                    if(n.x+n.w>group.x+group.w || n.y+n.h>group.y+group.h) throw Error('图片超出组');
                }
                const normal={id:'normal',type:'image',url:'a',natural_w:800,natural_h:1200,w:260,h:336};
                normalizeClassicNodeLayout(normal);
                if(normal.w!==520 || normal.h!==undefined) throw Error('普通竖图布局回归');
                return nodes.length;
            };
        `});
        assert.equal(await page.evaluate(() => checkLayout()), 6);
        console.log('PASS: Web/desktop × top-level/iframe single and batch downloads; portrait group layout and reload; normal portrait layout.');
    } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode=1;});
