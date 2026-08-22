/* SHIYIN-AI generated-image cache service worker. */
const CACHE_NAME = 'shiyin-generated-images-v1';
const CACHE_PREFIX = 'shiyin-generated-images-';
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

self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME).map(key => caches.delete(key)));
    await self.clients.claim();
})()));

self.addEventListener('fetch', event => {
    if (isCacheableRequest(event.request)) event.respondWith(handleImageRequest(event.request));
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
});
