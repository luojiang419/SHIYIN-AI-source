import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "static" / "js" / "canvas-media-queue.js"
CANVAS_HTML = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
SMART_HTML = (ROOT / "static" / "smart-canvas.html").read_text(encoding="utf-8")
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")


def run_node(script: str) -> dict:
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


class CanvasMediaQueueRuntimeTests(unittest.TestCase):
    def test_runtime_handles_fallback_timeout_cancel_and_video_limits(self):
        self.assertTrue(RUNTIME.exists(), "共享媒体队列运行时尚未创建")
        script = r"""
const assert = require('assert');
const {createMediaQueue} = require('./static/js/canvas-media-queue.js');

class FakeImage {
    constructor(kind='image') {
        this.dataset = {previewSrc:'/api/media-preview?id=1', previewState:'queued'};
        if(kind === 'video') this.dataset.previewKind = 'video';
        this.isConnected = true;
        this.listeners = new Map();
        this.attrs = new Map();
    }
    addEventListener(name, listener) {
        if(!this.listeners.has(name)) this.listeners.set(name, new Set());
        this.listeners.get(name).add(listener);
    }
    removeEventListener(name, listener) { this.listeners.get(name)?.delete(listener); }
    emit(name) { [...(this.listeners.get(name) || [])].forEach(listener => listener({type:name, target:this})); }
    set src(value) { this.attrs.set('src', value); }
    get src() { return this.attrs.get('src') || ''; }
    getAttribute(name) { return this.attrs.get(name) || null; }
    removeAttribute(name) { this.attrs.delete(name); }
}

(async () => {
    const fallback = new FakeImage();
    fallback.dataset.originalSrc = '/assets/original.png';
    const fallbackQueue = createMediaQueue({
        name:'fallback',
        collectCandidates:() => [],
        isEligible:() => true,
        fallbackSource:img => img.dataset.originalSrc || '',
        imageTimeoutMs:1000,
    });
    assert.equal(fallbackQueue.start(fallback), true);
    fallback.emit('error');
    assert.equal(fallback.src, '/assets/original.png');
    assert.equal(fallbackQueue.snapshot().activeTotal, 1);
    fallback.emit('load');
    fallback.emit('load');
    assert.equal(fallbackQueue.snapshot().activeTotal, 0);
    assert.equal(fallback.dataset.previewState, 'loaded');

    const hanging = new FakeImage();
    const timeoutQueue = createMediaQueue({
        name:'timeout',
        collectCandidates:() => [],
        isEligible:() => true,
        imageTimeoutMs:10,
        maxAttempts:1,
    });
    assert.equal(timeoutQueue.start(hanging), true);
    await new Promise(resolve => setTimeout(resolve, 30));
    assert.equal(timeoutQueue.snapshot().activeTotal, 0);
    assert.equal(hanging.dataset.previewState, 'failed');
    assert.equal(hanging.getAttribute('src'), null);

    let eligible = true;
    const offscreen = new FakeImage();
    const cancelQueue = createMediaQueue({
        name:'cancel',
        collectCandidates:() => [],
        isEligible:() => eligible,
        imageTimeoutMs:1000,
    });
    cancelQueue.start(offscreen);
    eligible = false;
    cancelQueue.cancelIneligible();
    assert.equal(cancelQueue.snapshot().activeTotal, 0);
    assert.equal(offscreen.dataset.previewState, 'queued');
    assert.equal(offscreen.getAttribute('src'), null);

    const videos = [new FakeImage('video'), new FakeImage('video'), new FakeImage('video')];
    const splitQueue = createMediaQueue({
        name:'split',
        collectCandidates:() => [],
        isEligible:() => true,
        maxActive:6,
        maxImageActive:6,
        maxVideoActive:2,
        videoTimeoutMs:1000,
    });
    assert.equal(splitQueue.start(videos[0]), true);
    assert.equal(splitQueue.start(videos[1]), true);
    assert.equal(splitQueue.start(videos[2]), false);
    assert.equal(splitQueue.snapshot().activeVideo, 2);
    splitQueue.destroy();

    fallbackQueue.destroy();
    timeoutQueue.destroy();
    cancelQueue.destroy();
    console.log(JSON.stringify({ok:true}));
})().catch(error => { console.error(error); process.exit(1); });
"""
        self.assertEqual(run_node(script), {"ok": True})

    def test_both_canvas_pages_load_runtime_before_canvas_code(self):
        runtime_src = "/static/js/canvas-media-queue.js?v=2026.09.01.media-queue-runtime.1"
        self.assertIn(runtime_src, CANVAS_HTML)
        self.assertIn(runtime_src, SMART_HTML)
        self.assertLess(CANVAS_HTML.index(runtime_src), CANVAS_HTML.index("/static/js/canvas.js"))
        self.assertLess(SMART_HTML.index(runtime_src), SMART_HTML.index("/static/js/smart-canvas.js"))

    def test_host_callback_failures_do_not_break_queue_or_leak_slots(self):
        script = r"""
const assert = require('assert');
const {createMediaQueue} = require('./static/js/canvas-media-queue.js');

class FakeImage {
    constructor(kind='image') {
        this.dataset = {previewSrc:'/api/media-preview?id=callback', previewState:'queued'};
        if(kind === 'video') this.dataset.previewKind = 'video';
        this.isConnected = true;
        this.listeners = new Map();
        this.attrs = new Map();
    }
    addEventListener(name, listener) {
        if(!this.listeners.has(name)) this.listeners.set(name, new Set());
        this.listeners.get(name).add(listener);
    }
    removeEventListener(name, listener) { this.listeners.get(name)?.delete(listener); }
    emit(name) { [...(this.listeners.get(name) || [])].forEach(listener => listener({type:name, target:this})); }
    set src(value) { this.attrs.set('src', value); }
    getAttribute(name) { return this.attrs.get(name) || null; }
    removeAttribute(name) { this.attrs.delete(name); }
}

const throws = label => () => { throw new Error(label); };

const startAndRecord = new FakeImage();
const callbackQueue = createMediaQueue({
    collectCandidates:throws('collectCandidates'),
    isEligible:throws('isEligible'),
    fallbackSource:throws('fallbackSource'),
    onStart:throws('onStart'),
    onRecord:throws('onRecord'),
    imageTimeoutMs:1000,
});
assert.doesNotThrow(() => callbackQueue.drainNow());
assert.equal(callbackQueue.start(startAndRecord), true);
assert.doesNotThrow(() => startAndRecord.emit('error'));
assert.equal(callbackQueue.snapshot().activeTotal, 0);
assert.equal(startAndRecord.dataset.previewState, 'failed');

const video = new FakeImage('video');
const videoQueue = createMediaQueue({
    collectCandidates:() => [],
    isEligible:() => true,
    replaceVideoFallback:throws('replaceVideoFallback'),
    videoTimeoutMs:1000,
});
assert.equal(videoQueue.start(video), true);
assert.doesNotThrow(() => video.emit('error'));
assert.equal(videoQueue.snapshot().activeTotal, 0);
assert.equal(video.dataset.previewState, 'failed');

callbackQueue.destroy();
videoQueue.destroy();
console.log(JSON.stringify({ok:true}));
"""
        self.assertEqual(run_node(script), {"ok": True})

    def test_classic_and_smart_canvases_use_shared_queue_controller(self):
        for source, name in ((CANVAS_JS, "classic"), (SMART_JS, "smart")):
            self.assertIn("window.CanvasMediaQueue.createMediaQueue", source, name)
            self.assertIn("cancelIneligible()", source, name)
            self.assertIn("maxVideoActive", source, name)
            self.assertNotIn("MediaQueueActive += 1", source, name)
        self.assertIn("onStart:() => recordClassicFirstPreviewStart()", CANVAS_JS)


if __name__ == "__main__":
    unittest.main()
