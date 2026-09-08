(function(){
    'use strict';
    function setup(key, id, defaultValue){
        const storageKey = `${key}_px_v1`;
        const slider = document.getElementById(`${id}`);
        const output = document.getElementById(`${id}Value`);
        const preview = document.getElementById(`${id}Preview`);
        const status = document.getElementById(`${id}Status`);
        const reset = document.getElementById(`${id}Reset`);
        let current = defaultValue;
        let revision = 0;
        let loading = false;
        let saving = false;
        let editing = false;
        let pending = null;

        function normalize(value){
            const number = Number(value);
            return Number.isFinite(number) && number >= 0 && number <= 240 && Number.isInteger(number) ? number : defaultValue;
        }

        function readLocal(){
            try {
                const value = localStorage.getItem(storageKey);
                if(value !== null) current = normalize(value);
            } catch(e) {}
        }

        function apply(value){
            current = normalize(value);
            revision++;
            try { localStorage.setItem(storageKey, String(current)); } catch(e) {}
        }

        function render(value=current){
            if(!slider) return;
            value = normalize(value);
            slider.value = String(value);
            output.textContent = `${value} px`;
            slider.setAttribute('aria-valuetext', `${value} px 节点间距`);
            preview.style.columnGap = `${value * .2}px`;
            preview.style.rowGap = `${value * .2}px`;
        }

        function showStatus(message, error=false){
            if(!status) return;
            status.textContent = message;
            status.classList.toggle('error', error);
        }

        async function request(options){
            const response = await fetch('/api/app-settings', options);
            const data = await response.json();
            if(!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '请求失败，请重试');
            return data;
        }

        async function refresh(){
            if(loading || saving || editing) return;
            loading = true;
            const startedAt = revision;
            try {
                const data = await request({cache:'no-store'});
                if(startedAt !== revision || saving || editing) return;
                apply(data[key] ?? defaultValue);
                render();
                if(slider) slider.disabled = false;
                if(reset) reset.disabled = false;
                showStatus('');
            } catch(error) {
                showStatus(`加载失败：${error.message}，请重新打开设置`, true);
            } finally { loading = false; }
        }

        async function save(value){
            pending = normalize(value);
            revision++;
            if(saving) return;
            saving = true;
            while(pending !== null){
                const target = pending;
                pending = null;
                showStatus('正在保存…');
                try {
                    const data = await request({
                        method:'PUT',
                        headers:{'Content-Type':'application/json'},
                        body:JSON.stringify({[key]:target}),
                    });
                    apply(data[key] ?? target);
                    if(pending === null && !editing){ render(); showStatus('已保存'); }
                } catch(error) {
                    if(pending === null){
                        if(!editing) render();
                        showStatus(`保存失败：${error.message}，请重试`, true);
                    }
                }
            }
            saving = false;
        }

        slider?.addEventListener('input', () => {
            editing = true;
            revision++;
            render(slider.value);
            showStatus('松开后自动保存');
        });
        slider?.addEventListener('change', () => { editing = false; save(slider.value); });
        reset?.addEventListener('click', () => { editing = false; render(defaultValue); save(defaultValue); });
        window.addEventListener('storage', event => {
            if(event.key !== storageKey) return;
            revision++;
            readLocal();
            if(!saving && !editing) render();
        });
        window.addEventListener('focus', refresh);
        document.addEventListener('visibilitychange', () => { if(!document.hidden) refresh(); });
        readLocal();
        render();
        refresh();
        return () => { readLocal(); return current; };
    }
    window.CanvasArrangeSpacing = {
        gap:setup('canvas_arrange_spacing', 'arrangeSpacing', 56),
        groupGap:setup('canvas_group_arrange_spacing', 'groupArrangeSpacing', 28),
    };
})();
