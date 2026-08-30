(function(){
  'use strict';
  const SRC = '/static/director/index.html';
  const sessions = new Map();
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  function capturesHtml(node){
    const items = Array.isArray(node?.directorCaptures) ? node.directorCaptures.filter(item => item?.url) : [];
    if(!items.length) return '<div class="director3d-empty"><i data-lucide="clapperboard"></i><span>在 3D 空间搭建场景、调整机位并导出截图</span></div>';
    return `<div class="director3d-captures">${items.slice(-6).map(item => `<img src="${esc(item.url)}" alt="${esc(item.name || '导演台截图')}" draggable="false">`).join('')}</div>`;
  }
  function bodyHtml(node){
    return `<div class="director3d-body"><div class="director3d-preview">${capturesHtml(node)}</div><div class="director3d-meta"><span><i data-lucide="layers-3"></i>3D 场景 · 角色 · 机位</span><button type="button" data-director3d-open><i data-lucide="external-link"></i>打开 3D导演台</button></div></div>`;
  }
  function dataUrlBlob(dataUrl){ return fetch(dataUrl).then(r => r.blob()); }
  function open(node, options){
    const existing = sessions.get(node?.id);
    if(existing) return existing;
    const overlay = document.createElement('div');
    overlay.className = 'director3d-overlay';
    overlay.innerHTML = `<div class="director3d-frame"><iframe title="3D导演台" src="${SRC}" allow="autoplay"></iframe></div>`;
    document.body.appendChild(overlay);
    const iframe = overlay.querySelector('iframe');
    let ready = false;
    let closed = false;
    let readyResolve;
    let readyReject;
    const readyPromise = new Promise((resolve, reject) => { readyResolve = resolve; readyReject = reject; });
    const readyTimer = setTimeout(() => readyReject(new Error('导演台加载超时')), 15000);
    const pending = new Map();
    const close = () => { if(closed) return; closed = true; window.removeEventListener('message', onMessage); overlay.remove(); };
    const post = (type, payload) => iframe?.contentWindow?.postMessage({type, payload}, window.location.origin);
    const uploadCaptures = async captures => {
      const list = [];
      for(const capture of captures){
        try {
          const blob = await dataUrlBlob(capture.dataUrl);
          const file = await options.uploadBlob(blob, capture.fileName || '导演台截图.png');
          if(file?.url) list.push({...file, kind:'image', name:file.name || capture.fileName || '导演台截图.png'});
        } catch(error){ options.toast?.(`截图上传失败：${error.message || '未知错误'}`); }
      }
      if(!list.length) return;
      node.directorCaptures = [...(node.directorCaptures || []), ...list].slice(-12);
      node.images = [...node.directorCaptures];
      for(const item of list) await options.createDirectorOutputNode?.(node, item);
      options.onChange?.(node, {render:true});
      options.toast?.(`已导出 ${list.length} 张导演台截图`);
    };
    async function onMessage(event){
      if(event.origin !== window.location.origin || event.source !== iframe.contentWindow) return;
      const type = event.data?.type;
      if(type === 'storyai:director-ready'){
        ready = true;
        clearTimeout(readyTimer);
        readyResolve(session);
        post('storyai:director-session', {instanceId:node.id, theme:window.StudioTheme?.get?.() || 'dark', project:node.directorProject || null});
        return;
      }
      if(type === 'storyai:director-close'){ session?.close(); return; }
      if(type === 'storyai:director-capture-response'){
        const requestId = String(event.data?.payload?.requestId || '');
        const request = pending.get(requestId);
        if(!request) return;
        pending.delete(requestId);
        if(event.data?.payload?.error) request.reject(new Error(String(event.data.payload.error)));
        else request.resolve(event.data?.payload?.capture || event.data?.payload?.captures?.[0] || null);
        return;
      }
      if(type === 'storyai:director-project-changed'){
        const project = event.data?.payload?.project;
        if(project && typeof project === 'object' && !Array.isArray(project)){ node.directorProject = project; options.onChange?.(node, {render:false}); }
        return;
      }
      if(type === 'storyai:director-captures-sent'){
        const captures = Array.isArray(event.data?.payload?.captures) ? event.data.payload.captures.filter(item => typeof item?.dataUrl === 'string' && item.dataUrl.startsWith('data:image/')) : [];
        if(captures.length) await uploadCaptures(captures);
      }
      if(type === 'storyai:director-video-sent') options.toast?.('视频导出已完成；当前画布暂保存截图输出，请使用截图连接下游节点');
    }
    window.addEventListener('message', onMessage);
    overlay.addEventListener('click', event => { if(event.target === overlay) session?.close(); });
    const session = {
      close,
      get ready(){ return ready; },
      readyPromise,
      pending,
      post,
      requestCapture(payload={}, timeoutMs=15000){
        const requestId = `director-capture-${Date.now()}-${Math.random().toString(36).slice(2)}`;
        return new Promise((resolve, reject) => {
          const timer = setTimeout(() => { pending.delete(requestId); reject(new Error('导演台当前机位截图超时')); }, timeoutMs);
          pending.set(requestId, {resolve:value => { clearTimeout(timer); resolve(value); }, reject:error => { clearTimeout(timer); reject(error); }});
          post('storyai:director-capture-request', {...payload, requestId, preset:'current'});
        });
      }
    };
    sessions.set(node?.id, session);
    const originalClose = session.close;
    session.close = () => { sessions.delete(node?.id); clearTimeout(readyTimer); readyReject(new Error('导演台已关闭')); pending.forEach(item => item.reject(new Error('导演台已关闭'))); pending.clear(); originalClose(); };
    return session;
  }
  async function capture(node, options={}, payload={}){
    const wasOpen = Boolean(sessions.get(node?.id));
    const session = open(node, options);
    try {
      await session.readyPromise;
      const result = await session.requestCapture(payload);
      if(!result?.dataUrl || !String(result.dataUrl).startsWith('data:image/')) throw new Error('导演台没有返回有效的当前机位截图');
      if(typeof options.uploadBlob !== 'function') throw new Error('当前画布未配置截图上传能力');
      const blob = await dataUrlBlob(result.dataUrl);
      const file = await options.uploadBlob(blob, result.fileName || `${node.id}-current-camera.png`);
      if(!file?.url) throw new Error('导演台截图上传失败');
      const item = {...file, kind:'image', name:file.name || result.fileName || 'director-current-camera.png', natural_w:Number(result.meta?.width || file.natural_w || 0), natural_h:Number(result.meta?.height || file.natural_h || 0), directorCaptureMeta:result.meta || null};
      node.directorCaptures = [...(node.directorCaptures || []), item].slice(-12);
      node.images = [...node.directorCaptures];
      options.onChange?.(node, {render:true});
      return item;
    } finally {
      if(!wasOpen) session.close();
    }
  }
  function bind(root,node,options={}){ root?.querySelector('[data-director3d-open]')?.addEventListener('click', event => { event.preventDefault(); event.stopPropagation(); open(node, options); }); }
  window.Director3DNode = {bodyHtml, bind, open, capture};
})();
