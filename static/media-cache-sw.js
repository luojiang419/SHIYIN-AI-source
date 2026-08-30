/* SHIYIN-AI generated-image cache service worker. */
const CACHE_PREFIX = 'shiyin-generated-images-';
const STATIC_CACHE_PREFIX = 'shiyin-static-assets-';
const WORKER_VERSION = (() => {
    try { return new URL(self.location.href).searchParams.get('v') || 'v2'; }
    catch (error) { return 'v2'; }
})();
const CACHE_NAME = `${CACHE_PREFIX}${WORKER_VERSION}`;
const STATIC_CACHE_NAME = `${STATIC_CACHE_PREFIX}${WORKER_VERSION}`;
const MAX_ENTRIES = 500;
const MAX_BYTES = 512 * 1024 * 1024;
const DB_NAME = 'shiyin-generated-image-cache';
const DB_STORE = 'entries';

function isSameOrigin(request) {
    try { return new URL(request.url).origin === self.location.origin; } catch (error) { return false; }
}

function isCacheablePath(url) {
    const path = url.pathname;
    if (path === '/api/media-preview' || path === '/api/image-jpeg' || path === '/api/download-output') return true;
    return path.startsWith('/output/') || path.startsWith('/assets/output/') || path.startsWith('/assets/generated/');
}

function isCacheableRequest(request) {
    if (request.method !== 'GET' || !isSameOrigin(request)) return false;
    if (request.destination && request.destination !== 'image') return false;
    try { return isCacheablePath(new URL(request.url)); } catch (error) { return false; }
}

function isVersionedStaticAssetRequest(request) {
    if (request.method !== 'GET' || !isSameOrigin(request)) return false;
    if (!['script', 'style', 'font', 'image'].includes(request.destination)) return false;
    try {
        const url = new URL(request.url);
        if (!url.pathname.startsWith('/static/') || url.pathname === '/media-cache-sw.js') return false;
        return hasContentRevision(url);
    } catch (error) {
        return false;
    }
}

async function handleStaticAssetRequest(request) {
    const cache = await caches.open(STATIC_CACHE_NAME);
    const cached = await cache.match(request);
    if (cached) return cached;
    try {
        const response = await fetch(request);
        if (response.ok) await cache.put(request, response.clone());
        return response;
    } catch (error) {
        return cached || Response.error();
    }
}

function hasContentRevision(url) {
    return ['rev', 'v', 'hash', 'version'].some(key => Boolean(url.searchParams.get(key)));
}

function needsFreshNetwork(request) {
    try {
        const url = new URL(request.url);
        // 预览接口和未携带内容修订号的媒体都可能复用同一 URL，刷新时必须优先取服务端最新结果。
        return url.pathname.startsWith('/api/') || !hasContentRevision(url);
    } catch (error) {
        return true;
    }
}

function openMetaDb() {
    return new Promise((resolve, reject) => {
        if (!self.indexedDB) { resolve(null); return; }
        const request = indexedDB.open(DB_NAME, 1);
        request.onupgradeneeded = () => request.result.createObjectStore(DB_STORE, {keyPath: 'url'});
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => resolve(null);
    });
}

async function readMeta() {
    const db = await openMetaDb();
    if (!db) return [];
    return new Promise(resolve => {
        const tx = db.transaction(DB_STORE, 'readonly');
        const request = tx.objectStore(DB_STORE).getAll();
        request.onsuccess = () => resolve(request.result || []);
        request.onerror = () => resolve([]);
    });
}

async function writeMeta(entry) {
    const db = await openMetaDb();
    if (!db) return;
    try {
        const tx = db.transaction(DB_STORE, 'readwrite');
        tx.objectStore(DB_STORE).put(entry);
    } catch (error) {}
}

async function deleteMeta(url) {
    const db = await openMetaDb();
    if (!db) return;
    try {
        const tx = db.transaction(DB_STORE, 'readwrite');
        tx.objectStore(DB_STORE).delete(url);
    } catch (error) {}
}

async function trimCache(cache) {
    const entries = await readMeta();
    if (!entries.length) return;
    let totalBytes = entries.reduce((sum, item) => sum + Number(item.bytes || 0), 0);
    const ordered = [...entries].sort((a, b) => Number(a.touchedAt || 0) - Number(b.touchedAt || 0));
    while (ordered.length > MAX_ENTRIES || totalBytes > MAX_BYTES) {
        const oldest = ordered.shift();
        if (!oldest) break;
        await cache.delete(oldest.url);
        await deleteMeta(oldest.url);
        totalBytes -= Number(oldest.bytes || 0);
    }
}

async function cacheResponse(request, response) {
    if (!response || !response.ok || !String(response.headers.get('content-type') || '').toLowerCase().startsWith('image/')) return;
    const cache = await caches.open(CACHE_NAME);
    await cache.put(request, response.clone());
    await writeMeta({
        url: request.url,
        bytes: Number(response.headers.get('content-length') || 0),
        touchedAt: Date.now(),
    });
    // 不在每次命中时遍历 CacheStorage，只在写入后做有界清理。
    await trimCache(cache);
}

async function handleImageRequest(request) {
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(request);
    if (cached) {
        const meta = await readMeta();
        const entry = meta.find(item => item.url === request.url);
        if (entry) await writeMeta({...entry, touchedAt: Date.now()});
        return cached;
    }
    try {
        const response = await fetch(request);
        await cacheResponse(request, response);
        return response;
    } catch (error) {
        return Response.error();
    }
}

async function networkFirstImageRequest(request) {
    try {
        // 绕过浏览器 HTTP 缓存，避免同 URL 的新生成结果被旧响应遮蔽。
        const response = await fetch(new Request(request, {cache: 'no-store'}));
        await cacheResponse(request, response);
        return response;
    } catch (error) {
        const cache = await caches.open(CACHE_NAME);
        const cached = await cache.match(request);
        return cached || Response.error();
    }
}

function isMediaPreviewRequest(request) {
    try { return new URL(request.url).pathname === '/api/media-preview'; }
    catch (error) { return false; }
}

async function staleWhileRevalidateMediaPreview(request, event) {
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(request);
    const refresh = fetch(new Request(request, {cache: 'no-store'}))
        .then(response => cacheResponse(request, response).then(() => response));
    if (cached) {
        // 首屏直接复用已有缩略图；刷新请求由 fetch event 托管，下一次进入即可得到最新结果。
        event.waitUntil(refresh.catch(() => {}));
        return cached;
    }
    try { return await refresh; }
    catch (error) { return Response.error(); }
}

self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME).map(key => caches.delete(key)));
    await Promise.all(keys.filter(key => key.startsWith(STATIC_CACHE_PREFIX) && key !== STATIC_CACHE_NAME).map(key => caches.delete(key)));
    await self.clients.claim();
})()));

self.addEventListener('fetch', event => {
    if (isVersionedStaticAssetRequest(event.request)) {
        event.respondWith(handleStaticAssetRequest(event.request));
        return;
    }
    if (isCacheableRequest(event.request)) {
        if (isMediaPreviewRequest(event.request)) {
            event.respondWith(staleWhileRevalidateMediaPreview(event.request, event));
        } else {
            event.respondWith(needsFreshNetwork(event.request)
                ? networkFirstImageRequest(event.request)
                : handleImageRequest(event.request));
        }
    }
});

self.addEventListener('message', event => {
    if (event.data?.type === 'clear-generated-image-cache') {
        event.waitUntil((async () => {
            await caches.delete(CACHE_NAME);
            const db = await openMetaDb();
            try { db?.close(); } catch (error) {}
            if (self.indexedDB) indexedDB.deleteDatabase(DB_NAME);
        })());
    }
    if (event.data?.type === 'invalidate-generated-image-cache') {
        event.waitUntil((async () => {
            const cache = await caches.open(CACHE_NAME);
            const urls = Array.isArray(event.data.urls) ? event.data.urls : [];
            await Promise.all(urls.map(async url => {
                if (typeof url !== 'string' || !url) return;
                await cache.delete(url);
                await deleteMeta(url);
            }));
        })());
    }
});
