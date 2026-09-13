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
            const nodesEl=document.body;
            const canvasNodeDomIndex=new Map(), canvasNodeIndex=new Map(), canvasNodeRectIndex=new Map();
            const classicIdleNodeRectMeasureIds=new Set(), classicConnectionDirtyIds=new Set(), selected=new Set();
            let classicIdleNodeRectMeasureHandle=0;
            const invalidateCanvasGeometry=()=>{}, markClassicConnectionsDirtyForNodes=()=>{};
            const scheduleLinksRender=()=>{}, scheduleMinimapNodeUpdate=()=>{}, scheduleSelectionHubPosition=()=>{};
            const pushUndo=()=>{throw Error('自动整理不应新增撤销记录');};
            const moveCanvasNodeAtom=(n,x,y)=>{n.x=x;n.y=y;};
            const defaultNodeSize=type=>type==='image'?{w:260,h:336}:{w:260,h:180};
            ${slice('function scheduleClassicNodeRectMeasure(', 'function rebuildCanvasDomIndexes(')}
            ${slice('function createInputGroupFromOutput(', 'function convertOutputNodeToInputGroup(')}
            ${slice('const CLASSIC_VIDEO_NODE_MIN_WIDTH', 'function renderNode(node)')}
            ${slice('function nodeRect(n){', 'const CANVAS_NODE_LAYOUT_GAP')}
            ${slice('const CANVAS_GROUP_ARRANGE_PADDING', 'function arrangeSelectedCanvasGroup(')}
            ${slice('const canvasGroupAutoFitPending', 'function createGroupForUploadedNodes(')}
            let renderCount=0;
            function render(){
                renderCount++;
                document.body.innerHTML='';
                for(const n of nodes){
                    normalizeClassicNodeLayout(n);
                    const el=document.createElement('div');
                    el.dataset.id=n.id;
                    el.className='node '+n.type+'-node';
                    el.style.left=n.x+'px';el.style.top=n.y+'px';
                    el.style.width=n.w+'px';el.style.height=(n.h||360)+'px';
                    document.body.append(el);
                    canvasNodeDomIndex.set(n.id,el);canvasNodeIndex.set(n.id,n);
                    if(!canvasNodeRectIndex.has(n.id))canvasNodeRectIndex.set(n.id,nodeRect(n));
                }
            }
            const settle=()=>new Promise(resolve=>setTimeout(resolve,450));
            window.checkLayout=async()=>{
                const group=createInputGroupFromOutput({images:['a','b','c','d','e']},{x:0,y:0});
                render();
                await settle();
                function verify(){
                    const members=group.items.map(id=>nodes.find(n=>n.id===id));
                    const rects=members.map(nodeRect);
                    rects.forEach((r,i)=>{
                        if(r.x+r.w>group.x+group.w-24 || r.y+r.h>group.y+group.h-24) throw Error('图片超出组');
                        if(i && i%3 && r.x < rects[i-1].x+rects[i-1].w+28) throw Error('水平顺序或间距错误');
                        if(i>=3 && r.y < rects[i-3].y+rects[i-3].h+28) throw Error('垂直顺序或间距错误');
                    });
                }
                verify();
                // 超过初始自动整理定时器后才获得竖图尺寸，必须通过真实测量回调再次整理。
                const first=nodes[0];first.natural_w=800;first.natural_h=1200;
                syncClassicMediaNodeOrientation(canvasNodeDomIndex.get(first.id),first);
                await settle();
                if(first.w!==520 || first.h!==undefined)throw Error('竖图尺寸被限制');
                verify();
                // JSON 恢复保留自动排版语义；后续另一个节点变高同样自动扩组。
                if(!JSON.parse(JSON.stringify(group)).autoArrangeInputGroup)throw Error('排版标记未保留');
                const last=nodes[4];last.h=650;render();
                scheduleClassicNodeRectMeasure([last.id]);
                await settle();verify();
                const stable=renderCount;await settle();
                if(renderCount!==stable)throw Error('自动整理重复渲染');
                return nodes.length;
            };
        `});
        assert.equal(await page.evaluate(() => checkLayout()), 6);
        console.log('PASS: Web/desktop × top-level/iframe single and batch downloads; ordered input groups with late portrait sizing, spacing, bounds and stable reflow.');
    } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode=1;});
