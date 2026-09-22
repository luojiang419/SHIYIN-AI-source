const input=document.querySelector('#base'), status=document.querySelector('#status');
chrome.storage.local.get(['base','lastStatus','enabled']).then(data=>{
  input.value=data.base || input.value;
  status.textContent=(data.enabled?'已启用。':'未启用。')+(data.lastStatus || '');
});
document.querySelector('#connect').onclick=async()=>{
  try {
    const url=new URL(input.value);
    const local=url.protocol==='http:' && ['127.0.0.1','localhost'].includes(url.hostname);
    if((!local && url.protocol!=='https:') || url.username || url.password) throw new Error('请输入本机HTTP地址或远程HTTPS拾影地址');
    if(!local){
      const origin=url.origin+'/*';
      if(!await chrome.permissions.request({origins:[origin]})) throw new Error('未授权该站点，连接已取消');
      const id='shiyin-'+url.hostname.replace(/[^a-z0-9]/gi,'-');
      const registered=await chrome.scripting.getRegisteredContentScripts();
      if(registered.some(x=>x.id===id)) await chrome.scripting.unregisterContentScripts({ids:[id]});
      await chrome.scripting.registerContentScripts([{id,matches:[url.origin+'/api/kling-web/connect*'],js:['handoff.js'],runAt:'document_idle'}]);
    }
    for(const tab of await chrome.tabs.query({url:url.origin+'/api/kling-web/connect*'})) {
      await chrome.scripting.executeScript({target:{tabId:tab.id},files:['handoff.js']});
    }
    await chrome.storage.local.set({base:url.origin,enabled:true,lastStatus:''});
    await chrome.alarms.create('kling-poll',{periodInMinutes:0.5});
    status.textContent='正在连接……';
    await chrome.runtime.sendMessage({type:'poll'});
    const data=await chrome.storage.local.get('lastStatus');
    status.textContent=data.lastStatus || '已连接，等待画布发送草稿';
  } catch(error) {status.textContent=error.message;}
};
document.querySelector('#stop').onclick=async()=>{
  await chrome.storage.local.set({enabled:false});
  status.textContent='已停止接收新草稿；已开始的填充仍会完成。';
};
