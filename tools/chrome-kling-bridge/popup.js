const input=document.querySelector('#base'), status=document.querySelector('#status');
chrome.storage.local.get(['base','lastStatus','enabled']).then(data=>{
  input.value=data.base || input.value;
  status.textContent=(data.enabled?'已启用。':'未启用。')+(data.lastStatus || '');
});
document.querySelector('#connect').onclick=async()=>{
  try {
    const url=new URL(input.value);
    if(url.protocol!=='http:' || !['127.0.0.1','localhost'].includes(url.hostname) || url.username || url.password) throw new Error('请输入本机 http://127.0.0.1:端口 或 localhost 地址');
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
