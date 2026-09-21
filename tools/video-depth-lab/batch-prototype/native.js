const $ = s => document.querySelector(s);
const api = window.__TAURI__;
const invoke = (name, args) => api.core.invoke(name, args);
const key = 'shiyin-depth-batch-v1';
let saved = {};
try { saved = JSON.parse(localStorage.getItem(key) || '{}'); } catch {}
let queue = (saved.queue || []).map(j => ({...j, state: j.state === 'active' ? 'waiting' : j.state}));
let outputRoot = saved.outputRoot || '';
let selected = 0, running = false, paused = false, preparing = false, exporting = false;
const defaults = { far: 0, near: 100, gamma: 0, contrast: 100, smooth: 0, invert: false };
const presets = { '默认': defaults, '主体增强': {...defaults, far: 12, near: 90, gamma: 8, contrast: 142, smooth: 7}, '空间层次': {...defaults, far: 4, near: 98, gamma: -8, contrast: 126, smooth: 3} };
let parameters = {...defaults};
const escapeHtml = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const persist = () => { try { localStorage.setItem(key, JSON.stringify({queue, outputRoot})); } catch { toast('无法保存队列，请检查磁盘空间'); } };
function toast(message) { $('[data-toast]').textContent = String(message); $('[data-toast]').hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => $('[data-toast]').hidden = true, 7000); }
function fail(error) { toast(String(error)); }
const controls = p => ({farPoint:p.far, nearPoint:p.near, midtone:p.gamma, contrast:p.contrast, smooth:p.smooth, invert:p.invert});
const modelSelect = $('.left-configuration select');
const sizeSelect = $('.compact-grid select');
const modelKey = () => modelSelect.selectedIndex === 1 ? 'vda_small_fp16_relative' : 'vda_base_fp16_relative';
const preview = document.createElement('video');
preview.muted = true; preview.loop = true; preview.playsInline = true; preview.className = 'real-video';
$('[data-depth-scene]').replaceWith(preview);
let previewPath = '';
function render() {
  const done = queue.filter(j => j.state === 'done').length;
  const active = queue.find(j => j.state === 'active');
  $('[data-queue]').innerHTML = queue.map((j, i) => `<article class="job ${j.state} ${i === selected ? 'selected' : ''}" data-select="${i}"><span class="thumb">${j.state === 'done' ? '✓' : '▶'}</span><div><div class="job-name">${escapeHtml(j.name)}</div><div class="job-meta" title="${escapeHtml(j.error || j.path)}">${escapeHtml(j.error || j.meta || '保留原视频规格')}</div>${j.state === 'active' ? `<div class="job-progress"><i style="width:${j.progress || 0}%"></i></div>` : ''}</div><div class="job-status">${({waiting:'等待', active:`${j.progress || 0}%`, done:'已完成', failed:'失败 · 点开始重试'})[j.state]}<button class="job-remove" data-remove="${i}" ${j.state === 'active' ? 'disabled' : ''}>×</button></div></article>`).join('');
  $('[data-total]').textContent = `${queue.length} 个视频`;
  $('[data-summary-progress]').textContent = `${done} / ${queue.length}`;
  $('[data-summary-bar]').style.width = `${queue.length ? (done + (active?.progress || 0)/100)/queue.length*100 : 0}%`;
  $('[data-remaining]').textContent = preparing ? '准备组件中' : active ? '处理中' : paused ? '已暂停' : '—';
  $('[data-queue-count]').textContent = `${queue.length} 个任务 · ${queue.filter(j => j.state === 'failed').length} 个失败`;
  $('[data-path]').textContent = outputRoot || '请选择输出目录';
  $('[data-note] b').textContent = preparing ? '首次准备运行时与模型' : active ? `正在处理 ${active.name}` : paused ? '队列已暂停' : '准备就绪';
  $('[data-note] span').textContent = active?.message || '按顺序提取，保留原始 FPS、全部帧与原始分辨率';
  $('[data-action="start"]').disabled = running || preparing || exporting;
  $('[data-action="clear"]').disabled = running || exporting;
  modelSelect.disabled = running || preparing; sizeSelect.disabled = running;
  const job = queue[selected];
  const path = job?.adjustedPath || job?.result?.outputVideoPath || '';
  if (path !== previewPath) { previewPath = path; if (path) preview.src = api.core.convertFileSrc(path); else { preview.removeAttribute('src'); preview.load(); } }
  $('[data-preview-name]').textContent = job?.name || '等待导入视频';
  $('[data-preview-info]').textContent = path ? '点击播放 · 双击划像对比 · 调参预览为近似效果，导出精确计算' : '提取完成后显示真实深度视频';
  $('[data-preview-state]').textContent = job?.state === 'done' ? '已完成' : '未完成';
  $('[data-action="export-adjusted"]').disabled = !job?.result?.rawDepthPath || running || preparing || exporting;
}
function renderParameters() {
  for (const [name, value] of Object.entries(parameters)) {
    const input = $(`[data-parameter="${name}"]`); if (input.type === 'checkbox') input.checked = value; else input.value = value;
    const out = $(`[data-value="${name}"]`); if (out) out.textContent = value;
  }
  preview.style.filter = `contrast(${parameters.contrast}%) brightness(${1 + parameters.gamma / 150}) invert(${parameters.invert ? 1 : 0}) blur(${parameters.smooth / 12}px)`;
}
function select(index) { selected = index; parameters = {...defaults, ...queue[index]?.parameters}; renderParameters(); render(); }
function saveParameters() { if (queue[selected]) queue[selected].parameters = {...parameters}; persist(); renderParameters(); }
function add(files) { for (const f of files) if (!queue.some(j => j.path === f.path)) queue.push({...f, state:'waiting', progress:0, parameters:{...defaults}, meta:f.width ? `${f.width}×${f.height} · ${Number(f.fps).toFixed(2)} FPS` : ''}); persist(); render(); }
async function status() {
  const s = await invoke('get_runtime_status');
  $('.health strong').textContent = s.runtimeReady ? '本地运行时已就绪' : '首次使用将下载运行时';
  $('.health small').textContent = s.runtimeReady ? `${s.gpu || s.device || ''} · 单任务串行` : '魔塔下载 · 完整性校验 · 下载后可离线使用';
  const m = s.models?.find(m => m.key === modelKey());
  $('.compact-model-status strong').textContent = m?.ready ? '当前模型已就绪' : '首次开始时从魔塔下载';
  $('.compact-model-status small').textContent = modelSelect.selectedIndex === 1 ? 'Small · 约 116 MB · Apache-2.0' : 'Base · 约 458 MB · 仅限非商业用途';
}
async function processQueue() {
  if (running || preparing || exporting) return;
  if (!queue.length) return toast('请先导入视频');
  if (!outputRoot) { outputRoot = await invoke('choose_output_directory') || ''; if (!outputRoot) return; }
  paused = false; $('[data-action="pause"]').textContent = '暂停队列'; preparing = true; render();
  try { await invoke('ensure_components', {model:modelKey()}); await status(); }
  catch (e) { fail(e); return; }
  finally { preparing = false; render(); }
  running = true;
  const model = modelKey(), inputSize = sizeSelect.selectedIndex === 1 ? 518 : 322;
  const pending = queue.filter(j => j.state === 'waiting' || j.state === 'failed');
  for (const job of pending) {
    if (paused) break;
    if (!queue.includes(job)) continue;
    job.state = 'active'; job.error = ''; job.progress = 0; render(); persist();
    try {
      job.result = await invoke('run_inference', {request:{inputPath:job.path, outputRoot, model, inputSize, targetFps:-1, maxFrames:-1, maxResolution:-1, parameters:controls(job.parameters)}});
      job.state = 'done'; job.progress = 100;
    } catch(e) { job.state = 'failed'; job.error = String(e); }
    persist(); render();
  }
  running = false; render(); toast(paused ? '当前视频已完成，队列已暂停' : '本轮队列处理结束');
}
$('[data-action="add"]').onclick = async () => { try { add(await invoke('choose_input_videos')); } catch(e) { fail(e); } };
$('[data-action="path"]').onclick = async () => { try { if (running || preparing) return; outputRoot = await invoke('choose_output_directory') || outputRoot; persist(); render(); } catch(e) { fail(e); } };
$('[data-action="start"]').onclick = () => processQueue().catch(fail);
$('[data-action="pause"]').onclick = () => { if (preparing) return toast('组件下载期间请等待，重新启动后可续传'); paused = !paused; $('[data-action="pause"]').textContent = paused ? '恢复队列' : '暂停队列'; if (!paused && !running) processQueue().catch(fail); else toast('将在当前视频完成后暂停'); render(); };
$('[data-action="clear"]').onclick = () => { if (running || exporting) return; queue = []; persist(); select(0); };
$('[data-queue]').onclick = e => { if (e.target.dataset.remove !== undefined) { const i = Number(e.target.dataset.remove); if (queue[i].state === 'active' || exporting) return; queue.splice(i, 1); persist(); select(Math.min(selected, queue.length - 1)); } else { const row = e.target.closest('[data-select]'); if(row) select(Number(row.dataset.select)); } };
$('[data-action="model"]').onclick = () => status().then(() => toast($('.health strong').textContent + '；' + $('.compact-model-status strong').textContent)).catch(fail);
$('.health .icon-button').onclick = () => status().catch(fail);
modelSelect.onchange = () => status().catch(fail);
$('[data-presets]').innerHTML = Object.keys(presets).map(name => `<button class="preset" data-preset="${name}">${name}</button>`).join('');
$('[data-presets]').onclick = e => { if (presets[e.target.dataset.preset]) { parameters = {...presets[e.target.dataset.preset]}; saveParameters(); } };
$('[data-action="reset-parameters"]').onclick = () => { parameters = {...defaults}; saveParameters(); };
document.querySelectorAll('[data-parameter]').forEach(input => input.oninput = () => { parameters[input.dataset.parameter] = input.type === 'checkbox' ? input.checked : Number(input.value); saveParameters(); });
$('[data-action="play-preview"]').onclick = () => { if (!previewPath) return; if (preview.paused) preview.play().catch(fail); else preview.pause(); };
preview.onplay = () => $('[data-play-icon]').hidden = true; preview.onpause = () => $('[data-play-icon]').hidden = false;
$('[data-action="export-adjusted"]').onclick = async () => {
  const job = queue[selected]; if (!job?.result || running || exporting) return;
  exporting = true; render();
  try { const result = await invoke('apply_parameters', {request:{rawPath:job.result.rawDepthPath, outputPath:job.result.outputDirectory + '/' + job.name.replace(/\.[^.]+$/, '') + '_depth_adjusted.mp4', parameters:controls(parameters)}}); job.adjustedPath = result.outputVideoPath; persist(); toast(`已导出：${job.adjustedPath}`); }
  catch(e) { fail(e); } finally { exporting = false; render(); }
};
const dialog = $('[data-compare-dialog]');
const sourceVideo = document.createElement('video'), depthVideo = document.createElement('video');
for (const v of [sourceVideo, depthVideo]) { v.muted = true; v.loop = true; v.className = 'real-video'; }
$('[data-compare-source]').replaceChildren(sourceVideo); $('.compare-depth').replaceChildren(depthVideo);
function wipe() { const value = Number($('[data-compare-wipe]').value); $('[data-compare-source]').style.clipPath = `inset(0 ${100-value}% 0 0)`; $('[data-compare-divider]').style.left = value + '%'; }
$('[data-action="play-preview"]').ondblclick = () => { const job = queue[selected]; if(!previewPath || !job) return; preview.pause(); sourceVideo.src = api.core.convertFileSrc(job.path); depthVideo.src = api.core.convertFileSrc(previewPath); $('[data-compare-name]').textContent = job.name; dialog.showModal(); wipe(); Promise.all([sourceVideo.play(), depthVideo.play()]).catch(fail); };
sourceVideo.ontimeupdate = () => { if (Math.abs(sourceVideo.currentTime - depthVideo.currentTime) > .15) depthVideo.currentTime = sourceVideo.currentTime; };
$('[data-action="close-compare"]').onclick = () => dialog.close(); dialog.onclose = () => { sourceVideo.pause(); depthVideo.pause(); };
$('[data-compare-wipe]').oninput = wipe;
async function init() {
  await api.event.listen('depth-progress', ({payload}) => { const job = queue.find(j => j.state === 'active'); if (job) { job.progress = payload.percent; job.message = payload.message; render(); } else if (preparing) $('[data-note] span').textContent = payload.message; });
  await api.event.listen('tauri://drag-drop', async ({payload}) => { for (const path of payload.paths || []) { try { add([await invoke('load_input_video', {path})]); } catch(e) { fail(e); } } });
  await status();
}
$('.queue-foot span:last-child').textContent = '失败任务点击开始重试 · 关闭后保留队列';
select(0); init().catch(fail);
