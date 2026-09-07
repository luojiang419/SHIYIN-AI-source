const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async()=>{
    const base = process.argv[2] || 'http://127.0.0.1:3015';
    const artifacts = process.argv[3] || '.codex-artifacts/113-video-model-switch-layout';
    fs.mkdirSync(artifacts,{recursive:true});
    const browser = await chromium.launch({headless:true,channel:'chrome'});
    try {
        const page = await browser.newPage({viewport:{width:1600,height:1200}});
        const errors=[];
        page.on('pageerror',error=>errors.push(error.message));
        await page.goto(`${base}/static/canvas.html?id=video-model-layout-${Date.now()}`);
        await page.waitForSelector('.node[data-id="h3"]');
        await page.evaluate(()=>{
            const upsertProvider = provider => {
                const index=apiProviders.findIndex(item=>item.id===provider.id);
                if(index>=0) apiProviders.splice(index,1,provider);
                else apiProviders.push(provider);
            };
            upsertProvider({id:'kling-cli',name:'可灵 CLI',enabled:true,video_models:['kling-v3-omni']});
            upsertProvider({id:'linkfox',name:'LinkFox',enabled:true,video_models:['海螺2.3']});
            const argumentsList=[
                {name:'duration',allowed_values:['3','5','10','15'],default:'5',required:true,description:'视频时长'},
                {name:'aspect_ratio',allowed_values:['16:9','9:16','1:1'],default:'16:9',description:'输出画幅比例'},
                {name:'resolution',allowed_values:['720p','1080p'],default:'1080p',description:'输出分辨率'},
                {name:'imageCount',allowed_values:['1','2','3','4'],default:'1',description:'生成数量'},
                {name:'prefer_multi_shots',allowed_values:['true','false'],default:'false',description:'优先生成多镜头叙事'},
                {name:'enable_audio',allowed_values:['true','false'],default:'true',description:'生成同步声音'},
                {name:'enable_asmr',allowed_values:['true','false'],default:'false',description:'增强环境声音细节'},
                {name:'audio_prompt',default:'',description:'描述环境音与关键音效'},
                {name:'music_prompt',default:'',description:'描述配乐的情绪和节奏'},
            ];
            const spec={model:'kling-v3-omni',alias:'Kling 3.0 Omni',arguments:argumentsList};
            klingCliState={loaded:true,loading:false,installed:true,authenticated:true,generationEnabled:true,canManage:true,version:'fixture',error:'',capabilities:{text_to_video:[spec],image_to_video:[spec],video_elements:[],video_reference_supported:false,video_reference_message:''}};
            updateKlingProviderModels();

            const image=nodes.find(node=>node.id==='image');
            const video=nodes.find(node=>node.id==='h3');
            video.x=720;video.y=80;video.h=1200;video.prompt='固定高度迁移测试\n'.repeat(80);
            video.apiProvider='kling-cli';video.model='kling-v3-omni';video.modelParameters={};
            const film={id:'film-switch',type:'film-video',x:1300,y:80,w:920,h:1500,apiProvider:'kling-cli',model:'kling-v3-omni',modelParameters:{},actorCount:1,prompt:'影视提示词固定在编辑器内部滚动。\n'.repeat(80)};
            nodes.push(film);
            connections.push({id:'video-switch-input',from:image.id,to:video.id});
            connections.push({id:'film-switch-input',from:image.id,to:film.id,inputRole:'storyboard'});
            syncGeneratorInputs();
            render();
            document.body.classList.add('theme-dark');
        });

        const focusNode = async id => {
            await page.evaluate(id=>{
                const node=nodes.find(item=>item.id===id);
                viewport.scale=.65;
                viewport.x=140-(Number(node?.x)||0)*viewport.scale;
                viewport.y=80-(Number(node?.y)||0)*viewport.scale;
                applyViewport();
            },id);
            await page.waitForTimeout(80);
        };
        const switchProvider = async (id, selector, provider) => {
            await focusNode(id);
            await page.locator(`.node[data-id="${id}"] ${selector}`).selectOption(provider);
            await page.waitForFunction(({id,provider})=>nodes.find(node=>node.id===id)?.apiProvider===provider,{id,provider});
            await page.waitForTimeout(140);
            await focusNode(id);
        };
        const measureVideo = id => page.locator(`.node[data-id="${id}"]`).evaluate(el=>{
            const state=nodes.find(node=>node.id===el.dataset.id);
            const frame=el.getBoundingClientRect();
            const shell=el.querySelector('.node-visual-shell').getBoundingClientRect();
            const body=el.querySelector('.node-body');
            const content=el.querySelector('.generator-canvas-content');
            const list=el.querySelector('.video-img-list');
            const controls=el.querySelector('.node-bottom-controls');
            const button=el.querySelector('.gen-btn');
            const buttonRect=button.getBoundingClientRect();
            const listRect=list.getBoundingClientRect();
            const controlsRect=controls.getBoundingClientRect();
            const prompt=el.querySelector('.generator-prompt-input');
            return {
                provider:state.apiProvider,
                model:state.model,
                width:el.offsetWidth,
                height:el.offsetHeight,
                shellHeight:shell.height / .65,
                storedHeight:state.h,
                autoHeight:el.classList.contains('auto-height-node'),
                sized:el.classList.contains('sized'),
                bottomGap:(frame.bottom-controlsRect.bottom)/.65,
                bodyOverflow:getComputedStyle(body).overflowY,
                contentOverflow:getComputedStyle(content).overflowY,
                listFlexShrink:getComputedStyle(list).flexShrink,
                thumbnailCount:list.querySelectorAll('.video-input-item').length,
                thumbnailBeforeControls:listRect.bottom<=controlsRect.top+1,
                buttonInside:buttonRect.bottom<=frame.bottom+1,
                buttonHittable:button.contains(document.elementFromPoint(buttonRect.x+buttonRect.width/2,buttonRect.y+buttonRect.height/2)),
                promptScrolls:prompt.scrollHeight>prompt.clientHeight,
                panel:el.querySelector('.kling-parameter-grid')?'kling':el.querySelector('.film-video-settings-h3')?'h3':el.querySelector('.linkfox-unified-settings')?'linkfox':'other',
            };
        });
        const measureFilm = id => page.locator(`.node[data-id="${id}"]`).evaluate(el=>{
            const state=nodes.find(node=>node.id===el.dataset.id);
            const frame=el.getBoundingClientRect();
            const shell=el.querySelector('.node-visual-shell').getBoundingClientRect();
            const body=el.querySelector('.node-body');
            const panel=el.querySelector('.film-node-panel');
            const scroll=el.querySelector('.film-node-scroll');
            const actions=el.querySelector('.film-node-actions');
            const mapping=el.querySelector('.film-mapping-list');
            const button=el.querySelector('.film-run-button');
            const actionsRect=actions.getBoundingClientRect();
            const buttonRect=button.getBoundingClientRect();
            const prompt=el.querySelector('[data-film-field="prompt"]');
            return {
                provider:state.apiProvider,
                model:state.model,
                width:el.offsetWidth,
                height:el.offsetHeight,
                shellHeight:shell.height/.65,
                storedHeight:state.h,
                autoHeight:el.classList.contains('auto-height-node'),
                sized:el.classList.contains('sized'),
                bottomGap:(frame.bottom-actionsRect.bottom)/.65,
                bodyOverflow:getComputedStyle(body).overflowY,
                scrollOverflow:getComputedStyle(scroll).overflowY,
                scrollFullyVisible:scroll.scrollHeight<=scroll.clientHeight+1,
                panelFullyVisible:panel.scrollHeight<=panel.clientHeight+1,
                mappingCount:mapping?.querySelectorAll('.film-mapping-chip').length||0,
                mappingVisible:Boolean(mapping&&mapping.getBoundingClientRect().height>0),
                buttonInside:buttonRect.bottom<=frame.bottom+1,
                buttonHittable:button.contains(document.elementFromPoint(buttonRect.x+buttonRect.width/2,buttonRect.y+buttonRect.height/2)),
                promptHeight:prompt.offsetHeight,
                promptScrolls:prompt.scrollHeight>prompt.clientHeight,
                panel:el.querySelector('.kling-parameter-grid')?'kling':el.querySelector('.film-video-settings-h3')?'h3':el.querySelector('.film-video-settings-linkfox')?'linkfox':'generic',
            };
        });

        const videoLayouts=[];
        const filmLayouts=[];
        for(const provider of ['kling-cli','minimax-h3','linkfox','kling-cli']){
            await switchProvider('h3','.video-provider',provider);
            videoLayouts.push(await measureVideo('h3'));
            await switchProvider('film-switch','[data-film-field="apiProvider"]',provider);
            filmLayouts.push(await measureFilm('film-switch'));
            await page.screenshot({path:path.join(artifacts,`${provider}-${videoLayouts.length}.png`),fullPage:true});
        }

        for(const layout of videoLayouts){
            assert.equal(layout.storedHeight,undefined,'video must discard every legacy or dragged height');
            assert.equal(layout.autoHeight,true,'video must stay in content-height mode');
            assert.equal(layout.sized,false,'video must not use fixed-size scrolling');
            assert.ok(Math.abs(layout.height-layout.shellHeight)<2,'video shell must fit its frame');
            assert.ok(layout.bottomGap>=0&&layout.bottomGap<16,'video controls must finish at the frame bottom');
            assert.equal(layout.contentOverflow,'visible','video thumbnails must not be folded into a scroll area');
            assert.equal(layout.listFlexShrink,'0','video thumbnail grid must never shrink');
            assert.ok(layout.thumbnailCount>=1&&layout.thumbnailBeforeControls,'video thumbnail grid must remain visible before controls');
            assert.equal(layout.buttonInside,true,'video action must remain inside the frame');
            assert.equal(layout.buttonHittable,true,'video action must remain clickable');
            assert.equal(layout.promptScrolls,true,'long video prompts must scroll inside the editor');
        }
        for(const layout of filmLayouts){
            assert.equal(layout.storedHeight,undefined,'film video must discard every legacy or dragged height');
            assert.equal(layout.autoHeight,true,'film video must use content-height mode');
            assert.equal(layout.sized,false,'film video must not use fixed-size scrolling');
            assert.ok(layout.width>=520&&layout.width<=620,'film video width must stay inside its design limits');
            assert.ok(Math.abs(layout.height-layout.shellHeight)<2,'film video shell must fit its frame');
            assert.ok(layout.bottomGap>=0&&layout.bottomGap<16,'film actions must finish at the frame bottom');
            assert.equal(layout.bodyOverflow,'visible','film video body must remain fully expanded');
            assert.equal(layout.scrollOverflow,'visible','film video content must not be folded into internal scrolling');
            assert.equal(layout.scrollFullyVisible,true,'film video content must remain fully visible');
            assert.equal(layout.panelFullyVisible,true,'film video panel must contain all controls');
            assert.ok(layout.mappingCount>=1&&layout.mappingVisible,'film asset thumbnails must remain visible');
            assert.equal(layout.buttonInside,true,'film video action must remain inside the frame');
            assert.equal(layout.buttonHittable,true,'film video action must remain clickable');
            assert.ok(Math.abs(layout.promptHeight-96)<2,'film prompt editor must keep a stable height');
            assert.equal(layout.promptScrolls,true,'long film prompts must scroll inside the editor');
        }
        assert.deepEqual(videoLayouts.map(layout=>layout.panel),['kling','other','linkfox','kling']);
        assert.deepEqual(filmLayouts.map(layout=>layout.panel),['generic','h3','linkfox','generic']);
        assert.ok(Math.max(...videoLayouts.map(layout=>layout.height))-Math.min(...videoLayouts.map(layout=>layout.height))>40,'video frame must follow different model panel heights');
        assert.ok(Math.max(...filmLayouts.map(layout=>layout.height))-Math.min(...filmLayouts.map(layout=>layout.height))>40,'film frame must follow different model panel heights');
        assert.ok(Math.abs(videoLayouts[0].height-videoLayouts.at(-1).height)<2,'video must return to the original Kling height without retained blank space');
        assert.ok(Math.abs(filmLayouts[0].height-filmLayouts.at(-1).height)<2,'film video must return to the original Kling height without retained blank space');

        const resized=await page.evaluate(()=>{
            const resize=(id,dx,dy)=>{
                const node=nodes.find(item=>item.id===id);
                const el=document.querySelector(`.node[data-id="${id}"]`);
                const before={width:el.offsetWidth,height:el.offsetHeight};
                startNodeResize({preventDefault(){},stopPropagation(){},clientX:0,clientY:0},node);
                onNodeResize({clientX:dx,clientY:dy});
                endDrag();
                return {before,after:{width:el.offsetWidth,height:el.offsetHeight},storedHeight:node.h};
            };
            return {video:resize('h3',2000,900),film:resize('film-switch',2000,900)};
        });
        assert.equal(resized.video.after.width,520);
        assert.equal(resized.film.after.width,620);
        assert.ok(Math.abs(resized.video.after.height-resized.video.before.height)<2);
        assert.ok(Math.abs(resized.film.after.height-resized.film.before.height)<2);
        assert.equal(resized.video.storedHeight,undefined);
        assert.equal(resized.film.storedHeight,undefined);
        assert.deepEqual(errors,[]);

        const report={videoLayouts,filmLayouts,resized,errors};
        fs.writeFileSync(path.join(artifacts,'report.json'),JSON.stringify(report,null,2));
        console.log(JSON.stringify(report));
    } finally {
        await browser.close();
    }
})().catch(error=>{console.error(error);process.exitCode=1;});
