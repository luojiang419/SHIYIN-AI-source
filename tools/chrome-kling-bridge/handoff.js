(() => {
  const ticket=location.hash.slice(1);
  if(!/^[\w-]{40,60}$/.test(ticket)) return;
  history.replaceState(null,'',location.pathname);
  chrome.runtime.sendMessage({type:'handoff',ticket}).then(result=>{
    document.querySelector('#status').textContent=result?.ok?'任务已接收，即将打开可灵。':result?.error || '插件接收失败';
  }).catch(error=>{document.querySelector('#status').textContent=error.message;});
})();
