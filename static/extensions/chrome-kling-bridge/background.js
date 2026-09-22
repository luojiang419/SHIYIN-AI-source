const KLING_URL = 'https://klingai.com/app/omni/new?ac=1';
let active = false;
let pendingWrites=Promise.resolve();
function updatePending(change) {
  const work=pendingWrites.then(async()=>{
    const data=await chrome.storage.local.get('pending');
    await chrome.storage.local.set({pending:change(data.pending || [])});
  });
  pendingWrites=work.catch(()=>{});
  return work;
}
async function api(base, path, options={}, ticket='') {
  const response = await fetch(base + '/api/kling-web' + path, {
    ...options, credentials:'include', headers:{'Content-Type':'application/json', 'X-Shiyin-Extension-Version':chrome.runtime.getManifest().version, ...(ticket?{Authorization:`Bearer ${ticket}`}:{})}, signal:AbortSignal.timeout(15000)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `服务返回 ${response.status}`);
  return data;
}
async function call(tabId, method, args=[]) {
  const results = await chrome.scripting.executeScript({target:{tabId}, func:async (method,args)=>{
    try { return {ok:true, value:await window.ShiyinKlingAdapter[method](...args)}; }
    catch(error) { return {ok:false,error:error.message}; }
  },args:[method,args]});
  if (!results[0]?.result?.ok) throw new Error(results[0]?.result?.error || '可灵页面已关闭或插件失去连接');
  return results[0].result.value;
}
async function targetTab() {
  const tabs = await chrome.tabs.query({url:'https://klingai.com/app/omni/*'});
  let tab = tabs.find(t=>!t.active) || tabs[0];
  if (!tab) {
    try {tab = await chrome.tabs.create({url:KLING_URL,active:false});}
    catch {tab = (await chrome.windows.create({url:KLING_URL,focused:false,state:'minimized'})).tabs[0];}
  }
  const deadline=Date.now()+30000;
  while (Date.now()<deadline) {
    const state=await chrome.tabs.get(tab.id);
    if(state.status==='complete') break;
    await new Promise(resolve=>setTimeout(resolve,500));
  }
  await chrome.scripting.executeScript({target:{tabId:tab.id},files:['adapter.js']});
  return tab.id;
}
async function tick() {
  if (active) return;
  active=true;
  let stored;
  try {
    stored=await chrome.storage.local.get(['enabled','base','pending','channels']);
    if(stored.enabled!==false && !(stored.pending || []).length) {
      for(const channel of stored.channels || []) {
        try {
          const result=await api(channel.base,'/transport/poll',{method:'POST'},channel.token);
          if(result.ticket) await updatePending(pending=>pending.some(x=>x.ticket===result.ticket)?pending:[...pending,{base:channel.base,ticket:result.ticket}]);
        } catch { /* 后端重启后由下一次画布交接重建连接，不重放已领取任务。 */ }
      }
      stored={...stored,...await chrome.storage.local.get('pending')};
    }
  } catch(error) {active=false;throw error;}
  const job=(stored.pending || [])[0];
  const base=job?.base || stored.base;
  const ticket=job?.ticket || '';
  if (!base || stored.enabled===false) {active=false;return;}
  let draft;
  let permitted=false;
  const draftApi=(path,options)=>api(base,ticket?`/transport/${path}`:`/drafts/${draft.id}/${path}`,options,ticket);
  try {
    ({draft}=await api(base,ticket?'/transport/claim':'/claim',{method:'POST'},ticket));
    if (!draft) {
      await chrome.storage.local.set({lastStatus:`已连接 ${base}，等待画布发送草稿`});
      return;
    }
    const tabId=await targetTab();
    for(let attempt=0;attempt<60;attempt++) {
      try { await call(tabId,'snapshot'); break; }
      catch(error) { if(attempt===59) throw error; await new Promise(resolve=>setTimeout(resolve,500)); }
    }
    const sourceKey=JSON.stringify(draft.references.map(ref=>[ref.kind,ref.url]));
    const {reuse}=await call(tabId,'prepare',[{sourceKey}]);
    const refs=[];
    for(const [index,ref] of (reuse?[]:draft.references).entries()) {
      const url=new URL(ref.url,base);
      if(url.origin!==new URL(base).origin || !/^\/(assets|output|input)\//.test(url.pathname)) throw new Error('拒绝读取非本地素材');
      const response=await fetch(ticket?`${base}/api/kling-web/transport/media/${index}`:url.href,{credentials:'include',headers:ticket?{Authorization:`Bearer ${ticket}`}:{},signal:AbortSignal.timeout(60000)});
      if(!response.ok) throw new Error(`读取素材失败：${response.status}`);
      const blob=await response.blob();
      if(blob.size>200*1024*1024) throw new Error('单个素材超过 200 MB');
      const id=`${draft.id}-${index}`;
      const name=decodeURIComponent(url.pathname.split('/').pop());
      await call(tabId,'beginFile',[id,name,blob.type.split(';')[0]]);
      const bytes=new Uint8Array(await blob.arrayBuffer());
      for(let offset=0;offset<bytes.length;offset+=262144) {
        let binary='';
        for(const byte of bytes.subarray(offset,offset+262144)) binary+=String.fromCharCode(byte);
        await call(tabId,'appendFile',[id,btoa(binary)]);
      }
      refs.push({id});
    }
    await call(tabId,'run',[{id:draft.id,prompt:draft.prompt,references:refs,sourceKey}]);
    let status='filled', message='图片、视频和提示词已填充；未提交生成';
    if(draft.auto_submit) {
      await call(tabId,'configure',[draft.settings]);
      await call(tabId,'checkSubmit',[draft.id]);
      // 从这里起，网络失败也不能推断未提交，禁止重放生成点击。
      permitted=true;
      await draftApi('submit-permit',{method:'POST',body:JSON.stringify({lease:draft.lease,status:'submitting'})});
      const result=await call(tabId,'submit',[draft.id]);
      status=result.status;
      message=result.message;
    }
    await draftApi('result',{method:'POST',body:JSON.stringify({lease:draft.lease,status,message})});
    await chrome.storage.local.set({lastStatus:message});
  } catch(error) {
    await chrome.storage.local.set({lastStatus:permitted?`提交结果未确认，请先查看可灵历史记录，勿重复生成：${error.message}`:error.message});
    if(draft) {
      try { await draftApi('result',{method:'POST',body:JSON.stringify({lease:draft.lease,status:permitted?'unknown':'failed',message:error.message})}); }
      catch { /* 后端租约超时会明确失败，不自动重试网页操作。 */ }
    }
  } finally {
    if(job) {
      await updatePending(pending=>pending.filter(x=>x.ticket!==ticket));
    }
    active=false;
  }
}
chrome.alarms.onAlarm.addListener(alarm=>{if(alarm.name==='kling-poll') void tick();});
async function start(){await chrome.alarms.create('kling-poll',{periodInMinutes:0.5});void tick();}
async function reconnectPages(){
  await start();
  const permissions=await chrome.permissions.getAll();
  const matches=['http://127.0.0.1/api/kling-web/connect*','http://localhost/api/kling-web/connect*',
    ...(permissions.origins || []).filter(o=>o.startsWith('https://') && !o.includes('klingai.com')).map(o=>o.replace(/\*$/, 'api/kling-web/connect*'))];
  for(const tab of await chrome.tabs.query({url:matches})) {
    try { await chrome.scripting.executeScript({target:{tabId:tab.id},files:['handoff.js']}); } catch {}
  }
}
chrome.runtime.onInstalled.addListener(()=>void reconnectPages());
chrome.runtime.onStartup.addListener(start);
chrome.runtime.onMessage.addListener((msg,sender,respond)=>{
  if(msg?.type==='handoff' && sender.id===chrome.runtime.id) {
    (async()=>{
      const source=new URL(sender.url);
      const local=source.protocol==='http:' && ['127.0.0.1','localhost'].includes(source.hostname);
      const granted=source.protocol==='https:' && await chrome.permissions.contains({origins:[source.origin+'/*']});
      if(!(local || granted) || source.pathname!=='/api/kling-web/connect' || !/^[\w-]{40,60}$/.test(msg.ticket)) throw Error('交接来源无效');
      try {
        const registered=await api(source.origin,'/transport/channel',{method:'POST'},msg.ticket);
        const saved=await chrome.storage.local.get('channels');
        await chrome.storage.local.set({channels:[...(saved.channels || []).filter(x=>x.base!==source.origin),{base:source.origin,token:registered.channel}]});
      } catch(error) { await updatePending(pending=>pending.filter(x=>x.ticket!==msg.ticket)); throw error; }
      await updatePending(pending=>pending.some(x=>x.ticket===msg.ticket)?pending:[...pending,{base:source.origin,ticket:msg.ticket}]);
      await chrome.storage.local.set({base:source.origin,enabled:true,lastStatus:'已自动接收画布任务'});
      await chrome.alarms.create('kling-poll',{periodInMinutes:0.5});
      respond({ok:true});
      void tick();
      if(sender.tab?.id) await chrome.tabs.remove(sender.tab.id);
    })().catch(error=>respond({ok:false,error:error.message}));
    return true;
  }
  if(msg?.type==='poll' && sender.id===chrome.runtime.id) { tick().then(()=>respond({ok:true})); return true; }
});
