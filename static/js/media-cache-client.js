(function installShiyinMediaCache(){
    'use strict';
    const CACHE_VERSION = (() => {
        try {
            return new URL(document.currentScript?.src || location.href, location.href).searchParams.get('v')
                || '2026.08.30.static-assets-cache.1';
        } catch (error) {
            return '2026.08.30.static-assets-cache.1';
        }
    })();
    const workerUrl = `/media-cache-sw.js?v=${CACHE_VERSION}`;
    let registrationPromise = null;

    function register(){
        if(registrationPromise) return registrationPromise;
        if(!('serviceWorker' in navigator) || location.protocol === 'file:') return Promise.resolve(null);
        registrationPromise = navigator.serviceWorker.register(workerUrl, {scope:'/'}).catch(() => null);
        return registrationPromise;
    }

    window.ShiyinMediaCache = Object.freeze({
        version: CACHE_VERSION,
        ready: register(),
        clear(){
            return register().then(registration => {
                const worker = navigator.serviceWorker.controller || registration?.active || registration?.waiting;
                worker?.postMessage({type:'clear-generated-image-cache'});
            }).catch(() => {});
        },
        invalidate(urls){
            const values = (Array.isArray(urls) ? urls : [urls]).filter(url => typeof url === 'string' && url);
            if(!values.length) return Promise.resolve();
            return register().then(registration => {
                const worker = navigator.serviceWorker.controller || registration?.active || registration?.waiting;
                worker?.postMessage({type:'invalidate-generated-image-cache', urls:values});
            }).catch(() => {});
        },
    });
})();
