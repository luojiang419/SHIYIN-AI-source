const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../static/media-cache-sw.js'), 'utf8');
const never = () => new Promise(() => {});

function fixture(fault, scope = 'account-a') {
    const calls = {open:0, network:0, auth:0};
    const tasks = [];
    const cache = {
        match: fault === 'match' ? never : async () => undefined,
        put: fault === 'put' ? never : async () => { if (fault === 'quota') throw Error('quota'); },
        keys: async () => [],
    };
    const context = {
        URL, Request, Response, Headers, Map, Date, console, setTimeout, clearTimeout,
        self:{location:{origin:'http://fixture'}, addEventListener(){}},
        caches:{open:async () => {
            calls.open++;
            if (fault === 'open') return never();
            if (fault === 'unavailable') throw Error('storage unavailable');
            return cache;
        }},
        fetch:async request => {
            if (request === '/api/auth/status') { calls.auth++; return new Response('', {headers:{'X-Media-Account':scope}}); }
            calls.network++;
            return new Response('pixels', {headers:{'X-Media-Account':scope, 'Content-Type':'image/png', 'Content-Length':'6'}});
        },
    };
    vm.createContext(context);
    vm.runInContext(source, context);
    return {context, calls, tasks, setScope(value){scope=value;}, event:{waitUntil(promise){tasks.push(promise);}}};
}

for (const handler of ['handleStaticAssetRequest', 'handleImageRequest']) {
    for (const fault of ['open', 'match', 'put', 'quota', 'unavailable']) {
        test(`${handler}: ${fault} cannot hold the response`, {timeout:2000}, async () => {
            const f = fixture(fault);
            const started = Date.now();
            const response = await f.context[handler](new Request('http://fixture/api/media-preview?rev=1'), f.event);
            assert.equal(await response.text(), 'pixels');
            assert.ok(Date.now() - started < 1000, 'cache blocked the local network response');
            assert.equal(f.calls.network, 1);
            if (['open','match','unavailable'].includes(fault)) {
                await f.context[handler](new Request('http://fixture/api/media-preview?rev=2'), f.event);
                assert.equal(f.calls.open, 1, 'subsequent images retried a known stalled cache');
            }
            if (fault !== 'put') await Promise.all(f.tasks);
        });
    }
}

test('account changes during cache timeout cannot return the prior account response', {timeout:2000}, async () => {
    const f = fixture('match');
    const pending = f.context.handleImageRequest(new Request('http://fixture/api/media-preview?rev=1'), f.event);
    await new Promise(resolve => setTimeout(resolve, 30));
    f.setScope('account-b');
    vm.runInContext('authEpoch++', f.context);
    const response = await pending;
    assert.equal(await response.text(), 'pixels');
    assert.equal(f.calls.network, 1);
    assert.equal(f.calls.auth, 2);
    assert.equal(response.headers.get('X-Media-Account'), 'account-b');
    await Promise.all(f.tasks);
});
