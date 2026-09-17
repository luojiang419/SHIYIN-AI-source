
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
      if(active)return;
      const source=options.getInputImage()?.url||node.cutoutSourceUrl;
      if(!source){options.toast('请先连接一张图片');return;}
      const initial=node.cutoutSourceUrl===source?node.cutoutSettings:null;
      // 挂到同源应用顶层，覆盖侧栏；不依赖浏览器全屏权限或 Esc 的浏览器行为。
      let host=window;
      try{if(window.top.document)host=window.top;}catch(_error){}
      const overlay=host.document.createElement('div');
      overlay.style.cssText='position:fixed;inset:0;z-index:100000;background:#000b;display:flex;align-items:center;justify-content:center';
      const panel=document.createElement('div');
      panel.style.cssText='width:100%;height:100%;background:var(--panel);display:flex;flex-direction:column';
      const frame=document.createElement('iframe');frame.src='/static/cutout-editor/index.html';frame.style.cssText='flex:1 1 0%;height:0;width:100%;border:0;min-height:0';frame.allow='fullscreen';
      frame.cutoutOwnerWindow=window;
      panel.append(frame);overlay.append(panel);host.document.body.append(overlay);active=overlay;
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
        observer.disconnect();
        host.removeEventListener('message',receive);
        host.removeEventListener('keydown',escapeEditor,true);
        window.removeEventListener('pagehide',cleanup);
        overlay.remove();active=null;
      };
      function escapeEditor(event){if(event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();cleanup();}}
      async function receive(event){
        if(event.origin!==location.origin||event.source!==frame.contentWindow)return;
        if(event.data?.type==='cutout:ready'){
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
      window.addEventListener('pagehide',cleanup);
      frame.focus();
    }
    for(const button of root.querySelectorAll('[data-cutout-open],[data-cutout-fullscreen]')){
      button.addEventListener('pointerdown',e=>e.stopPropagation());
      button.addEventListener('mousedown',e=>e.stopPropagation());
      button.onclick=e=>{e.stopPropagation();open();};
    }
  }
  window.CanvasCutoutNode={bodyHtml,bind};
})();
