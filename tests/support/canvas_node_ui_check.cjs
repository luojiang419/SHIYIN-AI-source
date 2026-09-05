// 运行前启动 canvas_startup_fixture.py；仅对隔离 fixture 操作，不提交生成请求。
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async()=>{
    const base = process.argv[2] || 'http://127.0.0.1:3013';
    const artifacts = process.argv[3] || '测试/画布资源与节点回归-20260905';
    fs.mkdirSync(artifacts,{recursive:true});
    const browser = await chromium.launch({headless:true,channel:'chrome'});
    try {
        const page = await browser.newPage({viewport:{width:1440,height:1000}});
        const errors = [], layouts = [];
        let fullRenders=0;
        page.on('pageerror',error=>errors.push(error.message));
        page.on('console',message=>{ if(message.text().startsWith('[fixture-render]')) fullRenders++; });
        const url = `${base}/static/canvas.html?id=node-ui-${Date.now()}&canvasPerf=1`;
        await page.goto(url);
        await page.waitForSelector('.poseReplicate-node');
        await page.waitForTimeout(250);
        assert.equal(fullRenders,1,'component status must not rebuild the entire canvas');
        assert.equal(await page.evaluate(async()=>{
            const image=document.querySelector('.image-node img');
            queueClassicSpecialRefresh(nodes.find(n=>n.id==='pose'));
            queueClassicSpecialRefresh(nodes.find(n=>n.id==='depth'));
            await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
            return image===document.querySelector('.image-node img');
        }),true,'unrelated media DOM remains connected');
        await page.evaluate(()=>{
            const pose=nodes.find(n=>n.id==='pose');
            pose.poseReplicateManualInputs={'target-image':[
                {url:'/fixture.png?garment=red',name:'red.png',kind:'image'},
                {url:'/fixture.png?garment=blue',name:'blue.png',kind:'image'}
            ]};
            refreshNodes(['pose']);
        });
        const poseNode=page.locator('.poseReplicate-node');
        assert.equal(await poseNode.locator('[data-pose-replicate-input-role="pose-reference"] strong').textContent(),'目标图片');
        assert.equal(await poseNode.locator('[data-pose-replicate-input-role="target-image"] strong').textContent(),'服装参考');
        assert.equal(await poseNode.locator('.pose-replicate-target-thumb').count(),2);
        assert.equal(await poseNode.locator('input[data-pose-replicate-file="target-image"]').getAttribute('multiple'),'');
        // 同一通用框架覆盖普通图片、批量图片和视频生成节点。
        await page.evaluate(()=>{
            const original=nodes.find(n=>n.id==='generator');
            nodes.push({...original,id:'batch',type:'batchGenerator',x:0,y:1300});render();
        });
        for(const id of ['generator','video','batch']){
            await page.evaluate(id=>{ const node=nodes.find(n=>n.id===id);viewport.x=40-node.x*.5;viewport.y=40-node.y*.5;applyViewport(); },id);
            const node=page.locator(`.node[data-id="${id}"]`);
            const before=await node.boundingBox();
            const handle=await node.locator('.resize-handle').boundingBox();
            await page.mouse.move(handle.x+handle.width/2,handle.y+handle.height/2);
            await page.mouse.down();
            await page.mouse.move(handle.x+handle.width/2+35,handle.y+handle.height/2+110,{steps:5});
            await page.mouse.up();
            const result=await node.evaluate(el=>{
                const rect=el.getBoundingClientRect(), shell=el.querySelector('.node-visual-shell').getBoundingClientRect();
                const body=el.querySelector('.node-body');
                const run=el.querySelector('.gen-run-row').getBoundingClientRect();
                const controls=el.querySelector('.node-bottom-controls').getBoundingClientRect();
                return {height:rect.height,width:rect.width,shellHeight:shell.height,bottomGap:rect.bottom-controls.bottom,buttonBottom:run.bottom,frameBottom:rect.bottom,scrollWidth:body.scrollWidth,clientWidth:body.clientWidth};
            });
            assert.ok(result.height>before.height+90,`${id} must retain manually increased height`);
            assert.ok(Math.abs(result.height-result.shellHeight)<1,`${id} shell fills the frame`);
            assert.ok(result.bottomGap>=0 && result.bottomGap<16,`${id} bottom controls remain inside frame and at bottom`);
            assert.ok(result.buttonBottom<result.frameBottom,`${id} button fits`);
            assert.ok(result.scrollWidth<=result.clientWidth+1,`${id} no horizontal overflow`);
            layouts.push({id,...result});
            await page.screenshot({path:path.join(artifacts,`resize-${id}.png`)});
            // 缩小到下限，内容可滚动且仍在完整框架中。
            await page.evaluate(id=>{
                const n=nodes.find(n=>n.id===id);startNodeResize({preventDefault(){},stopPropagation(){},clientX:0,clientY:0},n);
                onNodeResize({clientX:-1000,clientY:-1000});endDrag();
            },id);
            assert.equal(await node.evaluate(el=>el.querySelector('.node-body').scrollHeight>=el.querySelector('.node-body').clientHeight),true);
        }
        await page.evaluate(()=>{const pose=nodes.find(n=>n.id==='pose');pose.x=0;pose.y=2400;viewport.x=40;viewport.y=40-pose.y*.5;render();});
        await page.getByRole('button',{name:'一键复刻提示词设置',exact:true}).click();
        const cards=page.locator('.pose-template-card');await cards.first().waitFor();assert.equal(await cards.count(),8);
        await cards.first().click();
        const editor=page.getByRole('textbox',{name:'组合完整提示词'});
        const full=await page.locator('.pose-template-dialog').boundingBox();assert.equal(full.width,1440);assert.equal(full.height,1000);
        const custom='自定义测试：保持结构，改变服装映射。\n{{output_aspect_ratio}}\n{{user_instruction}}\n<literal & text>';
        await editor.fill(custom);
        assert.equal(await page.evaluate(()=>nodes.find(n=>n.id==='pose').poseReplicatePromptTemplates['depth:base-wardrobe']),custom);
        await editor.fill('');await page.getByRole('button',{name:'完成编辑',exact:true}).click();
        assert.equal(await editor.isVisible(),true);
        assert.equal(await page.evaluate(()=>nodes.find(n=>n.id==='pose').poseReplicatePromptTemplates['depth:base-wardrobe']),custom);
        await editor.fill(custom);await page.getByRole('button',{name:'完成编辑',exact:true}).click();
        await page.getByRole('button',{name:'关闭提示词设置',exact:true}).click();
        await page.evaluate(()=>saveCanvas());
        await page.reload();await page.waitForSelector('.poseReplicate-node');
        assert.equal(await page.evaluate(()=>nodes.find(n=>n.id==='pose').poseReplicatePromptTemplates['depth:base-wardrobe']),custom);
        for(const theme of ['light','dark','pure-white']){
            await page.evaluate(theme=>localStorage.setItem('studio_theme',theme),theme);
            await page.reload();await page.waitForSelector('.poseReplicate-node');
            await page.getByRole('button',{name:'一键复刻提示词设置',exact:true}).click();await cards.first().waitFor();
            await page.screenshot({path:path.join(artifacts,`templates-${theme}.png`)});
            await cards.first().click();assert.equal(await editor.inputValue(),custom);
            await page.screenshot({path:path.join(artifacts,`editor-${theme}.png`)});
            await page.keyboard.press('Escape');await page.keyboard.press('Escape');
        }
        await page.setViewportSize({width:720,height:920});
        await page.evaluate(()=>{const pose=nodes.find(n=>n.id==='pose');viewport.x=60;viewport.y=180-pose.y*viewport.scale;applyViewport();});
        await page.getByRole('button',{name:'一键复刻提示词设置',exact:true}).click();await cards.first().waitFor();await cards.first().click();
        await page.screenshot({path:path.join(artifacts,'editor-mobile.png')});
        assert.equal(await page.locator('.pose-template-dialog').evaluate(el=>el.scrollWidth<=el.clientWidth),true);
        await page.getByRole('button',{name:'恢复此组合默认值',exact:true}).click();
        assert.equal(await page.evaluate(()=>Object.keys(nodes.find(n=>n.id==='pose').poseReplicatePromptTemplates).length),0);
        await page.keyboard.press('Escape');await page.keyboard.press('Escape');
        assert.deepEqual(errors,[]);
        const report={layouts,initialFullRenders:1,templateCombinations:8,themes:['light','dark','pure-white'],fullScreen:[1440,1000],narrowScreen:[720,920],persisted:true,errors};
        fs.writeFileSync(path.join(artifacts,'ui-results.json'),JSON.stringify(report,null,2));
        console.log(JSON.stringify(report));
    } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
