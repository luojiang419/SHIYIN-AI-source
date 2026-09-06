import {
  CONTROL_DEFINITIONS,
  MODEL_OPTIONS,
  PRESETS,
  buildParameterConfig,
  defaultParameters,
  formatControlValue,
  normalizeParameters,
  parseParameterConfig,
} from "./controls.mjs";

const tauri = window.__TAURI__;
const invoke = tauri?.core?.invoke;
const convertFileSrc = tauri?.core?.convertFileSrc;
const state = {
  runtime: null,
  input: null,
  outputRoot: "",
  result: null,
  currentVideoPath: "",
  parameters: defaultParameters(),
  busy: false,
};

const $ = (selector) => document.querySelector(selector);
const elements = {
  runtime: $(".runtime-status"), runtimeTitle: $("[data-runtime-title]"), runtimeDetail: $("[data-runtime-detail]"),
  inputStage: $(".input-stage"), inputVideo: $("[data-input-video]"), inputEmpty: $("[data-input-empty]"), inputName: $("[data-input-name]"), inputMeta: $("[data-input-meta]"),
  inputActions: $("[data-input-actions]"),
  outputVideo: $("[data-output-video]"), outputEmpty: $("[data-output-empty]"), outputMeta: $("[data-output-meta]"), previewState: $("[data-preview-state]"),
  processing: $("[data-processing]"), processingTitle: $("[data-processing-title]"), processingDetail: $("[data-processing-detail]"), progressBar: $("[data-progress-bar]"),
  status: $("[data-status-message]"), outputRoot: $("[data-output-root]"), runSummary: $("[data-run-summary]"), toastRegion: $("[data-toast-region]"),
};

function errorMessage(error) {
  if (typeof error === "string") return error;
  return error?.message || error?.error || String(error || "未知错误");
}

function toast(message, type = "success") {
  const node = document.createElement("div");
  node.className = `toast ${type}`;
  node.textContent = message;
  elements.toastRegion.append(node);
  setTimeout(() => node.remove(), 4200);
}

function setStatus(message) { elements.status.textContent = message; }

function setBusy(busy, title = "正在处理", detail = "0%") {
  state.busy = busy;
  elements.processing.hidden = !busy;
  elements.processingTitle.textContent = title;
  elements.processingDetail.textContent = detail;
  document.querySelectorAll("button, select, input").forEach((node) => {
    if (node.matches('[data-action="refresh-runtime"]')) return;
    if (node.matches('[data-action="cancel-model"]')) {
      node.hidden = !busy;
      node.disabled = !busy;
      return;
    }
    node.disabled = busy || node.dataset.action === "run-model" && (!state.input || !state.runtime?.ready)
      || ["apply-parameters", "export-video", "open-output"].includes(node.dataset.action) && !state.result;
  });
}

function setProgress(percent, message) {
  elements.processingTitle.textContent = message || "正在处理";
  elements.processingDetail.textContent = `${percent}% · ${MODEL_OPTIONS[currentModel()].shortLabel}`;
  elements.progressBar.style.setProperty("--progress", `${percent}%`);
  setStatus(`${percent}% · ${message}`);
}

function currentModel() { return $("[data-field='model']").value; }

function inferenceOptions() {
  return {
    inputSize: Number($("[data-field='inputSize']").value),
    targetFps: Number($("[data-field='targetFps']").value),
    maxFrames: Number($("[data-field='maxFrames']").value),
    maxResolution: Number($("[data-field='maxResolution']").value),
  };
}

function formatDuration(seconds) {
  const value = Math.max(0, Math.round(Number(seconds) || 0));
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor(value % 3600 / 60);
  const remaining = value % 60;
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, "0")}:${String(remaining).padStart(2, "0")}`
    : `${minutes}:${String(remaining).padStart(2, "0")}`;
}

function updateExtractionSummary() {
  const options = inferenceOptions();
  const fps = options.targetFps < 0 ? "原始 FPS" : `${options.targetFps} FPS`;
  const frames = options.maxFrames < 0 ? "全部帧" : `前 ${options.maxFrames} 帧`;
  const resolution = options.maxResolution < 0 ? "原始分辨率" : `最长边 ${options.maxResolution}`;
  const complete = options.targetFps < 0 && options.maxFrames < 0 && options.maxResolution < 0;
  const estimate = state.input?.frameCount ? `，预计 ${state.input.frameCount.toLocaleString()} 帧` : "";
  elements.runSummary.textContent = complete
    ? `完整提取：${fps} · ${frames} · ${resolution}${estimate}。长视频耗时和磁盘占用较高，可随时停止。`
    : `采样提取：${fps} · ${frames} · ${resolution}${estimate}。`;
  elements.runSummary.dataset.complete = complete ? "true" : "false";
}

function renderModelNote() {
  const model = MODEL_OPTIONS[currentModel()];
  $("[data-model-note]").textContent = `${model.inferLen}-frame · overlap ${model.overlap} · ${model.precision}`;
}

function updateControl(key, value) {
  const definition = CONTROL_DEFINITIONS[key];
  const input = $(`[data-field='${key}']`);
  const output = $(`[data-control='${key}'] output`);
  input.min = definition.min;
  input.max = definition.max;
  input.step = definition.step;
  input.value = value;
  output.textContent = formatControlValue(key, value);
  const fill = (Number(value) - definition.min) / (definition.max - definition.min) * 100;
  input.style.setProperty("--fill", `${fill}%`);
}

function renderParameters(parameters = state.parameters) {
  state.parameters = normalizeParameters(parameters);
  for (const key of Object.keys(CONTROL_DEFINITIONS)) updateControl(key, state.parameters[key]);
  $("[data-field='invert']").checked = state.parameters.invert;
  markPreset();
  applyApproximatePreview();
}

function readParameters() {
  const value = {};
  for (const key of Object.keys(CONTROL_DEFINITIONS)) value[key] = Number($(`[data-field='${key}']`).value);
  value.invert = $("[data-field='invert']").checked;
  state.parameters = normalizeParameters(value);
  return state.parameters;
}

function markPreset() {
  document.querySelectorAll("[data-preset]").forEach((button) => {
    const preset = PRESETS[button.dataset.preset];
    button.classList.toggle("active", JSON.stringify(normalizeParameters(preset)) === JSON.stringify(state.parameters));
  });
}

function buildPresets() {
  const root = $("[data-presets]");
  root.replaceChildren(...Object.entries(PRESETS).map(([key, preset]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "preset-button";
    button.dataset.preset = key;
    button.textContent = preset.label;
    button.addEventListener("click", () => { renderParameters(preset); markPending(); });
    return button;
  }));
}

function applyApproximatePreview() {
  const p = state.parameters;
  const brightness = Math.max(0.05, 1 + p.brightness / 100);
  const contrast = Math.max(0, p.contrast / 100);
  const blur = p.smooth ? Math.min(3, p.smooth / 18) : 0;
  elements.outputVideo.style.filter = `brightness(${brightness}) contrast(${contrast}) invert(${p.invert ? 1 : 0}) blur(${blur}px)`;
}

function markPending() {
  readParameters();
  applyApproximatePreview();
  if (state.result) {
    elements.previewState.hidden = false;
    elements.previewState.textContent = "滤镜预览 · 点击应用参数精确重算";
  }
}

function setVideoSource(video, path) {
  video.pause();
  video.removeAttribute("src");
  video.load();
  video.src = convertFileSrc(path);
  video.hidden = false;
  video.load();
}

async function refreshRuntime() {
  elements.runtime.dataset.runtimeState = "checking";
  elements.runtimeTitle.textContent = "正在检查本地模型";
  elements.runtimeDetail.textContent = "核验 CUDA、FFmpeg 与两组权重";
  try {
    state.runtime = await invoke("get_runtime_status");
    const readyCount = state.runtime.models.filter((model) => model.ready).length;
    elements.runtime.dataset.runtimeState = state.runtime.ready ? "ready" : "error";
    elements.runtimeTitle.textContent = state.runtime.ready ? "两组视频深度模型已就绪" : `${readyCount}/2 模型已部署`;
    elements.runtimeDetail.textContent = `${state.runtime.gpu || "未检测 GPU"} · Torch ${state.runtime.torchVersion} · CUDA ${state.runtime.cudaVersion || "不可用"}`;
    setStatus(state.runtime.ready ? "运行环境就绪，可选择视频开始对比" : "运行环境不完整，请运行 setup.ps1");
  } catch (error) {
    state.runtime = { ready: false };
    elements.runtime.dataset.runtimeState = "error";
    elements.runtimeTitle.textContent = "运行环境尚未就绪";
    elements.runtimeDetail.textContent = errorMessage(error);
    setStatus("请先在工具目录运行 setup.ps1");
  }
  setBusy(false);
}

async function acceptInput(payload) {
  if (!payload) return;
  state.input = payload;
  state.result = null;
  state.currentVideoPath = "";
  setVideoSource(elements.inputVideo, payload.path);
  elements.inputEmpty.hidden = true;
  elements.inputName.hidden = false;
  elements.inputName.textContent = payload.name;
  elements.inputActions.hidden = false;
  const dimensions = payload.width && payload.height ? `${payload.width}×${payload.height}` : "未知尺寸";
  const fps = payload.fps ? `${Number(payload.fps).toFixed(3).replace(/\.0+$/, "")} FPS` : "未知 FPS";
  const frameCount = payload.frameCount ? `${Number(payload.frameCount).toLocaleString()} 帧` : "帧数待解码";
  elements.inputMeta.textContent = `${dimensions} · ${fps} · ${formatDuration(payload.duration)} · ${frameCount} · ${(payload.size / 1024 / 1024).toFixed(1)} MB`;
  elements.outputVideo.hidden = true;
  elements.outputEmpty.hidden = false;
  elements.previewState.hidden = true;
  updateExtractionSummary();
  setStatus(`已选择 ${payload.name}，请选择模型并开始测试`);
  setBusy(false);
}

function removeVideo() {
  if (state.busy) return;
  state.input = null;
  state.result = null;
  state.currentVideoPath = "";
  elements.inputVideo.pause();
  elements.inputVideo.removeAttribute("src");
  elements.inputVideo.load();
  elements.inputVideo.hidden = true;
  elements.inputEmpty.hidden = false;
  elements.inputName.hidden = true;
  elements.inputActions.hidden = true;
  elements.inputMeta.textContent = "等待视频";
  elements.outputVideo.pause();
  elements.outputVideo.removeAttribute("src");
  elements.outputVideo.load();
  elements.outputVideo.hidden = true;
  elements.outputEmpty.hidden = false;
  elements.outputMeta.textContent = "RELATIVE · H.264";
  elements.previewState.hidden = true;
  updateExtractionSummary();
  setStatus("已移除输入视频，可重新选择或拖入视频");
  setBusy(false);
}

async function chooseVideo() {
  try { await acceptInput(await invoke("choose_input_video")); }
  catch (error) { toast(errorMessage(error), "error"); }
}

async function cancelModel() {
  if (!state.busy) return;
  try {
    const stopped = await invoke("cancel_inference");
    if (stopped) {
      elements.processingDetail.textContent = "正在终止 worker…";
      setStatus("正在停止当前模型任务");
    }
  } catch (error) { toast(errorMessage(error), "error"); }
}

async function runModel() {
  if (!state.input || state.busy) return;
  setBusy(true, `正在运行 ${MODEL_OPTIONS[currentModel()].shortLabel}`, "0% · 启动 worker");
  setProgress(0, "正在启动模型任务");
  try {
    const result = await invoke("run_inference", { request: {
      inputPath: state.input.path,
      outputRoot: state.outputRoot,
      model: currentModel(),
      ...inferenceOptions(),
      parameters: readParameters(),
    }});
    state.result = result;
    state.currentVideoPath = result.outputVideoPath;
    setVideoSource(elements.outputVideo, state.currentVideoPath);
    elements.outputVideo.style.filter = "none";
    elements.outputEmpty.hidden = true;
    elements.previewState.hidden = false;
    elements.previewState.textContent = `${result.model.label} · ${result.elapsedSeconds}s`;
    elements.outputMeta.textContent = `${result.input.processedWidth}×${result.input.processedHeight} · ${result.input.processedFrames} 帧`;
    elements.runSummary.textContent = `${result.input.completeExtraction ? "完整" : "采样"}提取完成：${result.input.processedFrames} 帧，本次耗时 ${result.elapsedSeconds}s。`;
    setStatus(`测试完成：${result.outputDirectory}`);
    toast(`${result.model.label} 深度视频生成完成`);
  } catch (error) {
    setStatus(`模型测试失败：${errorMessage(error)}`);
    toast(errorMessage(error), "error");
  } finally { setBusy(false); }
}

async function applyParameters() {
  if (!state.result || state.busy) return;
  const outputPath = `${state.result.outputDirectory}/depth-preview-adjusted.mp4`;
  setBusy(true, "正在精确应用深度参数", "0% · 读取 Relative Depth");
  try {
    const result = await invoke("apply_parameters", { request: { rawPath: state.result.rawDepthPath, outputPath, parameters: readParameters() }});
    state.currentVideoPath = result.outputVideoPath;
    setVideoSource(elements.outputVideo, state.currentVideoPath);
    elements.outputVideo.style.filter = "none";
    elements.previewState.hidden = false;
    elements.previewState.textContent = "参数已精确应用";
    setStatus(`参数视频已更新：${state.currentVideoPath}`);
    toast("深度参数已精确重算");
  } catch (error) { toast(errorMessage(error), "error"); }
  finally { setBusy(false); }
}

async function chooseOutput() {
  try {
    const value = await invoke("choose_output_directory");
    if (value) { state.outputRoot = value; elements.outputRoot.textContent = value; }
  } catch (error) { toast(errorMessage(error), "error"); }
}

async function exportVideo() {
  try {
    const name = state.input ? `${state.input.name.replace(/\.[^.]+$/, "")}-${MODEL_OPTIONS[currentModel()].shortLabel}-depth.mp4` : "depth-video.mp4";
    const path = await invoke("export_depth_video", { sourcePath: state.currentVideoPath, suggestedName: name });
    if (path) toast(`已导出：${path}`);
  } catch (error) { toast(errorMessage(error), "error"); }
}

async function exportConfig() {
  try {
    const config = buildParameterConfig({ model: currentModel(), parameters: readParameters(), run: state.result, input: state.input, options: inferenceOptions() });
    const path = await invoke("export_parameter_config", { content: JSON.stringify(config, null, 2), suggestedName: `${MODEL_OPTIONS[currentModel()].shortLabel}-参数.json` });
    if (path) toast(`配置已保存：${path}`);
  } catch (error) { toast(errorMessage(error), "error"); }
}

async function importConfig() {
  try {
    const content = await invoke("import_parameter_config");
    if (!content) return;
    const config = parseParameterConfig(content);
    $("[data-field='model']").value = config.model;
    for (const [key, value] of Object.entries(config.inference)) {
      const input = $(`[data-field='${key}']`);
      if (input && value !== undefined) input.value = value;
    }
    renderModelNote();
    renderParameters(config.parameters);
    markPending();
    toast("模型与参数配置已导入");
  } catch (error) { toast(errorMessage(error), "error"); }
}

async function openOutput() {
  try { await invoke("open_output_directory", { path: state.result.outputDirectory }); }
  catch (error) { toast(errorMessage(error), "error"); }
}

function bind() {
  $("[data-action='choose-video']").addEventListener("click", (event) => { if (event.target !== elements.inputVideo && !event.target.closest(".input-actions")) chooseVideo(); });
  $("[data-action='choose-video']").addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); chooseVideo(); } });
  $("[data-action='refresh-runtime']").addEventListener("click", refreshRuntime);
  $("[data-action='replace-video']").addEventListener("click", chooseVideo);
  $("[data-action='remove-video']").addEventListener("click", removeVideo);
  $("[data-action='choose-output']").addEventListener("click", chooseOutput);
  $("[data-action='run-model']").addEventListener("click", runModel);
  $("[data-action='cancel-model']").addEventListener("click", cancelModel);
  $("[data-action='apply-parameters']").addEventListener("click", applyParameters);
  $("[data-action='export-video']").addEventListener("click", exportVideo);
  $("[data-action='export-config']").addEventListener("click", exportConfig);
  $("[data-action='import-config']").addEventListener("click", importConfig);
  $("[data-action='open-output']").addEventListener("click", openOutput);
  $("[data-action='reset-controls']").addEventListener("click", () => { renderParameters(defaultParameters()); markPending(); });
  $("[data-field='model']").addEventListener("change", (event) => {
    const model = MODEL_OPTIONS[event.target.value];
    $("[data-field='inputSize']").value = model.inputSize;
    renderModelNote();
    state.result = null;
    elements.outputVideo.hidden = true;
    elements.outputEmpty.hidden = false;
    setBusy(false);
    setStatus(`已切换到 ${model.label}，需重新运行模型测试`);
  });
  for (const field of ["targetFps", "maxFrames", "maxResolution"]) {
    $(`[data-field='${field}']`).addEventListener("change", updateExtractionSummary);
  }
  for (const key of Object.keys(CONTROL_DEFINITIONS)) {
    const input = $(`[data-field='${key}']`);
    input.addEventListener("input", () => { updateControl(key, input.value); markPending(); });
  }
  $("[data-field='invert']").addEventListener("change", markPending);
  window.addEventListener("dragover", (event) => { event.preventDefault(); elements.inputStage.classList.add("is-dragging"); });
  window.addEventListener("dragleave", () => elements.inputStage.classList.remove("is-dragging"));
  window.addEventListener("drop", (event) => { event.preventDefault(); elements.inputStage.classList.remove("is-dragging"); });
  tauri?.event?.listen("tauri://drag-drop", async ({ payload }) => {
    const path = payload?.paths?.[0];
    if (!path) return;
    try { await acceptInput(await invoke("load_input_video", { path })); }
    catch (error) { toast(errorMessage(error), "error"); }
  });
  tauri?.event?.listen("depth-progress", ({ payload }) => setProgress(payload.percent || 0, payload.message || "正在处理"));
}

buildPresets();
renderParameters();
renderModelNote();
updateExtractionSummary();
bind();
refreshRuntime();
