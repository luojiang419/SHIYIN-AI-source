const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async()=>{
    const base = process.argv[2] || 'http://127.0.0.1:3014';
    const artifacts = process.argv[3] || '.codex-artifacts/089-video-node-layout';
    fs.mkdirSync(artifacts,{recursive:true});
    const browser = await chromium.launch({headless:true,channel:'chrome'});
    try {
        const page = await browser.newPage({viewport:{width:1440,height:1000}});
        const errors=[];
        page.on('pageerror',error=>errors.push(error.message));
        await page.goto(`${base}/static/canvas.html?id=video-layout-${Date.now()}`);
        await page.waitForSelector('.node[data-id="h3"]');
        await page.evaluate(()=>{
            const h3=nodes.find(node=>node.id==='h3');
            h3.h=320;
            h3.duration=0;
            h3.aspectRatio='';
            h3.resolution='';
            for(let index=0;index<12;index+=1){
                const id=`video-ref-${index}`;
                nodes.push({id,type:'image',x:0,y:1800+index*20,url:`/fixture.png?video-ref=${index}`,name:`ref-${index}.png`,width:512,height:512});
                connections.push({id:`video-link-${index}`,from:id,to:h3.id});
            }
            syncGeneratorInputs();
            render();
            viewport.x=80-h3.x*viewport.scale;
            viewport.y=70-h3.y*viewport.scale;
            applyViewport();
        });
        await page.waitForTimeout(300);
        const layout=await page.locator('.node[data-id="h3"]').evaluate(el=>{
            const frame=el.getBoundingClientRect();
            const shell=el.querySelector('.node-visual-shell').getBoundingClientRect();
            const body=el.querySelector('.node-body');
            const content=el.querySelector('.generator-canvas-content');
            const controls=el.querySelector('.node-bottom-controls');
            const button=el.querySelector('.gen-btn');
            const controlsRect=controls.getBoundingClientRect();
            const buttonRect=button.getBoundingClientRect();
            const state=nodes.find(node=>node.id==='h3');
            return {
                nodeHeight:el.offsetHeight,
                frameHeight:frame.height,
                shellHeight:shell.height,
                bodyClientHeight:body.clientHeight,
                bodyScrollHeight:body.scrollHeight,
                bodyOverflow:getComputedStyle(body).overflow,
                contentClientHeight:content.clientHeight,
                contentScrollHeight:content.scrollHeight,
                contentOverflowY:getComputedStyle(content).overflowY,
                contentWheelBound:typeof content.onwheel==='function',
                footerFlexShrink:getComputedStyle(controls).flexShrink,
                controlsInside:controlsRect.top>=frame.top && controlsRect.bottom<=frame.bottom+1,
                buttonInside:buttonRect.top>=frame.top && buttonRect.bottom<=frame.bottom+1,
                buttonVisible:getComputedStyle(button).display!=='none' && buttonRect.height>0,
                duration:state.duration,
                aspectRatio:state.aspectRatio,
                resolution:state.resolution,
                storedHeight:state.h,
            };
        });
        const created=await page.evaluate(()=>{
            const index=apiProviders.findIndex(provider=>provider.id==='minimax-h3');
            if(index>0) apiProviders.unshift(...apiProviders.splice(index,1));
            const node=addVideoNode({x:2100,y:700});
            return {provider:node.apiProvider,model:node.model,duration:node.duration,aspectRatio:node.aspectRatio,resolution:node.resolution,h:node.h};
        });

        assert.equal(layout.nodeHeight,700,'legacy short video node must normalize to 700px');
        assert.ok(Math.abs(layout.frameHeight-layout.shellHeight)<1,'video shell must fill the frame');
        assert.equal(layout.bodyOverflow,'hidden','video node body must not scroll the fixed footer');
        assert.equal(layout.contentOverflowY,'auto','only the media content region should scroll');
        assert.equal(layout.contentWheelBound,true,'media scrolling must not bubble into canvas zoom');
        assert.ok(layout.contentScrollHeight>layout.contentClientHeight,'many references must scroll inside content region');
        assert.equal(layout.footerFlexShrink,'0','video controls must not collapse');
        assert.equal(layout.controlsInside,true,'video controls must stay inside the node frame');
        assert.equal(layout.buttonInside,true,'generate button must stay inside the node frame');
        assert.equal(layout.buttonVisible,true,'generate button must remain visible');
        assert.deepEqual(
            {duration:layout.duration,aspectRatio:layout.aspectRatio,resolution:layout.resolution,storedHeight:layout.storedHeight},
            {duration:5,aspectRatio:'16:9',resolution:'0.2MP 16:9 - 608x352',storedHeight:700},
        );
        assert.deepEqual(created,{
            provider:'minimax-h3',model:'MiniMax H3',duration:5,aspectRatio:'16:9',resolution:'0.2MP 16:9 - 608x352',h:undefined,
        });
        const promptLayouts=[];
        const input=page.locator('.node[data-id="h3"] .generator-prompt-input');
        const longPrompt='subject_definitions:\n'+'A woman approaches the court, turns and steps forward.\n'.repeat(100);
        for(const scenario of [
            {prompt:longPrompt}, {prompt:'短提示词'}, {prompt:''},
            {prompt:longPrompt,w:200,h:320}, {prompt:longPrompt,w:520,h:700},
            {prompt:longPrompt,w:440,h:1000}, {prompt:longPrompt,w:440,h:700},
            {prompt:longPrompt,w:440,h:700,runStatus:'failed',_cascadeFailed:true,runError:'布局回归测试'},
        ]){
            const {prompt}=scenario;
            if(scenario.w) await page.evaluate(scenario=>{
                Object.assign(nodes.find(node=>node.id==='h3'),scenario);
                render();
            },scenario);
            await input.fill(prompt);
            await page.waitForTimeout(100);
            const measured=await page.locator('.node[data-id="h3"]').evaluate(el=>{
                const frame=el.getBoundingClientRect();
                const button=el.querySelector('.gen-btn');
                const rect=button.getBoundingClientRect();
                const input=el.querySelector('.generator-prompt-input');
                const editorRect=input.getBoundingClientRect();
                const wrapRect=input.parentElement.getBoundingClientRect();
                const retry=el.querySelector('.node-retry-bar');
                return {height:el.offsetHeight,width:el.offsetWidth,buttonInside:rect.bottom<=frame.bottom,
                    buttonHittable:button.contains(document.elementFromPoint(rect.x+rect.width/2,rect.y+rect.height/2)),
                    promptInside:editorRect.bottom<=wrapRect.bottom+1,
                    retryInside:!retry||retry.getBoundingClientRect().bottom<=frame.bottom,
                    promptClientHeight:input.clientHeight,promptScrollHeight:input.scrollHeight,
                    mediaHeight:el.querySelector('.generator-canvas-content').clientHeight};
            });
            promptLayouts.push(measured);
            assert.equal(measured.height,Math.max(700,scenario.h||700),'editing prompts must preserve the fixed frame');
            assert.equal(measured.width,Math.max(440,scenario.w||440));
            assert.equal(measured.buttonInside,true,'long prompts must not push generate outside the frame');
            assert.equal(measured.buttonHittable,true,'generate must remain reachable without scrolling the footer');
            assert.equal(measured.promptInside,true,'editor must fit the available prompt area');
            assert.equal(measured.retryInside,true,'retry controls must stay inside the frame');
            assert.ok(measured.mediaHeight>=64,'media region must retain its minimum height');
            if(prompt.length>1000) assert.ok(measured.promptScrollHeight>measured.promptClientHeight,'long prompts must scroll inside the editor');
        }
        assert.deepEqual(errors,[]);
        await page.evaluate(()=>{
            const h3=nodes.find(node=>node.id==='h3');
            h3.runStatus='';h3._cascadeFailed=false;
            document.body.classList.add('theme-dark');
            viewport.scale=1;viewport.x=500-h3.x;viewport.y=150-h3.y;
            render();applyViewport();
        });
        await page.screenshot({path:path.join(artifacts,'h3-fixed-footer.png'),fullPage:true});
        const report={layout,created,promptLayouts,errors};
        fs.writeFileSync(path.join(artifacts,'report.json'),JSON.stringify(report,null,2));
        console.log(JSON.stringify(report));
    } finally {
        await browser.close();
    }
})().catch(error=>{console.error(error);process.exitCode=1;});
