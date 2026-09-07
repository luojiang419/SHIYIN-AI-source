// 使用隔离 canvas_startup_fixture.py；生成接口由 Playwright 替身处理。
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base=process.argv[2]||'http://127.0.0.1:3017';
const artifacts=process.argv[3]||'测试/LinkFox连线回归-20260907';
(async()=>{
    fs.mkdirSync(artifacts,{recursive:true});
    const browser=await chromium.launch({headless:true,channel:'chrome'});
    try {
        for(const smart of [false,true]){
            const page=await browser.newPage({viewport:{width:1400,height:1100}});
            const errors=[],requests=[];
            page.on('pageerror',error=>errors.push(error.message));
            page.on('dialog',dialog=>dialog.dismiss());
            if(smart) await page.route('**/static/smart-canvas.html?*',async route=>{
                // 产品入口已跳转普通画布，仅在测试页去掉兼容跳转以验证保留的运行时。
                const response=await route.fetch();
                const html=(await response.text()).replace(/<script>\s*\(function\(\)\{[\s\S]*?location\.replace\(target\);[\s\S]*?<\/script>/,'');
                await route.fulfill({response,body:html});
            });
            await page.route('**/api/linkfox-video',route=>{
                requests.push(route.request().postDataJSON());
                return route.fulfill({json:{videos:['https://example.com/result.mp4']}});
            });
            await page.goto(`${base}/static/${smart?'smart-canvas':'canvas'}.html?id=linkfox-${smart}`);
            await page.waitForFunction(()=>typeof nodes!=='undefined' && nodes.length && typeof render==='function');
            const connected=await page.evaluate(smart=>{
                nodes.length=0;
                const api=window.CanvasLinkfoxVideo;
                const target=api.createNode({x:550,y:30},{id:'linkfox-test',prompt:'fixture',w:480});
                nodes.push(target);
                for(let i=0;i<3;i++) nodes.push(smart?
                    {id:`image-${i}`,type:'image',images:[{url:`/fixture.png?image=${i}`,kind:'image'}],x:20,y:20+i*280,w:220,h:220}:
                    {id:`image-${i}`,type:'image',url:`/fixture.png?image=${i}`,x:20,y:20+i*280,w:220,h:220});
                if(smart){
                    canvas.connections=[];canvasUsesConnections=true;
                    for(let i=0;i<3;i++) assertConnection(connectInputNode(`image-${i}`,target.id,'reference-image'));
                } else {
                    connections=[];
                }
                function assertConnection(value){if(!value) throw new Error('connection rejected');}
                viewport.x=0;viewport.y=0;viewport.scale=1;
                render();applyViewport();
                return smart?canvas.connections.length:connections.length;
            },smart);
            if(smart) assert.equal(connected,3,'all three connections are persisted');
            else {
                for(let i=0;i<3;i++){
                    const from=await page.locator(`[data-id="image-${i}"] .port.out`).boundingBox();
                    const to=await page.locator('[data-id="linkfox-test"] .port.in').boundingBox();
                    await page.mouse.move(from.x+from.width/2,from.y+from.height/2);
                    await page.mouse.down();
                    await page.mouse.move(to.x+to.width/2,to.y+to.height/2,{steps:8});
                    await page.mouse.up();
                    await page.waitForFunction(count=>connections.filter(c=>c.to==='linkfox-test').length===count,i+1);
                    assert.match(await page.locator('[data-linkfox-input-summary]').textContent(),new RegExp(`已连接 ${i+1} 张`));
                }
                // 兼容截图中的历史无角色连线。
                await page.evaluate(()=>{connections.forEach(c=>delete c.inputRole);render();});
            }
            const summary=page.locator('[data-linkfox-input-summary]');
            assert.match(await summary.textContent(),/已连接 3 张/);
            await page.locator('[data-linkfox-action="run"]').click();
            await page.waitForFunction(()=>nodes.find(n=>n.id==='linkfox-test').runStatus==='done');
            assert.deepEqual(requests[0].imageList,[0,1,2].map(i=>`/fixture.png?image=${i}`));
            await page.locator('[data-linkfox-action="run"]').click();
            await page.waitForFunction(()=>nodes.find(n=>n.id==='linkfox-test').runStatus==='done');
            assert.equal(requests.length,2,'button rerun actually sends a second request');
            assert.deepEqual(requests[1].imageList,requests[0].imageList,'output video must not replace inputs');
            await page.screenshot({path:`${artifacts}/${smart?'smart':'classic'}-three-images.png`,fullPage:true});
            await page.evaluate(smart=>{
                const node=nodes.find(n=>n.id==='linkfox-test');node.mode='first_last_frame';
                const links=[{id:'tail',from:'image-1',to:node.id,inputRole:'last-frame',kind:'input'},
                    {id:'head',from:'image-0',to:node.id,inputRole:'reference-image',kind:'input'}];
                if(smart) canvas.connections=links;else connections=links;
                render();
            },smart);
            const ports=await page.locator('[data-id="linkfox-test"] [data-input-role]').evaluateAll(items=>items.map(el=>({role:el.dataset.inputRole,top:el.getBoundingClientRect().top})));
            const first=ports.find(p=>p.role==='reference-image'),last=ports.find(p=>p.role==='last-frame');
            assert.ok(first && last && last.top>first.top+30,'first and last ports must not overlap');
            await page.locator('[data-linkfox-action="run"]').click();
            await page.waitForFunction(()=>nodes.find(n=>n.id==='linkfox-test').runStatus==='done');
            assert.equal(requests[2].imageUrl,'/fixture.png?image=0');
            assert.equal(requests[2].lastFrameImageUrl,'/fixture.png?image=1');
            await page.evaluate(smart=>{
                if(smart) canvas.connections=[];else connections=[];
                render();
            },smart);
            assert.match(await summary.textContent(),/等待连接/);
            await page.locator('[data-linkfox-action="run"]').click();
            await page.waitForFunction(()=>nodes.find(n=>n.id==='linkfox-test').runStatus==='failed');
            assert.equal(requests.length,3,'empty inputs must never submit');
            assert.deepEqual(errors,[]);
            console.log(`${smart?'smart':'classic'}: 3 images, button, rerun, role order, disconnect passed`);
            await page.close();
        }
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
