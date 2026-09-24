const fs = require('fs');
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const classic = fs.readFileSync('static/js/canvas.js','utf8');
const smart = fs.readFileSync('static/js/smart-canvas.js','utf8');
const film = fs.readFileSync('static/js/canvas-film-nodes.js','utf8');
function fn(source,name){
  let start=source.indexOf('function '+name+'(');
  assert(start>=0,name);
  if(source.slice(start-6,start)==='async ') start-=6;
  return source.slice(start,source.indexOf('\n}',start)+2);
}
async function run(){
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const browserErrors=[];
  page.on('pageerror', error=>browserErrors.push(error.message));
  await page.setContent('<meta charset="utf-8"><style>body{font:14px sans-serif;background:#f5f0e7}section{display:inline-block;vertical-align:top;width:430px;margin:12px;padding:12px;background:white}select,input,button{margin:5px;padding:6px;max-width:400px}.gen-settings-row{margin:10px 0}.field{display:block}.smart-popover{border:1px solid #ddd;padding:5px}.model-list button{display:block}</style><section id="classic"></section><section id="film"></section><section id="smart"></section>');
  await page.addScriptTag({content:film});
  await page.addScriptTag({content:`
    const providers=[{id:'minimax-h3',name:'MiniMax H3',video_models:['MiniMax H3']},{id:'youyun-h3',name:'优云智算H3',video_models:['MiniMax-H3']}];
    const apiProviders=providers;
    const tr=value=>value; const escapeHtml=value=>String(value); const escapeAttr=escapeHtml;
    const defaultApiProviders=()=>providers;
    const minimaxH3ConnectionNote=()=> '本地 H3';
    let youyunH3State={loading:false,generationEnabled:true,defaults:{available_points:1150},error:''};
    ${fn(classic,'youyunH3ConnectionNote')}
    ${['isYouyunH3VideoNode','isMiniMaxH3VideoNode','videoApiProviders','resolveVideoProviderId','videoProviderOptions'].map(n=>fn(classic,n)).join('\n')}
    ${classic.slice(classic.indexOf('const MINIMAX_H3_VIDEO_RESOLUTIONS ='),classic.indexOf('function videoModelOptions('))}
    ${fn(classic,'youyunH3VideoSettingsHtml')}
    ${fn(classic,'h3VideoSettingsHtml')}
    window.classicNode={apiProvider:'minimax-h3',model:'MiniMax H3',duration:5,steps:2,resolution:'0.4MP 9:16 - 480x864',aspectRatio:'9:16'};
    window.drawClassic=()=>{
      applyMiniMaxH3VideoDefaults(classicNode);
      document.querySelector('#classic').innerHTML='<h2>普通视频节点</h2><select id="classic-provider">'+videoProviderOptions(classicNode.apiProvider)+'</select>'+h3VideoSettingsHtml(classicNode);
      document.querySelector('#classic-provider').onchange=e=>{classicNode.apiProvider=e.target.value;applyMiniMaxH3VideoDefaults(classicNode,{force:true});drawClassic();};
    };drawClassic();
    window.filmNode={type:'film-video',apiProvider:'minimax-h3',model:'MiniMax H3',duration:5,steps:2,resolution:'0.4MP 9:16 - 480x864',aspectRatio:'9:16'};
    window.drawFilm=()=>{
      CanvasFilmNodes.normalize(filmNode);
      const root=document.querySelector('#film');
      root.innerHTML='<h2>影视视频节点</h2>'+CanvasFilmNodes.h3VideoSettingsHtml(filmNode,videoProviderOptions(filmNode.apiProvider),'<option>'+filmNode.model+'</option>')+(filmNode.apiProvider==='youyun-h3'?'<div class="film-video-balance-note">'+youyunH3ConnectionNote()+'</div>':'');
      CanvasFilmNodes.bind(root,filmNode,{defaultModel:id=>providers.find(p=>p.id===id).video_models[0],onChange:()=>drawFilm()});
    };drawFilm();
  `});
  await page.addScriptTag({content:`
    const dynamicParams=document.querySelector('#smart');
    let settings={videoProvider:'minimax-h3',videoModel:'MiniMax H3',videoSteps:2,videoDuration:5,videoAspect:'9:16',videoResolution:'0.4MP 9:16 - 480x864'};
    const providerVideoModels=id=>providers.find(p=>p.id===id)?.video_models||[];
    const filterJimengVideoModels=value=>value;
    const isKlingSmartSettings=()=>false;
    const smartMiniMaxH3ConnectionNote=()=> '本地 H3';
    let smartYouyunH3State={loading:false,generationEnabled:true,defaults:{available_points:1150},error:''};
    ${fn(smart,'smartYouyunH3ConnectionNote')}
    ${['isYouyunH3SmartSettings','isMiniMaxH3SmartSettings','h3SmartVideoResolutions','h3SmartAspectForResolution','h3SmartResolutionForAspect','syncH3SmartVideoDimensions','renderVideoProviderControl','renderVideoModelControl','renderVideoDurationControl','videoAspectIconClass','renderH3VideoAspectControl','renderH3VideoResolutionControl','renderH3VideoStepsControl','renderVideoToggleControl','renderApiVideoParams'].map(n=>fn(smart,n)).join('\n')}
    window.drawSmart=()=>{renderApiVideoParams();};drawSmart();
    dynamicParams.addEventListener('click',e=>{const button=e.target.closest('[data-smart-param]');if(button){settings[button.dataset.smartParam]=button.dataset.smartValue;if(button.dataset.smartParam==='videoProvider')settings.videoModel='';syncH3SmartVideoDimensions(settings);drawSmart();}});
  `});
  for(const panel of ['classic','film','smart']){
    assert.match(await page.locator('#'+panel).textContent(),/0\.4MP 9:16/);
    assert.match(await page.locator('#'+panel).textContent(),/采样步数/);
  }
  assert.equal(await page.locator('#film [data-film-field="steps"]').inputValue(),'2');
  assert.equal(await page.locator('#film [data-film-field="resolution"] option').count(),18);
  await page.selectOption('#classic-provider','youyun-h3');
  await page.selectOption('#film [data-film-field="apiProvider"]','youyun-h3');
  await page.locator('#smart [data-smart-param="videoProvider"][data-smart-value="youyun-h3"]').click();
  for(const panel of ['classic','film','smart']){
    const text=await page.locator('#'+panel).textContent();
    assert.match(text,/768P/);assert.match(text,/4K/);assert.match(text,/移除音轨/);assert.doesNotMatch(text,/采样步数|0\.2MP/);
    assert.match(text,/优云智算H3.*可用积分 1,150/);
  }
  await page.selectOption('#film [data-film-field="resolution"]','2K');
  assert.equal(await page.locator('#film [data-film-field="resolution"]').inputValue(),'2K');
  await page.locator('#film [data-film-toggle="muteAudio"]').click();
  await page.locator('#film [data-film-toggle="watermark"]').click();
  assert.deepEqual(await page.evaluate(()=>[filmNode.muteAudio,filmNode.watermark]),[true,true]);
  for(const selector of ['#classic .video-duration','#film [data-film-field="duration"]','#smart [data-param="videoDuration"]']){
    assert.equal(await page.locator(selector).getAttribute('min'),'4');assert.equal(await page.locator(selector).getAttribute('max'),'30');
  }
  await page.screenshot({path:'.codex-tmp/h3-provider-split/cloud-panels.png',fullPage:true});
  await page.selectOption('#classic-provider','minimax-h3');
  await page.selectOption('#film [data-film-field="apiProvider"]','minimax-h3');
  await page.locator('#smart [data-smart-param="videoProvider"][data-smart-value="minimax-h3"]').click();
  for(const panel of ['classic','film','smart']){
    const text=await page.locator('#'+panel).textContent();assert.match(text,/采样步数/);assert.match(text,/0\.2MP/);assert.doesNotMatch(text,/移除音轨|可用积分/);
  }
  assert.match(classic,/film-video-balance-note/);
  assert.equal(await page.evaluate(()=>youyunH3ConnectionNote.call(null)), '优云智算H3 · 可用积分 1,150 · 已就绪');
  assert.equal(await page.locator('#film [data-film-field="steps"]').inputValue(),'2');
  for(const selector of ['#classic .video-duration','#film [data-film-field="duration"]','#smart [data-param="videoDuration"]']){
    assert.equal(await page.locator(selector).getAttribute('min'),'1');assert.equal(await page.locator(selector).getAttribute('max'),'15');
  }
  // 明确的平台 ID 不被同名模型误判。
  assert.equal(await page.evaluate(()=>isMiniMaxH3VideoNode({apiProvider:'other',model:'MiniMax H3'})),false);
  assert.equal(await page.evaluate(()=>isMiniMaxH3SmartSettings({videoProvider:'other',videoModel:'MiniMax H3'})),false);
  await page.screenshot({path:'.codex-tmp/h3-provider-split/local-panels.png',fullPage:true});
  assert.deepEqual(browserErrors,[]);
  console.log('PASS: classic / film / smart local-cloud-local switching, 18 local presets, 4 cloud tiers, duration bounds, local steps, cloud audio/watermark, strict provider identity');
 }finally{await browser.close();}
}
run().catch(e=>{console.error(e);process.exitCode=1;});
