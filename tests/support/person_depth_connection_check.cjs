const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/canvas-special-nodes.js', 'utf8');
function extract(name) {
    const start = source.search(new RegExp(`    (?:async )?function ${name}\\(`));
    assert.ok(start >= 0, name);
    const end = source.indexOf('\n    ', source.indexOf('\n    }', start) + 6);
    return source.slice(start, end < 0 ? undefined : end);
}
const context = vm.createContext({assert, TypeError, Date, fetch: null});
vm.runInContext(`
let personDepthStatus = {state:'downloading', progress:0.38, downloaded_bytes:38, total_bytes:100, install_available:true};
let personDepthUpdatedAt = 0, personDepthPollTimer = 0, personDepthStatusPromise = null, personDepthInstallPromise = null;
let personDepthAutoInstallAttempted = false;
let personDepthBindings = new Map([['node', {}]]);
const PERSON_DEPTH_ACTIVE_STATES = new Set(['checking','downloading','verifying','installing','smoke']);
let delay = 0, notifications = 0;
function clearTimeout() { delay = 0; }
function setTimeout(callback, ms) { delay = ms; return 1; }
function notifyPersonDepthBindings() { notifications++; }
function responseError() { return 'HTTP error'; }
function esc(value) { return String(value); }
function formatBytes(value) { return String(value); }
${['poseReplicateComponentHtml','schedulePersonDepthPoll','markPersonDepthConnectionError','refreshPersonDepthStatus','installPersonDepthComponent','maybeAutoInstallPersonDepth'].map(extract).join('\n')}
`, context);
async function run(code) { return vm.runInContext(`(async () => {${code}})()`, context); }
(async () => {
    await run(`
        fetch = async () => { throw new TypeError('Failed to fetch'); };
        await refreshPersonDepthStatus(true);
        assert.equal(personDepthStatus.state, 'connection_error');
        assert.equal(personDepthStatus.progress, 0.38);
        assert.equal(personDepthStatus.downloaded_bytes, 38);
        assert.equal(delay, 5000);
        assert.match(poseReplicateComponentHtml(personDepthStatus), /reconnect-person-depth/);
        assert.doesNotMatch(poseReplicateComponentHtml(personDepthStatus), /安装失败|Failed to fetch/);
        fetch = async () => ({ok:true,json:async () => ({state:'downloading',progress:0.5,install_available:true})});
        await refreshPersonDepthStatus(true);
        assert.equal(personDepthStatus.progress, 0.5);
        assert.equal(delay, 1500);
        personDepthAutoInstallAttempted = true;
        let posts = 0;
        fetch = async (url, options) => {
            if(options.method === 'POST') { posts++; throw new TypeError('Failed to fetch'); }
            return {ok:true,json:async () => ({state:'ready',ready:true})};
        };
        await installPersonDepthComponent().catch(() => {});
        assert.equal(personDepthStatus.state, 'connection_error');
        await refreshPersonDepthStatus(true);
        assert.equal(posts, 1);
        assert.equal(personDepthStatus.ready, true);
        assert.equal(delay, 0);
        fetch = async () => ({ok:true,json:async () => ({state:'failed',ready:false,install_available:true,message:'安装失败'})});
        personDepthAutoInstallAttempted = false;
        await refreshPersonDepthStatus(true);
        assert.equal(personDepthStatus.state, 'failed');
        assert.equal(delay, 0);
        assert.equal(personDepthAutoInstallAttempted, false);
        assert.match(poseReplicateComponentHtml(personDepthStatus), /retry-person-depth/);
    `);
    console.log('PASS: disconnect, progress preservation, reconnect, lost POST response, ready recovery, install failure');
})().catch(error => { console.error(error); process.exitCode = 1; });
