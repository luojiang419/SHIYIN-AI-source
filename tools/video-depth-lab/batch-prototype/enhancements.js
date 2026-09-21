const adjustmentStorageKey = "shiyin-batch-depth-prototype-adjustments-v1";
const adjustmentStore = JSON.parse(localStorage.getItem(adjustmentStorageKey) || "{}");
const currentJobKey = () => queue[selectedIndex]?.name || "default";
const persistAdjustments = () => { adjustmentStore[currentJobKey()] = { ...parameters }; localStorage.setItem(adjustmentStorageKey, JSON.stringify(adjustmentStore)); };
const restoreAdjustments = () => { Object.assign(parameters, presets["默认"], adjustmentStore[currentJobKey()] || {}); renderParameters(); };

document.querySelectorAll("[data-parameter]").forEach((input) => input.addEventListener("input", () => {
  parameters[input.dataset.parameter] = input.type === "checkbox" ? input.checked : Number(input.value);
  persistAdjustments();
}, true));
document.querySelector("[data-presets]").addEventListener("click", () => setTimeout(persistAdjustments));
document.querySelector("[data-action='reset-parameters']").addEventListener("click", () => setTimeout(persistAdjustments));
document.querySelector("[data-queue]").addEventListener("click", (event) => {
  if (!event.target.closest("[data-select]")) return;
  persistAdjustments();
  setTimeout(restoreAdjustments);
}, true);

const compareDialog = document.querySelector("[data-compare-dialog]");
const compareWipe = document.querySelector("[data-compare-wipe]");
const compareSource = document.querySelector("[data-compare-source]");
const compareDivider = document.querySelector("[data-compare-divider]");
const compareDepth = document.querySelector("[data-compare-depth]");
function applyCompareWipe() { const value = `${compareWipe.value}%`; compareSource.style.clipPath = `inset(0 ${100 - Number(compareWipe.value)}% 0 0)`; compareDivider.style.left = value; }
function openCompare() { persistAdjustments(); compareDepth.style.filter = document.querySelector("[data-depth-scene]").style.filter; compareDepth.style.setProperty("--far", `${parameters.far}%`); compareDepth.style.setProperty("--near", `${parameters.near}%`); document.querySelector("[data-compare-name]").textContent = queue[selectedIndex]?.name || "等待选择视频"; compareDialog.showModal(); applyCompareWipe(); }
document.querySelector("[data-action='play-preview']").addEventListener("dblclick", (event) => { event.preventDefault(); openCompare(); });
document.querySelector("[data-action='close-compare']").onclick = () => compareDialog.close();
compareWipe.oninput = applyCompareWipe;
document.querySelector("[data-action='export-adjusted']").onclick = () => { persistAdjustments(); const name = (queue[selectedIndex]?.name || "depth-video").replace(/\.[^.]+$/, ""); toast(`正在重新编码 ${name}_depth_adjusted.mp4；已保存本视频的调参数据`); };
restoreAdjustments();
