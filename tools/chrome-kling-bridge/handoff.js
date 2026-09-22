(() => {
  if(window.__shiyinHandoffRunning) return;
  const ticket=location.hash.slice(1) || sessionStorage.getItem('shiyin-kling-ticket') || '';
  if(!/^[\w-]{40,60}$/.test(ticket)) return;
  window.__shiyinHandoffRunning=true;
  sessionStorage.setItem('shiyin-kling-ticket',ticket);
  history.replaceState(null,'',location.pathname);
  chrome.runtime.sendMessage({type:'handoff',ticket}).then(result=>{
    if(result?.ok) sessionStorage.removeItem('shiyin-kling-ticket');
    const status=document.querySelector('#status');
    if(status) status.textContent=result?.ok?'任务已接收，即将打开可灵。':result?.error || '插件接收失败';
  }).catch(error=>{const status=document.querySelector('#status');if(status)status.textContent=error.message;})
    .finally(()=>{window.__shiyinHandoffRunning=false;});
})();
