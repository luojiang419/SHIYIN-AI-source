const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {chromium} = require('playwright');
const root = process.cwd();
const source = fs.readFileSync(path.join(root,'static/js/canvas.js'),'utf8');
function fn(name){
  const start=source.indexOf(`function ${name}(`);
  const end=source.indexOf('\nfunction ', start+1);
  return source.slice(start,end);
}
const prefs={defaultImageProvider:'image-b',defaultVideoProvider:'youyun-h3',image:{'image-b':{model:'b',ratio:'story',resolution:'4k'}},video:{'youyun-h3':{model:'MiniMax-H3',duration:12,aspectRatio:'9:16',resolution:'1080P',generateAudio:true},'kling-cli':{duration:8}}};
const context={window:{PersonalPreferences:{values:prefs,profile:(kind,id)=>prefs[kind]?.[id]||{}}},imageApiProviders:()=>[{id:'image-a'},{id:'image-b'}],defaultImageGenerationProvider:()=>({id:'image-a'}),allImageModels:()=>['a','b'],providerVideoModels:()=>['MiniMax-H3'],resolveVideoProviderId:id=>id||'youyun-h3',defaultPoint:()=>({x:0,y:0}),uid:x=>x,addNode:n=>n,sanitizeImageNodeProviderModel:()=>{},sanitizeVideoNodeProviderModel:()=>{},isMiniMaxH3VideoNode:()=>true,applyMiniMaxH3VideoDefaults:n=>Object.assign(n,{duration:5}),syncMiniMaxH3VideoDimensions:()=>{},DEFAULT_VIDEO_MODELS:[],videoModels:[]};
vm.createContext(context);
vm.runInContext(['defaultImageGenerationSelection','applyPersonalGenerationDefaults','addGeneratorNode','addBatchGeneratorNode','addVideoNode'].map(fn).join('\n'),context);
assert.equal(context.addGeneratorNode().ratio,'story');
assert.equal(context.addBatchGeneratorNode().resolution,'4k');
assert.equal(context.addVideoNode().duration,12);
assert.equal(context.addVideoNode().generateAudio,true);
const other={apiProvider:'kling-cli',type:'video'};context.applyPersonalGenerationDefaults(other,'video');assert.equal(other.duration,8);

(async()=>{
  const browser=await chromium.launch({headless:true});
  const output=path.join(root,'.codex-tmp','personal-preferences');fs.mkdirSync(output,{recursive:true});
  let saved=structuredClone(prefs);
  const providers=[{id:'image-b',name:'图片平台',image_models:['a','b']},{id:'youyun-h3',name:'优云 H3',video_models:['MiniMax-H3']},{id:'minimax-h3',name:'MiniMax H3',video_models:['MiniMax H3']},{id:'kling-cli',name:'可灵',video_models:['kling-v3-omni']}];
  try{
    for(const [theme,width] of [['dark',1280],['light',1280],['pure-white',390]]){
      const page=await browser.newPage({viewport:{width,height:900}});
      const errors=[];page.on('pageerror',e=>errors.push(e.message));
      await page.addInitScript(t=>localStorage.setItem('studio_theme',t),theme);
      await page.route('http://preferences.test/**',async route=>{
        const url=new URL(route.request().url());let data={};
        if(url.pathname.startsWith('/static/')){
          const file=path.join(root,url.pathname.slice(1));
          return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html'});
        }
        if(url.pathname==='/api/account/me')data={account:{id:'test-account',is_admin:false}};
        if(url.pathname==='/api/runtime/config')data={api_providers:providers};
        if(url.pathname==='/api/personal-preferences'){
          if(route.request().method()==='PUT')saved=JSON.parse(route.request().postData());
          data=saved;
        }
        if(url.pathname.endsWith('/quick-save'))data={mode:'manual',directory:''};
        if(url.pathname.endsWith('/select-directory'))data={selected:true,path:'C:\\PreferencesTest'};
        return route.fulfill({json:data});
      });
      await page.goto('http://preferences.test/static/personal-preferences.html');
      await page.waitForFunction(()=>!document.getElementById('preferencesFields').disabled);
      await page.locator('#videoSettings [data-field="duration"]').fill('14');
      await page.locator('#videoSettings [data-provider]').selectOption('kling-cli');
      await page.locator('#videoSettings [data-field="duration"]').fill('7');
      await page.locator('#videoSettings [data-provider]').selectOption('youyun-h3');
      assert.equal(await page.locator('#videoSettings [data-field="duration"]').inputValue(),'14');
      await page.locator('#chooseDirectory').click();
      await page.waitForFunction(()=>document.getElementById('saveDirectory').value==='C:\\PreferencesTest');
      await page.locator('#savePreferences').click();
      await page.getByText('已保存，新建节点将使用你的偏好').waitFor();
      assert.equal(saved.video['youyun-h3'].duration,14);assert.equal(saved.video['kling-cli'].duration,7);
      assert.deepEqual(saved.quickSave,{mode:'silent',directory:'C:\\PreferencesTest'});
      await page.reload();await page.waitForFunction(()=>!document.getElementById('preferencesFields').disabled);
      assert.equal(await page.locator('#videoSettings [data-field="duration"]').inputValue(),'14');
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      await page.screenshot({path:path.join(output,`${theme}.png`),fullPage:true});
      assert.deepEqual(errors,[]);await page.close();
    }
    const toolbar=await browser.newPage();
    await toolbar.setContent('<div id="toolbar"></div>');
    const toolbarFunction=source.slice(source.indexOf('function renderQuickToolbarItems(){'),source.indexOf("let canvasSettingsMode = 'toolbar';"));
    await toolbar.evaluate(code=>{
      const toolbarNodeItems=document.getElementById('toolbar');
      const CLASSIC_QUICK_TOOLBAR_DEFS=[{id:'video',label:'视频',icon:'video'},{id:'generator',label:'图片',icon:'image'}];
      const QUICK_TOOLBAR_ITEMS_KEY='toolbar';let ids=['video','generator'];
      const quickToolbarItemIds=()=>ids;
      const filterCanvasWorkModeItems=x=>x;
      const saveCanvasPreferenceList=(_key,next)=>{ids=next;};
      const refreshIcons=()=>{};const escapeAttr=x=>x,escapeHtml=x=>x;
      eval(code+'\nrenderQuickToolbarItems();');
    },toolbarFunction);
    await toolbar.locator('[data-toolbar-node="video"]').click({button:'right'});
    assert.equal(await toolbar.locator('[data-toolbar-node="video"]').count(),0);
    assert.equal(await toolbar.locator('[data-toolbar-node="generator"]').count(),1);
    await toolbar.close();
    console.log('PASS: node defaults, provider isolation, save/reload, three themes and mobile layout');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
