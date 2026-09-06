export const MODEL_OPTIONS = Object.freeze({
  gemdepth_vda_8f: Object.freeze({
    label: "GemDepth-VDA · 8-frame",
    shortLabel: "GemDepth 8F",
    inputSize: 392,
    precision: "FP16 autocast",
    depthType: "Relative Depth",
    inferLen: 8,
    overlap: 4,
    interpLen: 2,
  }),
  vda_base_fp16_relative: Object.freeze({
    label: "Video Depth Anything Base · FP16 · Relative",
    shortLabel: "VDA Base",
    inputSize: 322,
    precision: "FP16",
    depthType: "Relative Depth",
    inferLen: 32,
    overlap: 10,
    interpLen: 8,
  }),
});

export const CONTROL_DEFINITIONS = Object.freeze({
  farPoint: Object.freeze({ min: 0, max: 99, step: 1, defaultValue: 0, suffix: "%" }),
  nearPoint: Object.freeze({ min: 1, max: 100, step: 1, defaultValue: 100, suffix: "%" }),
  midtone: Object.freeze({ min: -100, max: 100, step: 1, defaultValue: 0, suffix: "" }),
  contrast: Object.freeze({ min: 0, max: 300, step: 1, defaultValue: 100, suffix: "%" }),
  brightness: Object.freeze({ min: -100, max: 100, step: 1, defaultValue: 0, suffix: "" }),
  smooth: Object.freeze({ min: 0, max: 50, step: 1, defaultValue: 0, suffix: "" }),
});

export const PRESETS = Object.freeze({
  neutral: Object.freeze({ label: "中性", farPoint: 0, nearPoint: 100, midtone: 0, contrast: 100, brightness: 0, smooth: 0, invert: false }),
  crisp: Object.freeze({ label: "清晰层次", farPoint: 4, nearPoint: 96, midtone: 8, contrast: 132, brightness: 0, smooth: 1, invert: false }),
  soft: Object.freeze({ label: "柔和稳定", farPoint: 1, nearPoint: 99, midtone: -6, contrast: 88, brightness: 2, smooth: 8, invert: false }),
  controlnet: Object.freeze({ label: "控制视频", farPoint: 3, nearPoint: 97, midtone: 4, contrast: 118, brightness: 0, smooth: 3, invert: false }),
});

export function defaultParameters() {
  return Object.fromEntries(Object.entries(CONTROL_DEFINITIONS).map(([key, definition]) => [key, definition.defaultValue]).concat([["invert", false]]));
}

export function normalizeParameters(value = {}) {
  const result = defaultParameters();
  for (const [key, definition] of Object.entries(CONTROL_DEFINITIONS)) {
    const number = Number(value[key]);
    if (Number.isFinite(number)) result[key] = Math.min(definition.max, Math.max(definition.min, number));
  }
  result.invert = Boolean(value.invert);
  if (result.nearPoint <= result.farPoint) {
    result.nearPoint = Math.min(100, result.farPoint + 1);
  }
  return result;
}

export function formatControlValue(key, value) {
  const definition = CONTROL_DEFINITIONS[key];
  const prefix = ["midtone", "brightness"].includes(key) && Number(value) > 0 ? "+" : "";
  return `${prefix}${Number(value)}${definition?.suffix || ""}`;
}

export function buildParameterConfig({ model, parameters, run = null, input = null, options = {} }) {
  if (!MODEL_OPTIONS[model]) throw new Error(`未知模型：${model}`);
  return {
    schema: "shiyin.video-depth-lab.parameters/v1",
    savedAt: new Date().toISOString(),
    model: { key: model, ...MODEL_OPTIONS[model] },
    inference: {
      inputSize: Number(options.inputSize || MODEL_OPTIONS[model].inputSize),
      targetFps: Number(options.targetFps || 12),
      maxFrames: Number(options.maxFrames || 48),
      maxResolution: Number(options.maxResolution || 960),
    },
    parameters: normalizeParameters(parameters),
    input: input ? { name: input.name, size: input.size } : null,
    lastRun: run ? {
      elapsedSeconds: run.elapsedSeconds,
      outputDirectory: run.outputDirectory,
      normalization: run.normalization,
    } : null,
  };
}

export function parseParameterConfig(value) {
  const parsed = typeof value === "string" ? JSON.parse(value) : value;
  if (!parsed || typeof parsed !== "object" || !parsed.model || !MODEL_OPTIONS[parsed.model.key]) {
    throw new Error("配置缺少有效的模型字段");
  }
  return {
    model: parsed.model.key,
    parameters: normalizeParameters(parsed.parameters),
    inference: parsed.inference || {},
  };
}
