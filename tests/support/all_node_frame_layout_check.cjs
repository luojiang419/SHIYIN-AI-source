// 配合 canvas_startup_fixture.py 使用；仅注入内存节点并测量布局，不提交生成请求。
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const base = process.argv[2] || 'http://127.0.0.1:3016';
const artifacts = process.argv[3] || '.codex-artifacts/115-all-node-frame-layout';
const fixtureImage = '/static/assets/camera-reference/angle-eye-front.png';
fs.mkdirSync(artifacts,{recursive:true});

function frameIssueSummary(items){
    return items.filter(item => item.issues.length).map(item => `${item.id}: ${item.issues.join(', ')}`).join('\n');
}

async function configureClassic(page){
    await page.goto(`${base}/static/canvas.html?id=all-node-frame-${Date.now()}`);
    await page.waitForSelector('.node[data-id="generator"]');
    await page.evaluate(fixtureImage => {
        const image = (id, extra={}) => ({id,type:'image',x:0,y:0,url:fixtureImage,name:`${id}.png`,width:1024,height:1024,...extra});
        const specs = [
            image('image'),
            {id:'prompt',type:'prompt',x:0,y:0,text:'完整框架提示词\n'.repeat(8)},
            {id:'loop',type:'loop',x:0,y:0,count:8,mode:'serial',showPrompt:true,imageInput:true,videoInput:true,loopStart:1,imageBatchSize:2,videoBatchSize:2,variablePrompt:'变量提示词\n'.repeat(4),fixedPrompt:'固定提示词'},
            {id:'group',type:'group',x:0,y:0,w:300,h:220,items:['image']},
            {id:'prompt-group',type:'promptGroup',x:0,y:0,w:360,h:240,items:['prompt']},
            {id:'llm',type:'llm',x:0,y:0,llmProvider:'custom',model:'private-chat',mode:'node',systemPrompt:'You are helpful.',chatInput:'',messages:[],outputText:'',llmInputHeight:110,llmOutputHeight:150,running:false},
            {id:'generator-rich',type:'generator',x:0,y:0,apiProvider:'custom',model:'private-image',prompt:'图片生成提示词',ratio:'wide',resolution:'2k',count:4,inputs:[]},
            {id:'batch-generator',type:'batchGenerator',x:0,y:0,apiProvider:'custom',model:'private-image',prompt:'批量处理提示词',ratio:'source',resolution:'2k',quality:'auto',inputs:[]},
            {id:'modelscope',type:'msgen',x:0,y:0,msgenModel:'zimage',msWidth:1024,msHeight:1024,msCustomModel:'fixture',msRatio:'square',msResolution:'1k',count:1,inputs:[]},
            {id:'video',type:'video',x:0,y:0,apiProvider:'custom',model:'private-video',duration:5,aspectRatio:'16:9',resolution:'1080p',prompt:'视频提示词\n'.repeat(12),inputs:[]},
            {id:'linkfox-video',type:'linkfox-video',x:0,y:0,apiProvider:'linkfox',model:'海螺2.3',duration:5,aspectRatio:'16:9',prompt:'LinkFox 视频提示词',inputs:[]},
            {id:'runninghub',type:'rh',x:0,y:0,w:430,rhMode:'workflow',rhPayment:'free',workflowId:'fixture-workflow',rhParams:{},inputs:[],running:false},
            {id:'lookbook',type:'lookbook',x:0,y:0,lookbookReferences:[],generatedOutputs:[],prompt:'平面广告需求'},
            {id:'ecom-model',type:'ecom-model',x:0,y:0,ecomItems:[{url:fixtureImage,name:'model.png'}],ecomDescription:'保持人物身份与服装细节'},
            {id:'ecom-product',type:'ecom-product',x:0,y:0,ecomItems:[{url:fixtureImage,name:'product.png'}],ecomDescription:'保持商品纹理与 Logo'},
            {id:'ecom-scene',type:'ecom-scene',x:0,y:0,ecomItems:[{url:fixtureImage,name:'scene.png'}],scenePrompt:'干净摄影棚',aspectRatio:'16:9',resolution:'2k',quality:'high'},
            {id:'ecom-compose',type:'ecom-compose',x:0,y:0,instruction:'合成要求\n'.repeat(5),videoPrompt:'视频镜头提示词\n'.repeat(4),aspectRatio:'3:4',resolution:'2k',quality:'high',count:4,inputs:[],generatedOutputs:[fixtureImage]},
            {id:'ecom-video',type:'ecom-video',x:0,y:0,apiProvider:'custom',model:'private-video',duration:5,aspectRatio:'9:16',prompt:'电商视频提示词',inputs:[]},
            {id:'film-prepare',type:'film-prepare-assets',x:0,y:0,title:'准备资产',items:[]},
            {id:'film-confirm',type:'film-confirm-shots',x:0,y:0,title:'确认镜头',items:[]},
            {id:'film-storyboard',type:'film-storyboard',x:0,y:0,apiProvider:'custom',model:'private-image',actorCount:8,prompt:'分镜合成提示词\n'.repeat(6),aspectRatio:'16:9',resolution:'2k',quality:'high',count:4,inputs:[]},
            {id:'film-line-art',type:'film-line-art',x:0,y:0,apiProvider:'custom',model:'private-image',prompt:'线稿分镜提示词',aspectRatio:'source',resolution:'2k',quality:'high',inputs:[]},
            {id:'film-video',type:'film-video',x:0,y:0,apiProvider:'custom',model:'private-video',actorCount:8,prompt:'影视视频提示词\n'.repeat(14),duration:5,aspectRatio:'16:9',resolution:'1080p',inputs:[]},
            {id:'storyboard-merge',type:'storyboardMerge',x:0,y:0,images:Array.from({length:8},(_,index)=>({url:fixtureImage,name:`frame-${index + 1}.png`}))},
            {id:'panorama',type:'panorama',x:0,y:0,w:520,h:520,panoramaPrompt:'测试',panoramaYaw:0,panoramaPitch:0,panoramaFov:72,panoramaAspect:'16:9',panoramaResolution:'1280x720'},
            {id:'dwpose',type:'dwpose',x:0,y:0,w:380,h:390,poseStatus:'idle'},
            {id:'depth-map',type:'depthMap',x:0,y:0,w:520,h:560,depthMapStatus:'idle'},
            {id:'result-compare',type:'resultCompare',x:0,y:0,w:520,h:560,compareDivider:50},
            {id:'director3d',type:'director3d',x:0,y:0,w:460,h:420,directorProject:null,directorCaptures:[]},
            {id:'pose-replicate',type:'poseReplicate',x:0,y:0,w:720,h:820,poseReplicateSchemaVersion:2,poseReplicateMode:'depth',poseReplicateProvider:'custom',poseReplicateModel:'private-image',poseReplicateRatio:'source',poseReplicateResolution:'2k',poseReplicateStatus:'idle',poseStatus:'idle',poseDepthStatus:'idle',poseReplicateRuns:[]},
            {id:'multi-view',type:'multiView',x:0,y:0,w:700,h:780,apiProvider:'custom',model:'private-image',resolution:'2k',quality:'high',multiViewMode:'person',multiViewStatus:'idle',generatedOutputs:[],multiViewOutputs:[]},
            {id:'topaz-video',type:'topazVideo',x:0,y:0,w:400,topazStatus:'idle'},
            {id:'blender-director',type:'blenderDirector',x:0,y:0,w:440,blenderPort:9876,cameraX:0,cameraY:-8,cameraZ:3,rotationX:67,rotationY:0,rotationZ:0,cameraLens:50,cameraFrame:1,cameraSettingsExpanded:true,frameStart:1,frameEnd:120,renderKind:'image',generatedOutputs:[],running:false},
            {id:'output',type:'output',x:0,y:0,images:Array.from({length:10},(_,index)=>({url:fixtureImage,name:`output-${index + 1}.png`,kind:'image'}))},
            {id:'legacy-angle',type:'angle',x:0,y:0,w:460,h:660,angleAzimuth:45,angleElevation:0,angleDistance:'medium',angleLens:'50',angleSubject:'person',anglePreserve:true,angleNotes:''},
        ];
        nodes.splice(0,nodes.length,...specs);
        connections.splice(0,connections.length);
        selected.clear();
        canvas.nodes=nodes;
        canvas.connections=connections;
        render();
        viewport.scale=1; viewport.x=40; viewport.y=40; applyViewport();
    }, fixtureImage);
    await page.waitForTimeout(4500);
}

async function measureClassic(page){
    return page.locator('.node[data-id]').evaluateAll(elements => elements.map(el => {
        const tolerance=2;
        const frame=el.getBoundingClientRect();
        const shell=el.querySelector('.node-visual-shell');
        const shellRect=shell?.getBoundingClientRect();
        const body=el.querySelector('.node-body');
        const bodyStyle=body ? getComputedStyle(body) : null;
        const issues=[];
        if(!shellRect) issues.push('missing-shell');
        else {
            if(Math.abs(frame.width-shellRect.width)>tolerance) issues.push('shell-width');
            if(Math.abs(frame.height-shellRect.height)>tolerance) issues.push('shell-height');
        }
        if(body){
            const horizontalOverflow=body.scrollWidth>body.clientWidth+tolerance;
            const verticalOverflow=body.scrollHeight>body.clientHeight+tolerance;
            if(horizontalOverflow&&!['auto','scroll'].includes(bodyStyle.overflowX)) issues.push('horizontal-clipping');
            if(verticalOverflow&&!['auto','scroll'].includes(bodyStyle.overflowY)) issues.push('vertical-clipping');
            const bodyRect=body.getBoundingClientRect();
            if(bodyRect.left<frame.left-tolerance||bodyRect.right>frame.right+tolerance) issues.push('body-outside-frame');
        }
        const controls=[...el.querySelectorAll('button,input,select,textarea')].filter(control => {
            const style=getComputedStyle(control);
            return style.display!=='none'&&style.visibility!=='hidden'&&control.getClientRects().length;
        });
        if(controls.some(control => {
            const rect=control.getBoundingClientRect();
            return rect.width>0&&(rect.left<frame.left-tolerance||rect.right>frame.right+tolerance);
        })) issues.push('control-horizontal-overflow');
        return {
            id:el.dataset.id,
            type:[...el.classList].find(name=>name.endsWith('-node'))||'',
            width:Math.round(frame.width),height:Math.round(frame.height),
            shellHeight:Math.round(shellRect?.height||0),
            autoHeight:el.classList.contains('auto-height-node'),
            bodyOverflow:bodyStyle ? `${bodyStyle.overflowX}/${bodyStyle.overflowY}` : '',
            bodyClient:body ? [body.clientWidth,body.clientHeight] : [0,0],
            bodyScroll:body ? [body.scrollWidth,body.scrollHeight] : [0,0],
            issues:[...new Set(issues)],
        };
    }));
}

async function configureSmart(page){
    const canvasId='all-smart-node-frame-audit';
    await page.route('**/static/smart-canvas.html*',async route => {
        const response=await route.fetch();
        const source=await response.text();
        const redirect=/\s*<!-- 兼容历史书签：智能画布已下线，统一进入画布编辑器。 -->\s*<script>[\s\S]*?location\.replace\(target\);[\s\S]*?<\/script>/;
        return route.fulfill({response,body:source.replace(redirect,'')});
    });
    await page.route(`**/api/canvases/${canvasId}*`,async route => {
        const request=route.request();
        if(request.method()!=='GET') return route.continue();
        const canvas={id:canvasId,title:'全节点框架审计',kind:'smart',project:'default',updated_at:1,viewport:{x:40,y:40,scale:.5},connections:[],nodes:[{id:'smart-seed',type:'smart-image',x:0,y:0,title:'上传节点',images:[],created_at:Date.now()}]};
        return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({canvas})});
    });
    await page.goto(`${base}/static/smart-canvas.html?id=${canvasId}`);
    await page.waitForSelector('.image-node[data-id]');
    await page.evaluate(fixtureImage => {
        const image = {url:fixtureImage,name:'fixture.png',kind:'image',natural_w:1024,natural_h:1024};
        const special=(id,specialType,w,h,extra={})=>({id,type:'smart-image',specialType,x:0,y:0,w,h,title:id,images:[],scale:0.62,created_at:Date.now(),...extra});
        const specs=[
            {id:'smart-upload',type:'smart-image',x:0,y:0,title:'上传节点',images:[],created_at:Date.now()},
            {id:'smart-image',type:'smart-image',x:0,y:0,title:'图片',images:[image],created_at:Date.now()},
            {id:'smart-media-group',type:'smart-image',x:0,y:0,title:'多图',images:Array.from({length:12},(_,index)=>({...image,name:`image-${index + 1}.png`})),created_at:Date.now()},
            {id:'smart-group',type:'smart-group',x:0,y:0,w:340,h:286,title:'智能分组',items:[],images:Array.from({length:8},(_,index)=>({...image,name:`group-${index + 1}.png`})),created_at:Date.now()},
            {id:'smart-prompt',type:'smart-prompt',x:0,y:0,w:316,h:360,title:'Prompt',text:'提示词内容\n'.repeat(12),promptSeparator:';',promptSplitEnabled:true,llmEnabled:true,llmProvider:'custom',llmModel:'private-chat',llmSystemEnabled:true,llmSystemPrompt:'system',llmInstruction:'instruction',created_at:Date.now()},
            {id:'smart-loop',type:'smart-loop',x:0,y:0,w:420,h:420,title:'Loop',count:8,mode:'serial',showPrompt:true,imageInput:true,loopStart:1,imageBatchSize:2,variablePrompt:'变量提示词',created_at:Date.now()},
            special('smart-film-storyboard','film-storyboard',520,720,{apiProvider:'custom',model:'private-image',actorCount:8,prompt:'分镜提示词\n'.repeat(8),aspectRatio:'16:9',resolution:'2k',quality:'high',count:4}),
            special('smart-film-line-art','film-line-art',520,620,{apiProvider:'custom',model:'private-image',prompt:'线稿提示词',aspectRatio:'source',resolution:'2k',quality:'high'}),
            special('smart-film-video','film-video',520,0,{apiProvider:'custom',model:'private-video',actorCount:8,prompt:'影视视频提示词\n'.repeat(14),duration:5,aspectRatio:'16:9',resolution:'1080p'}),
            special('smart-linkfox-video','linkfox-video',480,620,{apiProvider:'linkfox',model:'海螺2.3',duration:5,aspectRatio:'16:9',prompt:'LinkFox 视频提示词'}),
            special('smart-panorama','panorama',520,520,{panoramaPrompt:'测试',panoramaYaw:0,panoramaPitch:0,panoramaFov:72,panoramaAspect:'16:9',panoramaResolution:'1280x720'}),
            special('smart-dwpose','dwpose',380,390,{poseStatus:'idle'}),
            special('smart-depth-map','depth-map',520,560,{depthMapStatus:'idle'}),
            special('smart-director3d','director3d',460,420,{directorProject:null,directorCaptures:[]}),
            special('smart-pose-replicate','pose-replicate',720,820,{poseReplicateSchemaVersion:2,poseReplicateMode:'depth',poseReplicateProvider:'custom',poseReplicateModel:'private-image',poseReplicateRatio:'source',poseReplicateResolution:'2k',poseReplicateStatus:'idle',poseStatus:'idle',poseDepthStatus:'idle',poseReplicateRuns:[]}),
            special('smart-multi-view','multi-view',700,780,{apiProvider:'custom',model:'private-image',resolution:'2k',quality:'high',multiViewMode:'person',multiViewStatus:'idle',generatedOutputs:[],multiViewOutputs:[]}),
            special('smart-batch-generator','batch-generator',440,520,{apiProvider:'custom',model:'private-image',prompt:'批量处理',ratio:'source',resolution:'2k',quality:'auto'}),
            special('smart-legacy-angle','angle',460,660,{angleAzimuth:45,angleElevation:0,angleDistance:'medium',angleLens:'50',angleSubject:'person',anglePreserve:true,angleNotes:''}),
        ];
        nodes.splice(0,nodes.length,...specs);
        if(canvas){ canvas.nodes=nodes; canvas.connections=[]; }
        selectedId=''; selectedIds=[]; selectedImage={nodeId:'',index:-1};
        render();
        viewport.scale=1; viewport.x=40; viewport.y=40; applyViewport();
    }, fixtureImage);
    await page.waitForTimeout(4500);
}

async function measureSmart(page){
    return page.locator('.image-node[data-id]').evaluateAll(elements => elements.map(el => {
        const tolerance=2;
        const frame=el.getBoundingClientRect();
        const body=el.querySelector('.node-body');
        const bodyRect=body?.getBoundingClientRect();
        const bodyStyle=body ? getComputedStyle(body) : null;
        const issues=[];
        if(body){
            const horizontalOverflow=body.scrollWidth>body.clientWidth+tolerance;
            const verticalOverflow=body.scrollHeight>body.clientHeight+tolerance;
            if(horizontalOverflow&&!['auto','scroll'].includes(bodyStyle.overflowX)) issues.push('horizontal-clipping');
            if(verticalOverflow&&!['auto','scroll'].includes(bodyStyle.overflowY)) issues.push('vertical-clipping');
            if(bodyRect.left<frame.left-tolerance||bodyRect.right>frame.right+tolerance) issues.push('body-outside-frame');
            if(bodyRect.top<frame.top-tolerance||bodyRect.bottom>frame.bottom+tolerance) issues.push('body-vertical-outside-frame');
        }
        const controls=[...el.querySelectorAll('button,input,select,textarea')].filter(control => {
            const style=getComputedStyle(control);
            return style.display!=='none'&&style.visibility!=='hidden'&&control.getClientRects().length;
        });
        if(controls.some(control => {
            const rect=control.getBoundingClientRect();
            return rect.width>0&&(rect.left<frame.left-tolerance||rect.right>frame.right+tolerance);
        })) issues.push('control-horizontal-overflow');
        return {
            id:el.dataset.id,
            kind:el.classList.contains('smart-special-node')?[...el.classList].find(name=>name.startsWith('smart-')&&name.endsWith('-node')&&name!=='smart-special-node'):'base',
            width:Math.round(frame.width),height:Math.round(frame.height),
            autoHeight:el.classList.contains('smart-auto-height-node'),
            bodyOverflow:bodyStyle ? `${bodyStyle.overflowX}/${bodyStyle.overflowY}` : '',
            bodyClient:body ? [body.clientWidth,body.clientHeight] : [0,0],
            bodyScroll:body ? [body.scrollWidth,body.scrollHeight] : [0,0],
            bodyBounds:bodyRect ? [Math.round(bodyRect.top-frame.top),Math.round(bodyRect.bottom-frame.bottom)] : [0,0],
            issues:[...new Set(issues)],
        };
    }));
}

async function captureNodeSamples(page, selector, ids, prefix){
    for(const id of ids){
        await page.evaluate(({selector,id}) => {
            document.querySelectorAll(selector).forEach(node => { node.style.visibility=node.dataset.id===id?'visible':'hidden'; });
            const target=document.querySelector(`${selector}[data-id="${CSS.escape(id)}"]`);
            if(target){ target.style.left='20px'; target.style.top='90px'; target.style.zIndex='10000'; }
        },{selector,id});
        const clip=await page.evaluate(({selector,id}) => {
            const target=document.querySelector(`${selector}[data-id="${CSS.escape(id)}"]`);
            const rect=target?.getBoundingClientRect();
            return rect ? {x:Math.max(0,Math.floor(rect.x-4)),y:Math.max(0,Math.floor(rect.y-4)),width:Math.ceil(rect.width+8),height:Math.ceil(rect.height+8)} : null;
        },{selector,id});
        assert.ok(clip,`截图节点不存在：${id}`);
        await page.screenshot({path:path.join(artifacts,`${prefix}-${id}.png`),clip});
    }
    await page.evaluate(selector => document.querySelectorAll(selector).forEach(node => {
        node.style.removeProperty('visibility'); node.style.removeProperty('z-index');
    }),selector);
}

async function shrinkClassicNodes(page){
    await page.evaluate(() => {
        for(const node of nodes){
            startNodeResize({preventDefault(){},stopPropagation(){},clientX:0,clientY:0},node);
            onNodeResize({clientX:-10000,clientY:-10000});
            endDrag();
        }
    });
    await page.waitForTimeout(250);
}

async function shrinkSmartNodes(page){
    await page.evaluate(() => {
        nodes.forEach(node => {
            const limits=smartNodeResizeLimits(node);
            node.w=limits.minWidth;
            if(limits.minHeight>0) node.h=limits.minHeight; else delete node.h;
        });
        render();
    });
    await page.waitForTimeout(250);
}

(async()=>{
    const browser=await chromium.launch({headless:true,channel:'chrome'});
    const errors=[];
    try {
        const classicPage=await browser.newPage({viewport:{width:1800,height:1600}});
        classicPage.on('pageerror',error=>errors.push(`classic: ${error.message}`));
        await configureClassic(classicPage);
        const classic=await measureClassic(classicPage);
        await captureNodeSamples(classicPage,'.node[data-id]',['generator-rich','video','film-storyboard','pose-replicate','multi-view','output'],'classic');
        await shrinkClassicNodes(classicPage);
        const classicMinimum=await measureClassic(classicPage);
        await classicPage.setViewportSize({width:700,height:1000});
        const classicNarrow=await measureClassic(classicPage);

        const smartPage=await browser.newPage({viewport:{width:1800,height:1600}});
        smartPage.on('pageerror',error=>errors.push(`smart: ${error.message}`));
        await configureSmart(smartPage);
        const smart=await measureSmart(smartPage);
        await captureNodeSamples(smartPage,'.image-node[data-id]',['smart-prompt','smart-film-video','smart-depth-map','smart-legacy-angle'],'smart');
        await shrinkSmartNodes(smartPage);
        const smartMinimum=await measureSmart(smartPage);
        await smartPage.setViewportSize({width:700,height:1000});
        const smartNarrow=await measureSmart(smartPage);

        const report={classic,classicMinimum,classicNarrow,smart,smartMinimum,smartNarrow,errors};
        fs.writeFileSync(path.join(artifacts,'report.json'),JSON.stringify(report,null,2));
        console.log(JSON.stringify({
            classic:{default:classic.length,minimum:classicMinimum.length,narrow:classicNarrow.length},
            smart:{default:smart.length,minimum:smartMinimum.length,narrow:smartNarrow.length},
            screenshots:10,
            errors,
        }));
        assert.equal(classic.length,35,'经典画布节点清单必须完整渲染');
        assert.equal(smart.length,18,'智能画布节点清单必须完整渲染');
        assert.equal(errors.length,0,errors.join('\n'));
        assert.equal(frameIssueSummary(classic),'',`经典画布节点框架异常：\n${frameIssueSummary(classic)}`);
        assert.equal(frameIssueSummary(classicMinimum),'',`经典画布最小尺寸框架异常：\n${frameIssueSummary(classicMinimum)}`);
        assert.equal(frameIssueSummary(classicNarrow),'',`经典画布窄视口框架异常：\n${frameIssueSummary(classicNarrow)}`);
        assert.equal(frameIssueSummary(smart),'',`智能画布节点框架异常：\n${frameIssueSummary(smart)}`);
        assert.equal(frameIssueSummary(smartMinimum),'',`智能画布最小尺寸框架异常：\n${frameIssueSummary(smartMinimum)}`);
        assert.equal(frameIssueSummary(smartNarrow),'',`智能画布窄视口框架异常：\n${frameIssueSummary(smartNarrow)}`);
    } finally {
        await browser.close();
    }
})().catch(error=>{ console.error(error); process.exitCode=1; });
