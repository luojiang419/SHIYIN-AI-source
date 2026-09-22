const KLING_URL = 'https://klingai.com/app/omni/new?ac=1';
let active = false;
async function api(base, path, options={}) {
  const response = await fetch(base + '/api/kling-web' + path, {
    ...options, credentials:'include', headers:{'Content-Type':'application/json'}, signal:AbortSignal.timeout(15000)
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
  let tab = tabs.find(t=>t.active) || tabs[0];
  if (!tab) tab = await chrome.tabs.create({url:KLING_URL});
  else await chrome.tabs.update(tab.id,{active:true});
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
  const {enabled,base='http://127.0.0.1:3000'}=await chrome.storage.local.get(['enabled','base']);
  if (!enabled) return;
  active=true;
  let draft;
  try {
    ({draft}=await api(base,'/claim',{method:'POST'}));
    if (!draft) {
      await chrome.storage.local.set({lastStatus:`已连接 ${base}，等待画布发送草稿`});
      return;
    }
    const tabId=await targetTab();
    const sourceKey=JSON.stringify(draft.references.map(ref=>[ref.kind,ref.url]));
    const {reuse}=await call(tabId,'prepare',[{sourceKey}]);
    const refs=[];
    for(const [index,ref] of (reuse?[]:draft.references).entries()) {
      const url=new URL(ref.url,base);
      if(url.origin!==new URL(base).origin || !/^\/(assets|output|input)\//.test(url.pathname)) throw new Error('拒绝读取非本地素材');
      const response=await fetch(url.href,{credentials:'include',signal:AbortSignal.timeout(60000)});
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
    const message='图片、视频和提示词已填充；未提交生成，请在可灵核对参数';
    await api(base,`/drafts/${draft.id}/result`,{method:'POST',body:JSON.stringify({lease:draft.lease,status:'filled',message})});
    await chrome.storage.local.set({lastStatus:message});
  } catch(error) {
    await chrome.storage.local.set({lastStatus:error.message});
    if(draft) {
      try { await api(base,`/drafts/${draft.id}/result`,{method:'POST',body:JSON.stringify({lease:draft.lease,status:'failed',message:error.message})}); }
      catch { /* 后端租约超时会明确失败，不自动重试网页操作。 */ }
    }
  } finally { active=false; }
}
chrome.alarms.onAlarm.addListener(alarm=>{if(alarm.name==='kling-poll') void tick();});
chrome.runtime.onInstalled.addListener(()=>chrome.alarms.create('kling-poll',{periodInMinutes:0.5}));
chrome.runtime.onStartup.addListener(()=>chrome.alarms.create('kling-poll',{periodInMinutes:0.5}));
chrome.runtime.onMessage.addListener((msg,sender,respond)=>{
  if(msg?.type==='poll' && sender.id===chrome.runtime.id) { tick().then(()=>respond({ok:true})); return true; }
});
