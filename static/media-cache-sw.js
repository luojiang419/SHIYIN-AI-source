'use strict';
// 媒体缓存独立于应用版本；会话分区 + 实际源版本共同确定身份。
const CACHE_NAME = 'shiyin-media-session-v3';
const STATIC_CACHE_PREFIX = 'shiyin-static-assets-';
const STATIC_CACHE_NAME = `${STATIC_CACHE_PREFIX}v3`;
const MAX_ENTRIES = 1000;
const MAX_BYTES = 256 * 1024 * 1024;
const MAX_ITEM_BYTES = 16 * 1024 * 1024;
const inflight = new Map();
let authPending = null;
let authEpoch = 0;
let accountMutation = null;
let trimPending = null;
let lastTrim = 0;

function isCacheableRequest(request) {
    const url = new URL(request.url);
    return request.method === 'GET' && url.origin === self.location.origin
        && (!request.destination || request.destination === 'image')
        && (['/api/media-preview', '/api/image-jpeg', '/api/download-output'].includes(url.pathname)
            || url.pathname.startsWith('/assets/') || url.pathname.startsWith('/output/'));
}
function hasContentRevision(url) {
    return ['rev', 'v', 'hash', 'version'].some(key => Boolean(url.searchParams.get(key)));
}
function isVersionedStaticAssetRequest(request) {
    const url = new URL(request.url);
    return request.method === 'GET' && url.origin === self.location.origin
        && url.pathname.startsWith('/static/') && !url.pathname.startsWith('/static/assets/')
        && ['script', 'style', 'font', 'image'].includes(request.destination) && hasContentRevision(url);
}
async function handleStaticAssetRequest(request) {
    const cache = await caches.open(STATIC_CACHE_NAME);
    const cached = await cache.match(request);
    if (cached) return cached;
    const response = await fetch(request);
    if (response.ok) await cache.put(request, response.clone());
    return response;
}
async function authenticatedScope() {
    // 只合并正在执行的鉴权，不缓存鉴权结果；登出/过期立即停止缓存读取。
    if (accountMutation) await accountMutation.catch(() => {});
    const epoch = authEpoch;
    if (!authPending) {
        const pending = fetch('/api/auth/status', {cache:'no-store', credentials:'same-origin'})
            .then(response => response.ok ? response.headers.get('X-Media-Account') || '' : '')
            .catch(() => '').finally(() => { if (authPending === pending) authPending = null; });
        authPending = pending;
    }
    const scope = await authPending;
    return epoch === authEpoch ? scope : authenticatedScope();
}
function handleAccountMutation(request) {
    ++authEpoch;
    authPending = null;
    const pending = fetch(request).finally(() => {
        ++authEpoch;
        authPending = null;
        if (accountMutation === pending) accountMutation = null;
    });
    accountMutation = pending;
    return pending;
}
function scopedKey(request, scope) {
    const url = new URL(request.url);
    url.searchParams.set('__media_session', scope);
    return new Request(url.href);
}
async function trimCache(cache) {
    let total = 0;
    const entries = [];
    for (const key of await cache.keys()) {
        const response = await cache.match(key);
        const bytes = Number(response?.headers.get('X-Cache-Bytes') || 0);
        total += bytes;
        entries.push({key, bytes});
    }
    while (entries.length > MAX_ENTRIES || total > MAX_BYTES) {
        const oldest = entries.shift();
        await cache.delete(oldest.key);
        total -= oldest.bytes;
    }
}
function scheduleTrimCache(cache, event) {
    if (trimPending || Date.now() - lastTrim < 10000) return;
    lastTrim = Date.now();
    trimPending = trimCache(cache).catch(() => {}).finally(() => { trimPending = null; });
    event.waitUntil(trimPending);
}
async function cacheResponse(cache, key, response, scope) {
    if (!response.ok || response.status === 206 || response.headers.get('X-Media-Account') !== scope
        || !String(response.headers.get('content-type') || '').startsWith('image/')) return;
    const declared = Number(response.headers.get('content-length') || 0);
    // 未知大小的上游响应不读入内存；有界本地预览才进入持久缓存。
    if (!declared || declared > MAX_ITEM_BYTES) return;
    const body = await response.clone().blob();
    if (body.size > MAX_ITEM_BYTES) return;
    const headers = new Headers(response.headers);
    headers.delete('Vary'); // key 已包含已认证会话，不依赖 JS 无法读取的 Cookie。
    headers.set('X-Cache-Bytes', String(body.size));
    headers.set('X-Cache-Time', String(Date.now()));
    await cache.put(key, new Response(body, {status:response.status, headers}));
}
async function handleImageRequest(request, event) {
    const scope = await authenticatedScope();
    const epoch = authEpoch;
    if (!scope) return fetch(new Request(request, {cache:'no-store'}));
    const cache = await caches.open(CACHE_NAME);
    const key = scopedKey(request, scope);
    const cached = await cache.match(key);
    if (epoch !== authEpoch) return handleImageRequest(request, event);
    const url = new URL(request.url);
    const age = Date.now() - Number(cached?.headers.get('X-Cache-Time') || 0);
    if (cached && (hasContentRevision(url) || age < 30000)) return cached;
    let pending = inflight.get(key.url);
    if (!pending) {
        pending = fetch(new Request(request, {cache:'no-cache'})).then(response => {
            // 鉴权和媒体请求之间若发生账号切换，不返回另一账号的数据。
            if (epoch !== authEpoch || (response.ok && response.headers.get('X-Media-Account') !== scope)) return Response.error();
            event.waitUntil(cacheResponse(cache, key, response, scope).catch(() => {}));
            return response;
        }).finally(() => inflight.delete(key.url));
        inflight.set(key.url, pending);
    }
    scheduleTrimCache(cache, event);
    return (await pending).clone();
}
self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil((async () => {
    const keys = await caches.keys();
    // 旧缓存没有账号边界，禁止复用。
    await Promise.all(keys.filter(key => key !== CACHE_NAME && key !== STATIC_CACHE_NAME
        && (key.startsWith('shiyin-generated-image') || key.startsWith('shiyin-media-') || key.startsWith(STATIC_CACHE_PREFIX)))
        .map(key => caches.delete(key)));
    if (self.indexedDB) self.indexedDB.deleteDatabase('shiyin-generated-image-cache');
    await self.clients.claim();
})()));
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);
    if (url.origin === self.location.origin && event.request.method === 'POST'
        && ['/api/account/login','/api/account/logout','/api/account/register'].includes(url.pathname)) event.respondWith(handleAccountMutation(event.request));
    else if (isVersionedStaticAssetRequest(event.request)) event.respondWith(handleStaticAssetRequest(event.request));
    else if (isCacheableRequest(event.request)) event.respondWith(handleImageRequest(event.request, event));
});
self.addEventListener('message', event => {
    if (event.data?.type === 'activate-media-cache-worker') event.waitUntil(self.skipWaiting());
    if (event.data?.type === 'clear-generated-image-cache') event.waitUntil(caches.delete(CACHE_NAME));
    if (event.data?.type === 'invalidate-generated-image-cache') event.waitUntil((async () => {
        const urls = (event.data.urls || []).map(url => new URL(url, self.location.origin).href);
        const cache = await caches.open(CACHE_NAME);
        for (const key of await cache.keys()) {
            const url = new URL(key.url);
            url.searchParams.delete('__media_session');
            const original = url.searchParams.get('url');
            if (urls.includes(url.href) || (original && urls.includes(new URL(original, self.location.origin).href))) await cache.delete(key);
        }
    })());
});
