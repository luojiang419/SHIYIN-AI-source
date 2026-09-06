import assert from "node:assert/strict";
import test from "node:test";

import { MODEL_OPTIONS, buildParameterConfig, defaultParameters, normalizeParameters, parseParameterConfig } from "../frontend/controls.mjs";

test("模型注册项包含真实 8-frame 与 VDA Base 配置", () => {
  assert.deepEqual(Object.keys(MODEL_OPTIONS), ["gemdepth_vda_8f", "vda_base_fp16_relative"]);
  assert.equal(MODEL_OPTIONS.gemdepth_vda_8f.inferLen, 8);
  assert.equal(MODEL_OPTIONS.vda_base_fp16_relative.precision, "FP16");
  assert.equal(MODEL_OPTIONS.vda_base_fp16_relative.depthType, "Relative Depth");
});
test("参数归一化遵守扩大后的边界", () => {
  const value = normalizeParameters({ farPoint: -2, nearPoint: 200, contrast: 999, brightness: -999, invert: 1 });
  assert.equal(value.farPoint, 0);
  assert.equal(value.nearPoint, 100);
  assert.equal(value.contrast, 300);
  assert.equal(value.brightness, -100);
  assert.equal(value.invert, true);
});

test("版本化配置可完整往返模型与参数", () => {
  const config = buildParameterConfig({ model: "gemdepth_vda_8f", parameters: { ...defaultParameters(), smooth: 7 }, options: { inputSize: 392, targetFps: 12, maxFrames: 48, maxResolution: 960 } });
  const parsed = parseParameterConfig(JSON.stringify(config));
  assert.equal(parsed.model, "gemdepth_vda_8f");
  assert.equal(parsed.parameters.smooth, 7);
  assert.equal(parsed.inference.inputSize, 392);
});
