const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('playwright');

(async () => {
    const browser = await chromium.launch({headless:true, channel:process.env.PLAYWRIGHT_CHANNEL || 'msedge'});
    try {
        const page = await browser.newPage({viewport:{width:1100,height:900}});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('http://fixture.local/**', route => route.fulfill({body:'<div id="node" style="width:700px;margin:40px"></div>',contentType:'text/html'}));
        await page.goto('http://fixture.local/');
        await page.addStyleTag({content:':root{--text:#eee;--muted:#999;--faint:#999;--line:#444;--soft:#303030;--card-solid:#262626;--panel:#262626}body{background:#202020;color:#eee;font:13px sans-serif}'});
        for(const path of ['static/css/canvas-special-nodes.css','static/css/pose-replicate-node.css']) await page.addStyleTag({content:fs.readFileSync(path,'utf8')});
        await page.evaluate(() => {
            const canvas = document.createElement('canvas'); canvas.width=64; canvas.height=64;
            const context = canvas.getContext('2d'); context.fillStyle='#808080'; context.fillRect(0,0,64,64);
            window.baseImage = canvas.toDataURL(); window.uploads=[]; window.generated=[]; window.notices=[];
            const nativeFetch = window.fetch;
            window.fetch = async (url, options={}) => {
                if(url==='/api/app-settings') return Response.json({depth_map_mode:'person',depth_model_preference:'auto'});
                if(url==='/api/person-depth/component/status') return Response.json({ready:true,state:'ready'});
                if(url==='/api/ai/upload'){
                    const blob=options.body.get('files');const image=await createImageBitmap(blob);
                    const output=document.createElement('canvas');output.width=image.width;output.height=image.height;
                    const ctx=output.getContext('2d');ctx.drawImage(image,0,0);
                    const result={url:output.toDataURL(),natural_w:image.width,natural_h:image.height,name:'adjusted.png'};
                    window.uploads.push({pixel:ctx.getImageData(0,0,1,1).data[0],result});
                    return Response.json({files:[result]});
                }
                if(String(url).startsWith('/api/')) throw Error('Unexpected API '+url);
                return nativeFetch(url,options);
            };
        });
        await page.addScriptTag({content:fs.readFileSync('static/js/canvas-special-nodes.js','utf8')});
        await page.evaluate(async () => {
            await window.CanvasSpecialNodes.refreshDepthMapSettings();
            const action={url:baseImage,name:'target.png',natural_w:64,natural_h:64};
            window.fixtureNode={id:'pose-test',type:'poseReplicate',poseReplicateSchemaVersion:2,poseReplicateMode:'depth',poseReplicateProvider:'shiying',poseReplicateModel:'model-a',poseReplicateManualInputs:{'pose-reference':action,'target-image':[{...action,name:'clothes.png'}]},poseReferenceSignature:`${baseImage}|target.png|64x64`,poseDepthUrl:baseImage,poseDepthBaseUrl:baseImage,poseDepthBaseWidth:64,poseDepthBaseHeight:64,poseDepthStatus:'done',poseDepthSharedConfigSignature:'person|auto|0|100|0|100|0|0|0',poseDepthSourceSignature:`depth|person|${baseImage}|target.png|64x64`};
            const providers=[{id:'shiying',name:'shiying',models:['model-a','model-b']},{id:'second',name:'平台二',models:['model-c']}];
            let queued=false;
            window.renderFixture=()=>{
                const root=document.getElementById('node');
                root.innerHTML=CanvasSpecialNodes.poseReplicateBodyHtml(fixtureNode,{providers});
                CanvasSpecialNodes.bindPoseReplicate(root,fixtureNode,{
                    smart:fixtureNode.specialType==='pose-replicate',
                    toast:message=>notices.push(message),
                    onChange:(_node,meta)=>{if(meta.render&&!queued){queued=true;requestAnimationFrame(()=>{queued=false;renderFixture();});}},
                    generatePoseReplicate:async (_node,inputs)=>generated.push(inputs)
                });
            };
            renderFixture();
        });
        const platform=page.locator('[data-pose-platform-trigger]');
        await platform.click();
        await page.locator('[data-provider-id="second"]').click();
        await page.locator('[data-model-list] button').click();
        await page.waitForFunction(()=>fixtureNode.poseReplicateProvider==='second'&&fixtureNode.poseReplicateModel==='model-c');
        assert.equal(await page.locator('[data-pose-replicate-field="poseReplicateModel"]').count(),0);
        await page.locator('[data-special-action="pose-depth-controls"]').click();
        await page.locator('[data-depth-control-field="brightness"]').fill('25');
        await page.waitForFunction(()=>uploads.length>0&&fixtureNode.poseDepthControls?.brightness===25&&fixtureNode.poseDepthUrl!==baseImage);
        assert.ok(await page.evaluate(()=>uploads.at(-1).pixel>180),'actual PNG pixels must change');
        await page.locator('[data-depth-control-action="close"]').last().click();
        await page.locator('[data-special-action="run-pose-replicate"]').click();
        await page.waitForFunction(()=>generated.length===1);
        assert.equal(await page.evaluate(()=>generated[0].control.url===fixtureNode.poseDepthUrl),true);
        await page.evaluate(()=>{fixtureNode=JSON.parse(JSON.stringify(fixtureNode));fixtureNode.specialType='pose-replicate';renderFixture();});
        await page.locator('[data-special-action="pose-depth-controls"]').click();
        assert.equal(await page.locator('[data-depth-control-field="brightness"]').inputValue(),'25');
        await page.locator('[data-depth-control-action="reset"]').click();
        await page.waitForFunction(()=>fixtureNode.poseDepthUrl===baseImage&&fixtureNode.poseDepthControls.brightness===0);
        await page.keyboard.press('Escape');
        if(process.env.POSE_SCREENSHOT) await page.screenshot({path:process.env.POSE_SCREENSHOT,fullPage:true});
        await page.locator('[data-pose-replicate-field="poseReplicateMode"]').selectOption('skeleton');
        await page.waitForFunction(()=>document.querySelector('[data-special-action="pose-depth-controls"]').disabled);
        await page.setViewportSize({width:390,height:800});
        await page.evaluate(()=>{document.getElementById('node').style='width:360px;margin:0';});
        await platform.click();
        const bounds=await page.locator('.pose-replicate-platform-menu').boundingBox();
        assert.ok(bounds.x>=0&&bounds.x+bounds.width<=390,'menu must fit viewport');
        await page.keyboard.press('Escape');
        assert.equal(await page.locator('.pose-replicate-platform-menu').count(),0);
        assert.deepEqual(errors,[]);
        console.log('PASS: real node cascade, depth PNG adjustment, generation input, persistence, reset, mode and menu bounds');
    } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
