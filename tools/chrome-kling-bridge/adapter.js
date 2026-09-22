/* 只使用网页 DOM 与标准输入事件；不读取可灵 cookie、私有接口或框架内部状态。 */
(() => {
  if (window.ShiyinKlingAdapter?.version === '0.3.0') return;
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
  async function prepare(draft) {
    if(busy) throw new Error('正在填充另一份草稿');
    const current=editor().innerText;
    const reuse=!!completed && completed.sourceKey===draft.sourceKey && completed.text===current && completed.pool===poolSignature();
    if(!reuse && (cards().length || current.trim())) {
      // 用户授权画布任务覆盖当前草稿，通过网页重置同步清理素材和编辑器状态。
      const reset=unique('.omni-designer__message-input-area .reset-option');
      reset.click();
      const deadline=Date.now()+10000;
      while(cards().length || editor().innerText.trim()) {
        if(Date.now()>deadline) throw new Error('可灵草稿重置未完成，已停止本次任务');
        await sleep(200);
      }
      completed=null;
    }
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
    const {reuse}=await prepare(draft);
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
  function unique(selector) {
    const found=[...document.querySelectorAll(selector)].filter(visible);
    if(found.length!==1) throw new Error(`可灵控件已变化：${selector}`);
    return found[0];
  }
  function disabled(el){return el.disabled || el.getAttribute('aria-disabled')==='true' || el.classList.contains('disabled');}
  function settingsSignature(){
    return JSON.stringify({model:document.querySelector('.omni-setting-area .model')?.textContent,
      selected:[...document.querySelectorAll('.omni-setting-popover .option-tab-item.active')].map(e=>e.className),
      audio:document.querySelector('.has-native-audio svg')?.getAttribute('icon-name')});
  }
  async function configure(settings) {
    if(!/视频\s*3\.0\s*Omni/i.test(unique('.omni-setting-area .model').innerText)) throw new Error('请在可灵选择视频 3.0 Omni，当前模型不匹配');
    const trigger=unique('.omni-setting-area .setting-select');
    if(![...document.querySelectorAll('.omni-setting-popover')].some(visible)) {trigger.click();await sleep(250);}
    const select=async(group,label)=>{
      const panel=unique('.omni-setting-popover');
      const option=[...panel.querySelectorAll(`.${group} .option-tab-item`)].find(e=>e.querySelector('.inner')?.textContent.trim()===label);
      if(!option || disabled(option)) throw new Error(`可灵当前不支持参数：${label}`);
      if(!option.classList.contains('active')) {option.click();await sleep(200);}
      if(!option.classList.contains('active')) throw new Error(`可灵参数未生效：${label}`);
    };
    await select('model_mode',settings.resolution);
    await select('duration',`${settings.duration}s`);
    await select('aspect_ratio',settings.aspect_ratio==='auto'?'智能':settings.aspect_ratio);
    await select('imageCount','1');
    trigger.click();await sleep(150);
    const audio=unique('.has-native-audio');
    const checked=()=>audio.querySelector('svg')?.getAttribute('icon-name')==='IconCheckboxCheckedSecondary';
    if(checked()!==settings.generate_audio) {audio.click();await sleep(200);}
    if(checked()!==settings.generate_audio) throw new Error('音画同步设置未生效');
    completed.settings=settings;
    completed.settingsSignature=settingsSignature();
    return {configured:true};
  }
  const submittedIds=new Set();
  function checkSubmit(id) {
    if(!completed || completed.id!==id || completed.text!==editor().innerText || completed.pool!==poolSignature()) throw new Error('可灵草稿已被修改，停止自动生成');
    if(!completed.settings) throw new Error('生成参数尚未校验');
    if(completed.settingsSignature!==settingsSignature()) throw new Error('生成参数已被修改，停止自动生成');
    if(submittedIds.has(id) || sessionStorage.getItem(`shiyin-kling-submit-${id}`)) throw new Error('该任务已经尝试生成，禁止重复点击');
    const button=unique('.omni-designer__message-input-area button.button-pay');
    if(disabled(button) || !/^生成/.test(button.innerText.trim())) throw new Error('可灵生成按钮尚不可用，请检查登录、额度和素材');
    return {ready:true};
  }
  async function submit(id) {
    checkSubmit(id);
    const button=unique('.omni-designer__message-input-area button.button-pay');
    const before=new Set([...document.querySelectorAll('.virtual-item[id]')].map(e=>e.id));
    const text=completed.text.replace(/\s+/g,'');
    // 在点击之前写入；点击后的任何错误都不能授权第二次点击。
    sessionStorage.setItem(`shiyin-kling-submit-${id}`,'attempted');
    submittedIds.add(id);
    button.click();
    const deadline=Date.now()+30000;
    while(Date.now()<deadline){
      await sleep(400);
      const error=[...document.querySelectorAll('.el-message--error')].filter(visible).map(e=>e.innerText).join(' ');
      if(error) return {status:'unknown',message:`可灵提示：${error}；请核对历史记录后再决定是否重发`};
      const created=[...document.querySelectorAll('.virtual-item[id]')].find(e=>!before.has(e.id) && e.querySelector('.omni-stream-item') && e.querySelector('.prompt-display')?.innerText.replace(/\s+/g,'')===text);
      if(created) return {status:'submitted',message:`已提交可灵生成，任务 ${created.id}；可在可灵查看生成进度`};
    }
    return {status:'unknown',message:'已点击生成，但未确认可灵任务回执。请查看可灵历史记录，勿重复提交。'};
  }
  window.ShiyinKlingAdapter = {version:'0.3.0',beginFile, appendFile, upload, fillText, run, snapshot, prepare,configure,checkSubmit,submit};
})();
