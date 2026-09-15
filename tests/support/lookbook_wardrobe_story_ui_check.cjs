// 真实隔离后端负责页面/保存；仅模拟收费任务接口，验证中途回填与冲突保护。
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');

(async()=>{
  const base='http://127.0.0.1:3048';
  const output=path.resolve('.codex-artifacts/lookbook-wardrobe-ui/check');
  fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({headless:true,channel:'msedge'});
  const page=await browser.newPage({viewport:{width:1440,height:1100}});
  const tasks=new Map();let latest;let count=0;
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const story={version:process.env.LOOKBOOK_STORY_TEST_VERSION||'lookbook-editorial-story-v2',source_signature:'ui-signature',title:'并肩赴约',ad_brief:'《并肩赴约》\n故事：门口等待同伴，沿台阶走下，在街角并肩同行。\n立意：自然穿着与从等待到同行的松弛情绪。\n服装展示：侧背剪裁、露腰系带结构、走动的面料垂坠。\n摄影意图：门内侧拍、台阶低位、街角侧后观察，机位为服装服务。'};
  await page.route('**/api/ecommerce/tasks',async route=>{
    if(route.request().method()!=='POST')return route.continue();
    const payload=route.request().postDataJSON();
    latest={id:'ui-story-'+(++count),ready:false,status:'running',payload};tasks.set(latest.id,latest);
    await route.fulfill({json:{id:latest.id,status:'running',count:payload.count,options:payload.options}});
  });
  await page.route('**/api/ecommerce/tasks/*',async route=>{
    const id=route.request().url().split('/').pop();const item=tasks.get(id);
    if(!item)return route.continue();
    const options={...item.payload.options};
    if(item.ready)Object.assign(options,{lookbook_story:story,lookbook_context_signature:'ui-signature'});
    await route.fulfill({json:{id,status:item.status,error:item.status==='failed'?'测试：第二阶段失败，故事保留':'',progress_status:item.ready?'故事已完成，正在编写服装展示与多机位提示词…':'正在综合参考图，构思以服装为主的故事与立意…',options,request:{...item.payload,options}}});
  });
  try{
    await page.goto(base+'/api/auth/bootstrap?token=lookbook-wardrobe-ui-local');
    const response=await page.request.post(base+'/api/canvases',{data:{title:'Lookbook服装故事回填验证',kind:'classic'}});
    assert.equal(response.ok(),true);
    const canvas=(await response.json()).canvas;
    const url=base+'/static/canvas.html?id='+canvas.id;
    await page.goto(url);
    await page.waitForFunction(()=>window.CanvasLookbookNode&&typeof render==='function');
    await page.evaluate(()=>{
      nodes.splice(0,nodes.length);connections.splice(0,connections.length);
      nodes.push({...CanvasLookbookNode.createNode({x:0,y:0}),id:'wardrobe-lookbook'});
      viewport.x=100;viewport.y=50;viewport.scale=1;render();
    });
    const input=()=>page.locator('[data-lookbook-field="lookbookPrompt"]');
    await page.locator('[data-lookbook-run]').click();
    await page.waitForFunction(()=>nodes.find(n=>n.id==='wardrobe-lookbook')?.ecomTaskId==='ui-story-1');
    assert.equal(latest.payload.options.instruction,'');
    // 未编辑但保持焦点时也应该看到回填，不能被焦点恢复逻辑还原成空值。
    await input().focus();latest.ready=true;
    await page.waitForFunction(()=>document.querySelector('[data-lookbook-field="lookbookPrompt"]')?.value.includes('并肩赴约'));
    assert.equal(await input().inputValue(),story.ad_brief);
    assert.equal(await page.evaluate(()=>CanvasLookbookNode.sourceInstruction(nodes.find(n=>n.id==='wardrobe-lookbook'))),'');
    await page.screenshot({path:path.join(output,'story-backfilled.png')});
    latest.status='failed';
    await page.waitForFunction(()=>nodes.find(n=>n.id==='wardrobe-lookbook')?.runStatus==='failed');
    await page.evaluate(()=>saveCanvas());
    await page.reload();
    await page.waitForFunction(()=>document.querySelector('[data-lookbook-field="lookbookPrompt"]')?.value.includes('并肩赴约'));
    assert.equal(await input().inputValue(),story.ad_brief);
    // 下一次任务返回期间编辑文本，不得覆盖；原始故事仍存在任务响应。
    await page.locator('[data-lookbook-run]').click();
    await page.waitForFunction(()=>nodes.find(n=>n.id==='wardrobe-lookbook')?.ecomTaskId==='ui-story-2');
    assert.equal(latest.payload.options.instruction,'');
    await input().fill('用户新要求：保留白色两件式，安静优雅地走过街角');
    latest.ready=true;
    await page.waitForFunction(()=>nodes.find(n=>n.id==='wardrobe-lookbook')?.lookbookStoryNotice?.includes('未被覆盖'));
    assert.match(await input().inputValue(),/用户新要求/);
    await page.screenshot({path:path.join(output,'edited-input-preserved.png')});
    latest.status='failed';
    await page.waitForFunction(()=>nodes.find(n=>n.id==='wardrobe-lookbook')?.runStatus==='failed');
    // 恢复原始需求，以及过期任务和输入法组合态保护。
    await page.locator('summary').filter({hasText:'查看原始需求'}).click();
    await page.locator('[data-lookbook-restore-brief]').click();
    assert.equal(await input().inputValue(),'');
    const checks=await page.evaluate(story=>{
      const node=nodes.find(n=>n.id==='wardrobe-lookbook');
      const pending={lookbookGroupId:'current-run',lookbookInputRevision:node.lookbookInputRevision,lookbookPromptAtStart:''};
      node.lookbookActiveRunId='current-run';node.ecomTaskId='current-task';
      const task={options:{lookbook_story:story,instruction:'',lookbook_context_signature:'ui-signature'}};
      const stale=CanvasLookbookNode.applyStoryResult(node,'old-task',task,pending);
      const el=document.querySelector('[data-lookbook-field="lookbookPrompt"]');
      el.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true}));
      const composing=CanvasLookbookNode.applyStoryResult(node,'current-task',task,pending);
      el.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true}));
      const applied=CanvasLookbookNode.applyStoryResult(node,'current-task',task,pending);
      refreshRunNodes(node);
      return {stale,composing,applied};
    },story);
    assert.deepEqual(checks,{stale:false,composing:false,applied:true});
    assert.deepEqual(errors,[]);
    const result={status:'passed',apiCalls:'mocked; no paid generation',realPersistence:true,backfillWhileFocused:true,failedStageRetainsStory:true,reloadRestoresStory:true,originalInstructionPreserved:true,editedInputPreserved:true,restoreOriginal:true,staleTaskBlocked:true,compositionBlocked:true,pageErrors:errors};
    fs.writeFileSync(path.join(output,'verification.json'),JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  }catch(error){
    fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({error:String(error),pageErrors:errors,state:await page.evaluate(()=>({node:nodes.find(n=>n.id==='wardrobe-lookbook'),versionSupported:String(CanvasLookbookNode.applyStoryResult).includes('lookbook-editorial-story-v2')}))},null,2));
    throw error;
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
