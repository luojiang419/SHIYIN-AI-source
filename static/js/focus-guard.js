(function(){
    if(window.StudioFocusGuard) return;

    const EDITABLE_SELECTOR = 'input, textarea, select, option, [contenteditable=""], [contenteditable="true"], [contenteditable="plaintext-only"]';
    const TEXT_INPUT_TYPES = new Set(['text','search','url','tel','email','password','number']);
    const state = {
        composing:false,
        composingElement:null,
        lastCompositionAt:0,
        deferred:new Map(),
        flushing:false,
    };

    function cssEscape(value){
        if(window.CSS?.escape) return CSS.escape(String(value));
        return String(value).replace(/["\\]/g, '\\$&');
    }

    function editableElement(target){
        const el = target?.closest?.(EDITABLE_SELECTOR);
        if(!el) return null;
        if(el.matches?.('option')) return el.closest('select');
        return el;
    }

    function isTextEditable(target){
        const el = editableElement(target);
        if(!el) return false;
        const tag = String(el.tagName || '').toUpperCase();
        if(tag === 'TEXTAREA' || el.isContentEditable) return true;
        if(tag !== 'INPUT') return false;
        return TEXT_INPUT_TYPES.has(String(el.type || 'text').toLowerCase());
    }

    function isEditable(target){
        return !!editableElement(target);
    }

    function selectorFor(el){
        if(!el || el.nodeType !== 1) return '';
        if(el.id) return `#${cssEscape(el.id)}`;
        const tag = String(el.tagName || '').toLowerCase();
        const attrs = [];
        ['name','data-option','data-reference-field','data-reference-key','data-rh-param','data-comfy-param','data-field','data-template-edit-text'].forEach(name => {
            const value = el.getAttribute?.(name);
            if(value != null && value !== '') attrs.push(`[${name}="${cssEscape(value)}"]`);
        });
        if(attrs.length) return `${tag}${attrs.join('')}`;
        const parentId = el.closest?.('[data-id]')?.getAttribute?.('data-id') || '';
        if(parentId && el.classList?.length) {
            return `[data-id="${cssEscape(parentId)}"] ${tag}.${[...el.classList].map(cssEscape).join('.')}`;
        }
        if(el.classList?.length) return `${tag}.${[...el.classList].map(cssEscape).join('.')}`;
        return '';
    }

    function capture(target=document.activeElement){
        const el = editableElement(target);
        if(!el) return null;
        const selectionStart = typeof el.selectionStart === 'number' ? el.selectionStart : null;
        const selectionEnd = typeof el.selectionEnd === 'number' ? el.selectionEnd : null;
        return {
            element:el,
            selector:selectorFor(el),
            selectionStart,
            selectionEnd,
            value:typeof el.value === 'string' ? el.value : '',
            requestedAt:Date.now(),
        };
    }

    function querySnapshot(snapshot){
        if(!snapshot) return null;
        if(snapshot.element?.isConnected) return snapshot.element;
        if(!snapshot.selector) return null;
        try {
            const candidates = [...document.querySelectorAll(snapshot.selector)];
            if(!candidates.length) return null;
            return candidates.find(el => typeof el.value !== 'string' || el.value === snapshot.value) || candidates[0];
        } catch(e) {
            return null;
        }
    }

    function restore(snapshot){
        const target = querySnapshot(snapshot);
        if(!target) return false;
        const active = document.activeElement;
        if(active && active !== document.body && active !== document.documentElement && active !== target && isEditable(active)) return false;
        try { target.focus({preventScroll:true}); } catch(e) { try { target.focus(); } catch(_) {} }
        if(typeof target.setSelectionRange === 'function') {
            const end = Number(target.value?.length || 0);
            const start = Number.isFinite(snapshot.selectionStart) ? Math.min(snapshot.selectionStart, end) : end;
            const finish = Number.isFinite(snapshot.selectionEnd) ? Math.min(snapshot.selectionEnd, end) : start;
            try { target.setSelectionRange(start, finish); } catch(e) {}
        }
        return document.activeElement === target;
    }

    function shouldDeferDomUpdate(root=document){
        if(!state.composing) return false;
        const active = editableElement(document.activeElement);
        if(!active || !isTextEditable(active)) return false;
        if(!root || root === document) return true;
        return root.contains?.(active) || active.contains?.(root);
    }

    function flushDeferred(){
        if(state.flushing) return;
        state.flushing = true;
        setTimeout(() => {
            state.flushing = false;
            const callbacks = [...state.deferred.values()];
            state.deferred.clear();
            callbacks.forEach(callback => {
                try { callback(); } catch(error) { console.error('[focus-guard] deferred update failed', error); }
            });
        }, 0);
    }

    function deferDomUpdate(key, callback){
        if(!key || typeof callback !== 'function') return;
        state.deferred.set(String(key), callback);
    }

    document.addEventListener('compositionstart', event => {
        const target = editableElement(event.target);
        if(!target || !isTextEditable(target)) return;
        state.composing = true;
        state.composingElement = target;
        state.lastCompositionAt = Date.now();
    }, true);

    document.addEventListener('compositionend', () => {
        state.composing = false;
        state.composingElement = null;
        state.lastCompositionAt = Date.now();
        flushDeferred();
    }, true);

    const originalBlur = HTMLElement.prototype.blur;
    HTMLElement.prototype.blur = function guardedBlur(){
        if(state.composing && isTextEditable(this)) return;
        return originalBlur.call(this);
    };

    window.StudioFocusGuard = {
        state,
        isEditable,
        isTextEditable,
        isComposing:() => state.composing,
        capture,
        restore,
        shouldDeferDomUpdate,
        deferDomUpdate,
        flushDeferred,
    };
})();
