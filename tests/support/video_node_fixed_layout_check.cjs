const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async()=>{
    const base = process.argv[2] || 'http://127.0.0.1:3014';
    const artifacts = process.argv[3] || '.codex-artifacts/112-video-node-compact-layout';
    fs.mkdirSync(artifacts,{recursive:true});
    const browser = await chromium.launch({headless:true,channel:'chrome'});
    try {
        const page = await browser.newPage({viewport:{width:1440,height:1000}});
        const errors=[];
        page.on('pageerror',error=>errors.push(error.message));
        await page.goto(`${base}/static/canvas.html?id=video-layout-${Date.now()}`);
        await page.waitForSelector('.node[data-id="h3"]');
        const setReferences = async (count, storedHeight=null) => {
            await page.evaluate(({count,storedHeight})=>{
                nodes=nodes.filter(node=>!String(node.id).startsWith('video-ref-'));
                connections=connections.filter(connection=>!String(connection.id).startsWith('video-link-'));
                const h3=nodes.find(node=>node.id==='h3');
                if(storedHeight == null) delete h3.h;
                else h3.h=storedHeight;
                for(let index=0;index<count;index+=1){
                    const id=`video-ref-${index}`;
                    nodes.push({id,type:'image',x:0,y:1800+index*20,url:`/fixture.png?video-ref=${index}`,name:`ref-${index}.png`,width:512,height:512});
                    connections.push({id:`video-link-${index}`,from:id,to:h3.id});
                }
                syncGeneratorInputs();
                render();
                viewport.scale=1;
                viewport.x=80-h3.x;
                viewport.y=60-h3.y;
                applyViewport();
            },{count,storedHeight});
            await page.waitForTimeout(120);
            return page.locator('.node[data-id="h3"]').evaluate(el=>{
                const frame=el.getBoundingClientRect();
                const shell=el.querySelector('.node-visual-shell').getBoundingClientRect();
                const body=el.querySelector('.node-body');
                const content=el.querySelector('.generator-canvas-content');
                const list=el.querySelector('.video-img-list');
                const controls=el.querySelector('.node-bottom-controls');
                const button=el.querySelector('.gen-btn');
                const items=[...el.querySelectorAll('.video-input-item')];
                const itemRects=items.map(item=>item.getBoundingClientRect());
                const thumbRects=items.map(item=>item.querySelector('.video-input-thumb').getBoundingClientRect());
                const rowTops=[];
                itemRects.forEach(rect=>{
                    if(!rowTops.some(top=>Math.abs(top-rect.top)<1)) rowTops.push(rect.top);
                });
                const controlsRect=controls.getBoundingClientRect();
                const buttonRect=button.getBoundingClientRect();
                const contentRect=content.getBoundingClientRect();
                const listRect=list.getBoundingClientRect();
                const listStyle=getComputedStyle(list);
                const contentStyle=getComputedStyle(content);
                const state=nodes.find(node=>node.id==='h3');
                return {
                    count:items.length,
                    nodeHeight:el.offsetHeight,
                    frameHeight:frame.height,
                    shellHeight:shell.height,
                    storedHeight:state.h,
                    autoHeight:el.classList.contains('auto-height-node'),
                    sized:el.classList.contains('sized'),
                    rowCount:rowTops.length,
                    firstRowCount:itemRects.filter(rect=>Math.abs(rect.top-rowTops[0])<1).length,
                    columnGap:parseFloat(listStyle.columnGap),
                    rowGap:parseFloat(listStyle.rowGap),
                    listFlexShrink:listStyle.flexShrink,
                    contentFlexShrink:contentStyle.flexShrink,
                    contentOverflow:contentStyle.overflow,
                    bodyOverflow:getComputedStyle(body).overflow,
                    thumbWidths:thumbRects.map(rect=>rect.width),
                    thumbHeights:thumbRects.map(rect=>rect.height),
                    mediaBeforeControls:listRect.bottom<=controlsRect.top+1 && contentRect.bottom<=controlsRect.top+1,
                    controlsInside:controlsRect.top>=frame.top && controlsRect.bottom<=frame.bottom+1,
                    buttonInside:buttonRect.top>=frame.top && buttonRect.bottom<=frame.bottom+1,
                    buttonHittable:button.contains(document.elementFromPoint(buttonRect.x+buttonRect.width/2,buttonRect.y+buttonRect.height/2)),
                    duration:state.duration,
                    aspectRatio:state.aspectRatio,
                    resolution:state.resolution,
                };
            });
        };

        const layouts={};
        layouts.three=await setReferences(3,1000);
        await page.evaluate(()=>document.body.classList.add('theme-dark'));
        await page.screenshot({path:path.join(artifacts,'h3-compact-three-inputs.png'),fullPage:true});
        layouts.six=await setReferences(6,700);
        layouts.seven=await setReferences(7,320);
        layouts.twelve=await setReferences(12,1000);
        const created=await page.evaluate(()=>{
            const index=apiProviders.findIndex(provider=>provider.id==='minimax-h3');
            if(index>0) apiProviders.unshift(...apiProviders.splice(index,1));
            const node=addVideoNode({x:2100,y:700});
            return {provider:node.apiProvider,model:node.model,duration:node.duration,aspectRatio:node.aspectRatio,resolution:node.resolution,h:node.h};
        });

        for(const layout of Object.values(layouts)){
            assert.ok(Math.abs(layout.frameHeight-layout.shellHeight)<1,'video shell must follow its content-driven frame');
            assert.equal(layout.storedHeight,undefined,'legacy stored heights must be removed');
            assert.equal(layout.autoHeight,true,'video node must use auto-height layout');
            assert.equal(layout.sized,false,'video node must not retain the fixed-size layout');
            assert.equal(layout.columnGap,8,'thumbnail columns must keep an 8px gap');
            assert.equal(layout.rowGap,12,'thumbnail rows must keep a 12px gap');
            assert.equal(layout.listFlexShrink,'0','thumbnail grid must never collapse');
            assert.equal(layout.contentFlexShrink,'0','media region must never compete for height with controls');
            assert.equal(layout.contentOverflow,'visible','all thumbnail rows must remain visible without internal scrolling');
            assert.ok(layout.thumbWidths.every(width=>width>50),'six thumbnails must remain readable at minimum node width');
            assert.ok(layout.thumbWidths.every((width,index)=>Math.abs(width-layout.thumbHeights[index])<1),'all thumbnails must stay square');
            assert.equal(layout.mediaBeforeControls,true,'media rows must finish before settings begin');
            assert.equal(layout.controlsInside,true,'settings must stay inside the natural node frame');
            assert.equal(layout.buttonInside,true,'generate button must stay inside the natural node frame');
            assert.equal(layout.buttonHittable,true,'generate button must remain reachable');
        }
        assert.ok(layouts.three.nodeHeight<700,'three references must not leave a meaningless 700px frame');
        assert.equal(layouts.three.rowCount,1);
        assert.equal(layouts.six.rowCount,1);
        assert.equal(layouts.six.firstRowCount,6);
        assert.equal(layouts.seven.rowCount,2);
        assert.equal(layouts.seven.firstRowCount,6);
        assert.equal(layouts.twelve.rowCount,2);
        assert.equal(layouts.twelve.firstRowCount,6);
        assert.ok(layouts.seven.nodeHeight>layouts.six.nodeHeight,'the seventh reference must add a natural second row');
        assert.ok(Math.abs(layouts.seven.nodeHeight-layouts.twelve.nodeHeight)<2,'seven and twelve references must occupy the same two-row height');
        assert.ok(Math.abs(layouts.three.thumbWidths[0]-layouts.twelve.thumbWidths[0])<1,'thumbnail size must not change with row count');
        assert.deepEqual(
            {duration:layouts.twelve.duration,aspectRatio:layouts.twelve.aspectRatio,resolution:layouts.twelve.resolution},
            {duration:5,aspectRatio:'16:9',resolution:'0.2MP 16:9 - 608x352'},
        );
        assert.deepEqual(created,{
            provider:'minimax-h3',model:'MiniMax H3',duration:5,aspectRatio:'16:9',resolution:'0.2MP 16:9 - 608x352',h:undefined,
        });

        const input=page.locator('.node[data-id="h3"] .generator-prompt-input');
        const longPrompt='subject_definitions:\n'+'A woman approaches the court, turns and steps forward.\n'.repeat(100);
        await input.fill(longPrompt);
        await page.waitForTimeout(100);
        const promptLayout=await page.locator('.node[data-id="h3"]').evaluate(el=>{
            const frame=el.getBoundingClientRect();
            const button=el.querySelector('.gen-btn');
            const buttonRect=button.getBoundingClientRect();
            const input=el.querySelector('.generator-prompt-input');
            return {
                height:el.offsetHeight,
                buttonInside:buttonRect.bottom<=frame.bottom+1,
                buttonHittable:button.contains(document.elementFromPoint(buttonRect.x+buttonRect.width/2,buttonRect.y+buttonRect.height/2)),
                promptClientHeight:input.clientHeight,
                promptScrollHeight:input.scrollHeight,
            };
        });
        assert.ok(Math.abs(promptLayout.height-layouts.twelve.nodeHeight)<2,'long prompts must not stretch the compact node');
        assert.equal(promptLayout.buttonInside,true,'long prompts must not push generate outside the frame');
        assert.equal(promptLayout.buttonHittable,true,'generate must remain reachable with a long prompt');
        assert.ok(promptLayout.promptScrollHeight>promptLayout.promptClientHeight,'long prompts must scroll inside the editor');
        assert.deepEqual(errors,[]);
        await page.evaluate(()=>{
            const h3=nodes.find(node=>node.id==='h3');
            document.body.classList.add('theme-dark');
            viewport.scale=1;viewport.x=500-h3.x;viewport.y=150-h3.y;
            render();applyViewport();
        });
        await page.screenshot({path:path.join(artifacts,'h3-compact-two-row-grid.png'),fullPage:true});
        const report={layouts,created,promptLayout,errors};
        fs.writeFileSync(path.join(artifacts,'report.json'),JSON.stringify(report,null,2));
        console.log(JSON.stringify(report));
    } finally {
        await browser.close();
    }
})().catch(error=>{console.error(error);process.exitCode=1;});
