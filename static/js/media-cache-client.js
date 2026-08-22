(function installShiyinMediaCache(){
    'use strict';
    const CACHE_VERSION = '2026.08.22.generated-image-cache.1';
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
    });
})();
