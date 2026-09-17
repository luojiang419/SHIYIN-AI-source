
(() => {
  const escape=value=>String(value||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let active=null;
  function bodyHtml(node){
    return '<div class="cutout-node" style="height:100%;display:flex;flex-direction:column;gap:10px;padding:12px"><button data-cutout-open style="flex:1;min-height:180px;border:1px solid var(--line-2);background:repeating-conic-gradient(var(--soft) 0% 25%,var(--soft-2) 0% 50%) 0/20px 20px;color:var(--text);cursor:crosshair"><img data-cutout-preview style="width:100%;height:260px;object-fit:contain;display:none"><span data-cutout-empty>连接图片后点击开始抠像</span></button><button data-cutout-fullscreen class="btn">全屏操作 / 重新抠像</button><small data-cutout-note>保存后向下游传递透明 PNG</small></div>';
  }
  function bind(root,node,options){
    const input=options.getInputImage();
    const url=node.outputUrl||input?.url||node.cutoutSourceUrl;
    const image=root.querySelector('[data-cutout-preview]');
    if(url){image.src=options.resolveUrl?.(url)||url;image.style.display='block';root.querySelector('[data-cutout-empty]').hidden=true;}
    async function open(){
      if(options.openEditor){options.openEditor();return;}
      if(active)return;
      const source=options.getInputImage()?.url||node.cutoutSourceUrl;
      if(!source){options.toast('请先连接一张图片');return;}
      const initial=node.cutoutSourceUrl===source?node.cutoutSettings:null;
      // 挂到同源应用顶层，覆盖侧栏；不依赖浏览器全屏权限或 Esc 的浏览器行为。
      let host=window;
      try{if(window.top.document)host=window.top;}catch(_error){}
      const overlay=host.document.createElement('div');
      overlay.setAttribute('role','dialog');overlay.setAttribute('aria-label','自动抠像编辑器');
      overlay.style.cssText='position:fixed;inset:0;z-index:100000;background:#000b;display:flex;align-items:center;justify-content:center';
      const panel=document.createElement('div');
      panel.style.cssText='width:100%;height:100%;background:var(--panel);display:flex;flex-direction:column';
      const fallback=host.document.createElement('div');
      fallback.style.cssText='display:flex;align-items:center;justify-content:space-between;gap:12px;padding:8px 16px;flex-shrink:0;color:var(--text);background:var(--panel)';
      const status=host.document.createElement('span');status.textContent='正在加载抠像编辑器…';
      const close=host.document.createElement('button');close.textContent='返回画布（Esc）';close.style.cssText='padding:6px 14px;color:var(--text);background:var(--soft);border:1px solid var(--line-2);cursor:pointer';
      fallback.append(status,close);
      const frame=document.createElement('iframe');frame.src='/static/cutout-editor/index.html';
      // 顶层壳的路由 iframe 默认透明且不可交互，弹层必须显式隔离这些样式与生命周期。
      frame.dataset.studioOverlay='cutout';frame.title='自动抠像编辑器';
      frame.style.cssText='position:relative;inset:auto;display:block;opacity:1;visibility:visible;pointer-events:auto;transition:none;transform:none;flex:1 1 0%;height:0;width:100%;border:0;min-height:0';frame.allow='fullscreen';
      frame.cutoutOwnerWindow=window;
      panel.append(fallback,frame);overlay.append(panel);host.document.body.append(overlay);active=overlay;
      const loadingTimer=setTimeout(()=>{status.textContent='编辑器加载失败，请返回画布后重试';},15000);
      function syncTheme(){
        const style=getComputedStyle(document.body);
        const colors={};
        for(const key of ['page','panel','card-solid','soft','soft-2','line','line-2','text','muted','strong','strong-text'])
          colors[key]=style.getPropertyValue('--'+key).trim();
        frame.contentWindow?.postMessage({type:'cutout:theme',dark:document.documentElement.classList.contains('theme-dark'),colors},location.origin);
      }
      const observer=new MutationObserver(syncTheme);
      observer.observe(document.documentElement,{attributes:true,attributeFilter:['class','style']});
      observer.observe(document.body,{attributes:true,attributeFilter:['class','style']});
      const cleanup=()=>{
        clearTimeout(loadingTimer);
        observer.disconnect();
        host.removeEventListener('message',receive);
        host.removeEventListener('keydown',escapeEditor,true);
        if(host!==window)window.removeEventListener('keydown',escapeEditor,true);
        window.removeEventListener('pagehide',cleanup);
        overlay.remove();active=null;
      };
      close.onclick=cleanup;
      function escapeEditor(event){if(event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();cleanup();}}
      async function receive(event){
        if(event.origin!==location.origin||event.source!==frame.contentWindow)return;
        if(event.data?.type==='cutout:ready'){
          clearTimeout(loadingTimer);fallback.style.display='none';
          syncTheme();
          frame.contentWindow.postMessage({type:'cutout:load',sourceUrl:source,settings:initial},location.origin);
        }else if(event.data?.type==='cutout:cancel'){
          cleanup();
        }else if(event.data?.type==='cutout:saved'){
          if(event.data.sourceUrl!==source||!event.data.file?.url)return;
          if(options.getInputImage()?.url && options.getInputImage().url!==source){options.toast('上游图片已改变，请关闭后重新编辑');return;}
          node.cutoutSourceUrl=source;
          const {session_id,...settings}=event.data.settings||{};
          node.cutoutSettings=settings;
          node.outputUrl=event.data.file.url;node.outputName='自动抠像.png';node.outputKind='image';
          node.outputWidth=event.data.file.width;node.outputHeight=event.data.file.height;
          options.onSaved();cleanup();options.toast('抠像已保存，下游图片引用已同步');
        }
      }
      host.addEventListener('message',receive);
      host.addEventListener('keydown',escapeEditor,true);
      if(host!==window)window.addEventListener('keydown',escapeEditor,true);
      window.addEventListener('pagehide',cleanup);
      frame.focus();
    }
    for(const button of root.querySelectorAll('[data-cutout-open],[data-cutout-fullscreen]')){
      button.addEventListener('pointerdown',e=>e.stopPropagation());
      button.addEventListener('mousedown',e=>e.stopPropagation());
      button.onclick=e=>{e.stopPropagation();open();};
    }
  }
  function mountEditor(container,options){
    const frame=document.createElement('iframe');
    frame.id='imageCutoutFrame';frame.title='抠像工具';frame.dataset.studioOverlay='cutout';
    frame.style.cssText='position:relative;display:block;opacity:1;visibility:visible;pointer-events:auto;width:100%;height:100%;border:0;min-height:0';
    frame.src='/static/cutout-editor/index.html';
    function theme(){
      const style=getComputedStyle(document.body),colors={};
      for(const key of ['page','panel','card-solid','soft','soft-2','line','line-2','text','muted','strong','strong-text'])colors[key]=style.getPropertyValue('--'+key).trim();
      frame.contentWindow?.postMessage({type:'cutout:theme',dark:document.documentElement.classList.contains('theme-dark'),colors},location.origin);
    }
    function receive(event){
      if(event.origin!==location.origin||event.source!==frame.contentWindow)return;
      if(event.data?.type==='cutout:ready'){
        clearTimeout(timer);theme();
        frame.contentWindow.postMessage({type:'cutout:load',sourceUrl:options.sourceUrl,settings:options.settings,embedded:true},location.origin);
      }else if(event.data?.type==='cutout:controls')options.onState?.(event.data);
      else if(event.data?.type==='cutout:cancel')options.onClose();
      else if(event.data?.type==='cutout:saved'&&event.data.sourceUrl===options.sourceUrl&&event.data.file?.url)options.onSaved(event.data);
    }
    const timer=setTimeout(()=>options.onState?.({canSave:false,busy:false,error:'抠像工具加载失败，请返回画布后重试'}),15000);
    const observer=new MutationObserver(theme);
    observer.observe(document.documentElement,{attributes:true,attributeFilter:['class','style']});
    observer.observe(document.body,{attributes:true,attributeFilter:['class','style']});
    window.addEventListener('message',receive);container.append(frame);
    return {
      save:()=>frame.contentWindow?.postMessage({type:'cutout:save'},location.origin),
      fit:()=>frame.contentWindow?.postMessage({type:'cutout:fit'},location.origin),
      destroy:()=>{clearTimeout(timer);observer.disconnect();window.removeEventListener('message',receive);frame.remove();}
    };
  }
  window.CanvasCutoutNode={bodyHtml,bind,mountEditor};
})();
