/* 只使用网页 DOM 与标准输入事件；不读取可灵 cookie、私有接口或框架内部状态。 */
(() => {
  if (window.ShiyinKlingAdapter) return;
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const visible = el => !!el && el.getClientRects().length > 0;
  function editor() {
    const items = [...document.querySelectorAll('.omni-prompt-editor .tiptap[contenteditable="true"]')].filter(visible);
    if (items.length !== 1) throw new Error('未找到唯一的可灵 Omni 编辑框，请先登录并打开 Omni');
    return items[0];
  }
  function pool() { return editor().closest('.materials-and-editor')?.querySelector('.material-pool'); }
  function cards() { return [...(pool()?.querySelectorAll('.omni-material-pool__material-item:not(.upload)') || [])]; }
  function snapshot() {
    return {text: editor().innerText, cards: cards().map(e => ({label:e.querySelector('.label-text')?.textContent || '', ready:!!e.querySelector('img[src^="https://"]')}))};
  }
  const files = new Map();
  let busy = false;
  let completed = null;
  function poolSignature() { return cards().map(e=>e.querySelector('img')?.src || '').join('\n'); }
  function prepare(draft) {
    if(busy) throw new Error('正在填充另一份草稿');
    const current=editor().innerText;
    const reuse=!!completed && completed.sourceKey===draft.sourceKey && completed.text===current && completed.pool===poolSignature();
    if(!reuse && (cards().length || current.trim())) throw new Error('当前可灵编辑器已有草稿，请先保存或点击网页“重置”，再重新发送');
    return {reuse};
  }
  function beginFile(id, name, type) {
    if (!/^(image\/(png|jpeg)|video\/(mp4|quicktime))$/.test(type)) throw new Error('不支持的素材类型');
    files.set(id, {name, type, parts:[], size:0});
  }
  function appendFile(id, base64) {
    const file = files.get(id);
    if (!file) throw new Error('素材传输未初始化');
    const bytes = Uint8Array.from(atob(base64), c => c.charCodeAt(0));
    file.size += bytes.length;
    if (file.size > 200 * 1024 * 1024) { files.delete(id); throw new Error('单个素材超过 200 MB'); }
    file.parts.push(bytes);
  }
  async function upload(id) {
    const data = files.get(id);
    if (!data) throw new Error('素材尚未传输');
    const input = document.querySelector('input[type="file"][accept*=".mp4"]');
    if (!input) throw new Error('可灵上传控件已变化，请更新插件');
    const before = cards().length;
    const dt = new DataTransfer();
    dt.items.add(new File(data.parts, data.name, {type:data.type}));
    files.delete(id);
    input.files = dt.files;
    input.dispatchEvent(new Event('change', {bubbles:true}));
    const until = Date.now() + 180000;
    while (Date.now() < until) {
      await sleep(400);
      const error = [...document.querySelectorAll('.el-message--error')].filter(visible).map(e=>e.innerText).join(' ');
      if (error) throw new Error(error);
      const current = cards();
      if (current.length > before && current.every(e=>e.querySelector('img[src^="https://"]') && e.querySelector('.label-text')?.textContent) && !current.some(e=>/上传中|处理中|解析中|\d+%/.test(e.innerText) || e.querySelector('.el-progress,.is-loading'))) {
        await sleep(800);
        return {name:data.name, cards:cards().length};
      }
    }
    throw new Error('等待素材上传超时，请查看可灵页面；不会自动重复上传');
  }
  async function fillText(prompt) {
    prompt=String(prompt).replace(/<<<image_(\d+)>>>/g,'图片$1').replace(/<<<video_(\d+)>>>/g,'视频$1').replace(/@?图(\d+)/g,'图片$1');
    if (!String(prompt).trim()) throw new Error('提示词不能为空');
    const labels=new Set(cards().map(e=>e.querySelector('.label-text')?.textContent));
    const tokens=[...prompt.matchAll(/@?(?:图片|视频)\d+/g)];
    for(const token of tokens) if(!labels.has(token[0].replace(/^@/,''))) throw new Error(`未上传引用素材：${token[0]}`);
    const el = editor();
    el.focus();
    const range = document.createRange();
    range.selectNodeContents(el);
    const selection = window.getSelection();
    selection.removeAllRanges(); selection.addRange(range);
    document.execCommand('delete');
    await sleep(100);
    let offset=0;
    const insert=text=>{
      const lines=text.split(/\r?\n/);
      lines.forEach((line,index)=>{
        if(index && !document.execCommand('insertLineBreak')) throw new Error('编辑器拒绝换行');
        if(line && !document.execCommand('insertText',false,line)) throw new Error('编辑器拒绝写入提示词');
      });
    };
    for(const token of tokens){
      insert(prompt.slice(offset,token.index));
      insert('@');
      const label=token[0].replace(/^@/,'');
      let button;
      for(let attempt=0;attempt<40;attempt++){
        await sleep(100);
        button=[...document.querySelectorAll('button')].find(e=>visible(e) && e.querySelector('.mention-label')?.textContent===label);
        if(button) break;
      }
      if(!button) throw new Error(`找不到可灵引用菜单：${label}`);
      button.click();
      await sleep(150);
      offset=token.index+token[0].length;
    }
    insert(prompt.slice(offset));
    await sleep(150);
    const normalize=text=>text.replace(/\s+/g,'').replace(/@(?=(?:图片|视频)\d+)/g,'');
    if (normalize(el.innerText) !== normalize(prompt)) throw new Error('提示词写入校验失败');
    const mentions=[...el.querySelectorAll('.media-tag-wrapper')].map(e=>e.dataset.label);
    if(mentions.length!==tokens.length) throw new Error('可灵素材引用绑定失败');
    return {text:el.innerText, mentions, cards:cards().length, generated:false};
  }
  async function run(draft) {
    if (busy) throw new Error('正在填充另一份草稿');
    if (completed?.id === draft.id) return {status:'filled', generated:false};
    const {reuse}=prepare(draft);
    busy = true;
    try {
      if(!reuse){
        for (const ref of draft.references) await upload(ref.id);
        if(editor().innerText.trim()) throw new Error('上传过程中提示词被修改，已停止填充以保留当前编辑');
      }
      const result = await fillText(draft.prompt);
      completed = {id:draft.id,sourceKey:draft.sourceKey,text:editor().innerText,pool:poolSignature()};
      return {status:'filled', ...result};
    } finally { busy = false; files.clear(); }
  }
  window.ShiyinKlingAdapter = {beginFile, appendFile, upload, fillText, run, snapshot, prepare};
})();
