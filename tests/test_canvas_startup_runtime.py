"""执行真实启动脚本，验证冷启动请求时序及页面初始化回退。"""
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_early_canvas_request_and_dom_startup():
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const boot = fs.readFileSync('static/js/canvas-startup.js', 'utf8');
const source = fs.readFileSync('static/js/canvas.js', 'utf8');
const deferred = () => {
    let resolve;
    const promise = new Promise(done => resolve = done);
    return {promise, resolve};
};
function start(search, fetch) {
    const context = vm.createContext({window:{location:{search}}, URLSearchParams,
        performance:{now:() => 25}, fetch});
    vm.runInContext(boot, context);
    return context.window.CanvasStartup;
}
(async () => {
    let requests = [];
    const response = deferred();
    const startup = start('?id=board%2Fone', url => {
        requests.push(url);
        return response.promise;
    });
    // DOM/编辑器尚不存在，请求已发出；切换 ID 不能误消费启动项目。
    assert.deepEqual(requests, ['/api/canvases/board%2Fone']);
    assert.equal(startup.takeCanvas('another-board'), null);
    const initial = startup.takeCanvas('board/one');
    assert.equal(startup.takeCanvas('board/one'), null);
    const data = {canvas:{id:'board/one', nodes:[{id:'n1', type:'text'}]}};
    response.resolve({ok:true, json:async () => data});
    assert.equal((await initial).data, data);
    assert.equal(startup.timings.dataReadyAt, 25);
    const empty = start('', () => {throw new Error('must not request without id');});
    assert.equal(empty.takeCanvas(''), null);

    // 错误在消费前也不会成为未处理 rejection，JSON 和网络失败均可交给编辑器处理。
    for(const fetch of [
        async () => {throw new Error('offline');},
        async () => ({ok:false, status:404}),
        async () => ({ok:true, json:async () => {throw new Error('invalid json');}}),
    ]) {
        const failed = start('?id=missing', fetch);
        await new Promise(resolve => setImmediate(resolve));
        assert.ok((await failed.takeCanvas('missing')).error);
    }

    // 执行实际 openCanvas，确保预取、后续重开和失败走正确路径。
    const openSource = source.slice(source.indexOf('async function openCanvas(id){'),
        source.indexOf('function migrateLegacySmartCanvasNodes', source.indexOf('async function openCanvas(id){')));
    function editor(startup) {
        const calls = [];
        const ctx = {window:{CanvasStartup:startup, location:{replace:url => calls.push('redirect')}},
            performance:{now:() => 100}, console:{error:() => {}},
            canvas:null, nodes:[], connections:[], selected:new Set(),
            setStatus:() => {}, tr:key => key,
            fetch:async url => {calls.push(url); return {ok:true, json:async () => data};},
            migrateLegacySmartCanvasNodes:nodes => ({nodes, changed:false}),
            localViewportForCanvas:(_id, viewport) => viewport,
            render:() => calls.push('render'),
            scheduleCanvasSecondaryStartup:() => calls.push('secondary'),
            canvasListUrlForProject:() => '/list',
        };
        for(const name of ['resetCascadeRuntimeState', 'rememberCanvasListProject', 'clearClassicHistory',
            'pruneCanvasRuntimeCollections', 'resetTransientRunState', 'sanitizeConnections',
            'setCanvasMode', 'renderCanvasList', 'scheduleSave', 'requestedCanvasListProject',
            'rememberedCanvasListProject']) ctx[name] = () => {};
        vm.createContext(ctx);
        vm.runInContext(openSource, ctx);
        return {ctx, calls};
    }
    const first = editor(start('?id=board%2Fone', async () => ({ok:true, json:async () => data})));
    await first.ctx.openCanvas('board/one');
    assert.deepEqual(first.calls, ['render', 'secondary']);
    assert.equal(first.ctx.classicNavigationStartedAt, 0);
    assert.equal(first.ctx.nodes[0].id, 'n1');
    await first.ctx.openCanvas('board/one');
    assert.deepEqual(first.calls.slice(2), ['/api/canvases/board%2Fone', 'render', 'secondary']);
    assert.equal(first.ctx.classicNavigationStartedAt, 100);
    const failedEditor = editor(start('?id=board%2Fone', async () => ({ok:false, status:404})));
    await failedEditor.ctx.openCanvas('board/one');
    assert.deepEqual(failedEditor.calls, ['redirect']);
    const fallback = editor(undefined);
    await fallback.ctx.openCanvas('board/one');
    assert.deepEqual(fallback.calls, ['/api/canvases/board%2Fone', 'render', 'secondary']);

    // DOM 已就绪但 load 尚未触发、配置请求一直未返回，仍应打开画布。
    const initSource = source.slice(source.indexOf('async function initializeCanvasPage(){'));
    for(const readyState of ['loading', 'interactive', 'complete']) {
        const config = deferred();
        const calls = [];
        let onReady;
        const ctx = {window:{location:{search:'?id=board'}}, document:{readyState,
            addEventListener:(name, callback, opts) => {
                assert.equal(name, 'DOMContentLoaded'); assert.equal(opts.once, true); onReady=callback;
            }}, localStorage:{getItem:() => null}, URLSearchParams,
            performance:{now:() => 10}, CANVAS_THEME_KEY:'canvas_theme', tr:key => key,
            loadConfig:() => {calls.push('config'); return config.promise;},
            openCanvas:async id => {assert.equal(id, 'board'); calls.push('open');}};
        for(const name of ['startCanvasStatsLoop', 'updateCanvasStats', 'applyTheme',
            'loadClassicShortcutLocalFallback', 'loadClassicShortcutSettings', 'applyQuickToolbarState',
            'initOutputCompareEvents', 'initOutputPreviewZoomEvents', 'applyViewport']) ctx[name] = () => {};
        vm.runInNewContext(initSource, ctx);
        if(readyState === 'loading') {assert.deepEqual(calls, []); await onReady();}
        assert.deepEqual(calls, ['config', 'open']);
        assert.equal(ctx.window.onload, undefined);
    }
    console.log('early request, one-shot consumption, failures, fallback and DOM startup passed');
})().catch(error => {console.error(error); process.exitCode=1;});
"""
    result = subprocess.run(
        ["node", "--unhandled-rejections=strict", "-e", script], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_canvas_scripts_keep_order_without_document_write():
    import re

    html = (ROOT / "static/canvas.html").read_text(encoding="utf-8")
    scripts = re.findall(r'<script([^>]*?)src="([^\"]+)"[^>]*>', html)
    assert scripts[0][1].startswith('/static/js/canvas-startup.js?')
    assert html.index('canvas-startup.js') < html.index('rel="stylesheet"')
    assert all('defer' in attrs for attrs, _ in scripts[1:])
    paths = [url.split('?')[0] for _, url in scripts]
    assert '/static/js/i18n.js' not in paths
    assert paths.index('/static/js/i18n-core.js') < paths.index('/static/js/i18n/canvas.js')
    assert paths.index('/static/js/canvas-special-nodes.js') < paths.index('/static/js/canvas.js')
    assert paths.index('/static/js/canvas-legacy-migration.js') < paths.index('/static/js/canvas.js')
    assert '/static/js/i18n/smart-canvas.js' in paths  # 提示词库仍使用 smart.* 翻译。
    assert paths[-1] == '/static/js/canvas.js'
    for path in paths:
        assert (ROOT / path.lstrip('/')).is_file()
