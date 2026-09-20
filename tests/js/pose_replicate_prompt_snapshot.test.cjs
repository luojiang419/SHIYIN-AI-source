const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('static/js/canvas-special-nodes.js', 'utf8').replace(/\r\n/g, '\n');
const start = source.indexOf("        root.querySelector('[data-special-action=\"run-pose-replicate\"]')");
assert.ok(start >= 0);
const binding = source.slice(start, source.indexOf('\n\n        if(action?.url)', start));

async function check(value) {
    let click, resume;
    const generated = [];
    const control = {value};
    const node = {poseReplicateMode:'depth', poseDepthBaseUrl:'depth', poseReplicatePrompt:'旧补充要求'};
    const ctx = {
        root:{querySelector:selector => selector.includes('run-pose-replicate')
            ? {addEventListener:(_event, callback) => {click = callback;}} : control},
        node, String, Math, Number, Promise,
        options:{generatePoseReplicate:async (_node, _inputs, prompt) => generated.push(prompt)},
        applyPoseDepthGlobalControls:() => new Promise(resolve => {resume = resolve;}),
        poseReplicateInput:() => ({url:'reference'}),
        poseReplicateInputs:() => [{url:'garment'}],
        poseReplicateControlItem:() => ({url:'depth'}),
        activeDepthMapStatus:() => ({ready:true}), notify(){},
    };
    vm.runInNewContext(binding, ctx);
    const pending = click({preventDefault(){}, stopPropagation(){}});
    // 模拟同步深度期间节点被刷新，以及用户为下一次任务改写输入框。
    node.poseReplicatePrompt = '同步期间读回的旧内容';
    control.value = '下一轮的补充要求';
    resume(true);
    await pending;
    assert.deepEqual(generated, [value.trim()]);
}

(async () => {
    await check('');
    await check('  粗斜纹，橙黄色车线。不改变人物身份。  ');
    console.log('pose replicate submits the clicked text, including clearing, across depth sync');
})().catch(error => {console.error(error); process.exitCode = 1;});
