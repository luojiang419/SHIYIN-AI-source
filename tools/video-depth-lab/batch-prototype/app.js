const queue = [
  { name: "fashion_walk_01.mp4", meta: "1920×1080 · 00:42 · 158 MB", state: "active", progress: 58 },
  { name: "studio_turntable.mov", meta: "3840×2160 · 01:18 · 476 MB", state: "waiting", progress: 0 },
  { name: "street_motion_03.mp4", meta: "1920×1080 · 00:27 · 94 MB", state: "waiting", progress: 0 },
];
let paused = false;
let selectedIndex = 0;
const parameters = { far: 8, near: 94, gamma: 0, contrast: 115, smooth: 4, invert: false };
const presets = {
  "默认": { far: 8, near: 94, gamma: 0, contrast: 115, smooth: 4, invert: false },
  "主体增强": { far: 12, near: 90, gamma: 8, contrast: 142, smooth: 7, invert: false },
  "空间层次": { far: 4, near: 98, gamma: -8, contrast: 126, smooth: 3, invert: false },
};
const $ = (selector) => document.querySelector(selector);
const toast = (message) => { const node = $("[data-toast]"); node.textContent = message; node.hidden = false; window.clearTimeout(toast.timer); toast.timer = window.setTimeout(() => { node.hidden = true; }, 2600); };
function render() {
  const active = queue.findIndex((job) => job.state === "active");
  if (selectedIndex >= queue.length) selectedIndex = Math.max(queue.length - 1, 0);
  $("[data-queue]").innerHTML = queue.map((job, index) => `<article class="job ${job.state} ${index === selectedIndex ? "selected" : ""}" data-select="${index}"><span class="thumb">${job.state === "done" ? "✓" : "▶"}</span><div><div class="job-name">${job.name}</div><div class="job-meta">${job.meta}</div>${job.state === "active" ? `<div class="job-progress"><i style="width:${job.progress}%"></i></div>` : ""}</div><div class="job-status">${job.state === "active" ? `${job.progress}% · 推理中` : job.state === "done" ? "已完成" : "等待队列"}<button class="job-remove" data-remove="${index}" title="移除任务">×</button></div></article>`).join("");
  const done = queue.filter((job) => job.state === "done").length;
  $("[data-total]").textContent = `${queue.length} 个视频`;
  $("[data-summary-progress]").textContent = `${Math.min(active + 1, queue.length)} / ${queue.length}`;
  $("[data-summary-bar]").style.width = `${queue.length ? ((done + (active >= 0 ? queue[active].progress / 100 : 0)) / queue.length) * 100 : 0}%`;
  $("[data-queue-count]").textContent = `${queue.length} 个任务 · ${active >= 0 ? "1 个进行中" : "等待开始"}`;
  const current = queue[active];
  $("[data-note]").innerHTML = current ? `<b>${paused ? "队列已暂停" : `正在处理 ${active + 1} / ${queue.length}`}</b><span>${current.name} · ${paused ? "将在恢复后继续" : "正在进行深度推理"}</span>` : `<b>队列等待开始</b><span>添加视频后点击开始批量提取</span>`;
  renderPreview();
}
function renderPreview() {
  const job = queue[selectedIndex];
  const name = job?.name?.replace(/\.[^.]+$/, "") || "等待选择视频";
  const state = job?.state || "waiting";
  const label = state === "done" ? "已完成" : state === "active" ? "处理中" : "等待队列";
  $("[data-preview-name]").textContent = `${name}_depth.mp4`;
  $("[data-preview-info]").textContent = state === "done" ? "H.264 · 相对深度 · 可导出到指定目录" : state === "active" ? `${job.progress}% · 推理结果将在完成后保存` : "尚未生成 · 参数将在本任务开始时应用";
  $("[data-preview-state]").textContent = label;
  $("[data-preview-state]").className = `preview-state ${state}`;
  const scene = $("[data-depth-scene]");
  scene.style.filter = `contrast(${parameters.contrast}%) brightness(${1 + parameters.gamma / 150}) invert(${parameters.invert ? 1 : 0}) blur(${parameters.smooth / 12}px)`;
  scene.style.setProperty("--far", `${parameters.far}%`);
  scene.style.setProperty("--near", `${parameters.near}%`);
}
function renderParameters() {
  Object.entries(parameters).forEach(([key, value]) => {
    const input = $(`[data-parameter="${key}"]`); const output = $(`[data-value="${key}"]`);
    if (!input) return; if (input.type === "checkbox") input.checked = value; else input.value = value;
    if (output) output.textContent = key === "far" || key === "near" || key === "contrast" ? `${value}%` : value;
  });
  $("[data-presets]").innerHTML = Object.keys(presets).map((name) => `<button type="button" data-preset="${name}" class="preset ${JSON.stringify(parameters) === JSON.stringify(presets[name]) ? "active" : ""}">${name}</button>`).join("");
  renderPreview();
}
function addFiles(files) { [...files].forEach((file) => queue.push({ name: file.name, meta: "等待读取视频信息", state: "waiting", progress: 0 })); render(); toast(`已添加 ${files.length} 个视频到队列`); }
$("[data-action='add']").onclick = () => $("[data-input]").click(); $("[data-input]").onchange = (event) => addFiles(event.target.files);
$("[data-queue]").onclick = (event) => { const removeIndex = Number(event.target.dataset.remove); if (Number.isInteger(removeIndex)) { queue.splice(removeIndex, 1); render(); toast("已从队列移除视频"); return; } const item = event.target.closest("[data-select]"); if (item) { selectedIndex = Number(item.dataset.select); render(); toast(`已切换到 ${queue[selectedIndex].name} 的结果预览`); } };
$("[data-action='clear']").onclick = () => { queue.splice(0); render(); toast("队列已清空"); };
$("[data-action='pause']").onclick = (event) => { paused = !paused; event.target.textContent = paused ? "恢复队列" : "暂停队列"; render(); toast(paused ? "队列将在当前安全点暂停" : "队列已恢复"); };
$("[data-action='start']").onclick = () => { if (!queue.length) return toast("请先导入至少一个视频"); const job = queue.find((item) => item.state === "waiting"); if (job) { job.state = "active"; job.progress = 1; } paused = false; $("[data-action='pause']").textContent = "暂停队列"; render(); toast("批量提取已开始，任务将严格串行执行"); };
$("[data-action='path']").onclick = () => toast("正式版将调用 Tauri 原生目录选择器"); $("[data-action='model']").onclick = () => toast("模型尚未下载：正式版将在首次开始时从魔塔校验并下载");
$("[data-action='play-preview']").onclick = () => { const icon = $("[data-play-icon]"); icon.textContent = icon.textContent === "▶" ? "Ⅱ" : "▶"; toast(icon.textContent === "Ⅱ" ? "正在播放深度视频预览" : "已暂停预览"); };
$("[data-action='reset-parameters']").onclick = () => { Object.assign(parameters, presets["默认"]); renderParameters(); toast("已恢复默认深度参数"); };
$("[data-presets]").onclick = (event) => { const name = event.target.dataset.preset; if (name) { Object.assign(parameters, presets[name]); renderParameters(); toast(`已应用“${name}”预设`); } };
document.querySelectorAll("[data-parameter]").forEach((input) => input.addEventListener("input", () => { parameters[input.dataset.parameter] = input.type === "checkbox" ? input.checked : Number(input.value); renderParameters(); }));
document.addEventListener("dragover", (event) => event.preventDefault()); document.addEventListener("drop", (event) => { event.preventDefault(); if (event.dataTransfer.files.length) addFiles(event.dataTransfer.files); });
setInterval(() => { if (paused) return; const job = queue.find((item) => item.state === "active"); if (!job) return; job.progress = Math.min(100, job.progress + 1); if (job.progress === 100) { job.state = "done"; const next = queue.find((item) => item.state === "waiting"); if (next) { next.state = "active"; next.progress = 1; } } render(); }, 1150);
render(); renderParameters();
