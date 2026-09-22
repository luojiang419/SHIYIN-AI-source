const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');

async function backgroundCase({reuse=false, uploadError=false, autoSubmit=false, submitError=false}={}){
  const calls=[],requests=[],status={enabled:true,base:'http://127.0.0.1:3000'};
  const draft={auto_submit:autoSubmit,settings:{duration:5,resolution:'1080p',aspect_ratio:'16:9',generate_audio:false},id:'draft-1',lease:'lease-1',prompt:'参考视频1和图片1',references:[
    {url:'/assets/a.mp4',kind:'video'}, {url:'/assets/b.png',kind:'image'}]};
  const context=vm.createContext({console,URL,AbortSignal,Uint8Array,Blob,Date,setTimeout,btoa,
    fetch:async(url,options)=>{
      requests.push({url:String(url),options});
      assert.equal(options.credentials,'include');
      if(String(url).endsWith('/claim')) return {ok:true,json:async()=>({draft})};
      if(String(url).endsWith('/submit-permit')) return {ok:true,json:async()=>({permitted:true})};
      if(String(url).endsWith('/result')) return {ok:true,json:async()=>({ok:true})};
      return {ok:true,blob:async()=>new Blob(['test-binary'],{type:String(url).endsWith('.mp4')?'video/mp4':'image/png'})};
    },
    chrome:{storage:{local:{get:async()=>status,set:async data=>Object.assign(status,data)}},
      tabs:{query:async()=>[{id:12,active:true}],update:async()=>{},get:async()=>({status:'complete'})},
      scripting:{executeScript:async options=>{
        if(options.files) return [];
        const [method,args]=options.args;calls.push({method,args});
        if(method==='prepare') return [{result:{ok:true,value:{reuse}}}];
        if(method==='submit') return [{result:submitError?{ok:false,error:'回执丢失'}:{ok:true,value:{status:'submitted',message:'已提交'}}}];
        if(method==='run' && uploadError) return [{result:{ok:false,error:'上传失败'}}];
        return [{result:{ok:true,value:{status:'filled',generated:false}}}];
      }},alarms:{onAlarm:{addListener(){}},create(){}},
      runtime:{onInstalled:{addListener(){}},onStartup:{addListener(){}},onMessage:{addListener(){}}}}
  });
  vm.runInContext(fs.readFileSync(path.join(root,'tools/chrome-kling-bridge/background.js'),'utf8')+'\nthis.runTick=tick;',context);
  await context.runTick();
  const result=JSON.parse(requests.find(x=>x.url.endsWith('/result')).options.body);
  assert.equal(result.status,uploadError?'failed':submitError?'unknown':autoSubmit?'submitted':'filled');
  assert.equal(calls.filter(x=>x.method==='beginFile').length,reuse?0:2);
  assert.equal(calls.filter(x=>x.method==='run').length,1);
  assert.ok(!requests.some(x=>/generate|canvas-video/.test(x.url)));
  assert.equal(calls.filter(x=>x.method==='submit').length,autoSubmit&&!uploadError?1:0);
  assert.equal(requests.filter(x=>x.url.endsWith('/submit-permit')).length,autoSubmit&&!uploadError?1:0);
  assert.ok(calls.every(x=>['snapshot','prepare','beginFile','appendFile','run','configure','checkSubmit','submit'].includes(x.method)));
}

async function canvasCase(type){
  const source=fs.readFileSync(path.join(root,'static/js/canvas.js'),'utf8');
  const code=source.slice(source.indexOf('const klingWebSendingNodes='),source.indexOf('async function ensureKlingGenerationAvailable'));
  const requests=[],messages=[],node={id:'node1',type};
  const refs=[{url:'/assets/video.mp4',kind:'video'},{url:'/assets/image.png',kind:'image'}];
  const context=vm.createContext({Set,Date,Promise,JSON,String,encodeURIComponent,setTimeout:resolve=>resolve(),nodes:[node],isKlingOmni30Model:()=>true,
    orderedSources:(_n,sources)=>sources,generatorSources:()=>[{refs}],combinedGeneratorPrompt:()=> '普通提示词',
    classicFilmAssets:()=>refs,connectedCanvasPromptTextForSubmission:()=>'',mediaKindForRef:ref=>ref.kind,
    window:{CanvasFilmNodes:{buildPrompt:()=>({prompt:'影视提示词',refs})}},scheduleSave(){},setStatus:message=>messages.push(message),
    showErrorModal:error=>{throw new Error(error);},
    fetch:async(url,opts)=>{requests.push({url,opts});return {ok:true,json:async()=>opts?{id:'draft1'}:{status:'submitted',message:'已提交可灵生成'}};}
  });
  vm.runInContext(code+'\nthis.sendDraft=fillKlingWebDraft;',context);
  await Promise.all([context.sendDraft('node1'),context.sendDraft('node1')]);
  assert.equal(requests.filter(r=>r.opts?.method==='POST').length,2);
  const body=JSON.parse(requests[0].opts.body);
  assert.deepEqual(body.references,refs.map(ref=>({...ref,name:''})));
  assert.equal(body.prompt,type==='film-video'?'影视提示词':'普通提示词');
  assert.equal(node.klingWebDraftId,'draft1');
  assert.equal(body.auto_submit,true);
  assert.ok(messages.some(x=>x.includes('已提交可灵生成')));
  assert.ok(requests.every(x=>x.url.startsWith('/api/kling-web/')));
}
(async()=>{
  await backgroundCase();await backgroundCase({reuse:true});await backgroundCase({uploadError:true});
  await backgroundCase({autoSubmit:true});await backgroundCase({autoSubmit:true,submitError:true});
  await canvasCase('video');await canvasCase('film-video');
  console.log('7 runtime cases passed: transfer, reuse, upload failure, one-click submit, uncertain receipt, canvas, film canvas');
})().catch(error=>{console.error(error);process.exitCode=1;});
