// 启动层独立于编辑器脚本，覆盖脚本下载和工程准备期间。
(() => {
    const style = document.createElement('style');
    style.textContent = `
    .canvas-entry-progress{position:absolute;inset:0;z-index:11000;display:grid;place-items:center;background:var(--page,var(--bg,#1a1a1a));color:var(--text,#eee)}
    .canvas-entry-progress[hidden]{display:none}
    .canvas-entry-card{width:min(320px,80vw);text-align:center;font:14px/1.6 system-ui,sans-serif}
    .canvas-entry-track{height:5px;margin:22px 0 12px;border-radius:8px;background:color-mix(in srgb,currentColor 12%,transparent);overflow:hidden}
    .canvas-entry-fill{height:100%;width:4%;border-radius:inherit;background:#c9b38d;box-shadow:0 0 12px #c9b38d80;position:relative;transition:width .3s ease;animation:canvas-entry-breathe 2s ease-in-out infinite}
    .canvas-entry-fill:after{content:'';position:absolute;inset:0;background:linear-gradient(90deg,transparent,#fff9,transparent);transform:translateX(-100%);animation:canvas-entry-shimmer 2.3s ease-in-out infinite}
    .canvas-entry-detail{font-size:12px;opacity:.65;min-height:20px}
    .canvas-entry-card button{margin:12px 6px 0;padding:7px 16px;border:1px solid currentColor;border-radius:8px;background:transparent;color:inherit;cursor:pointer}
    @keyframes canvas-entry-breathe{50%{opacity:.55;box-shadow:0 0 18px #c9b38da0}}
    @keyframes canvas-entry-shimmer{to{transform:translateX(100%)}}
    @media(prefers-reduced-motion:reduce){.canvas-entry-fill,.canvas-entry-fill:after{animation:none;transition:none}}
    `;
    document.head.appendChild(style);
    function create(parent=document.body){
        const el = document.createElement('div');
        el.className = 'canvas-entry-progress';
        el.innerHTML = '<div class="canvas-entry-card"><div role="status" data-entry-message>正在进入画布中...</div><div class="canvas-entry-track" role="progressbar" aria-label="画布加载进度" aria-valuemin="0" aria-valuemax="100"><div class="canvas-entry-fill"></div></div><div class="canvas-entry-detail"></div><div data-entry-actions></div></div>';
        parent.appendChild(el);
        let value = 0;
        return {
            el,
            update(progress, detail=''){
                value = Math.max(value, Math.min(100, progress));
                el.querySelector('.canvas-entry-fill').style.width = `${value}%`;
                el.querySelector('[role=progressbar]').setAttribute('aria-valuenow', String(Math.round(value)));
                el.querySelector('.canvas-entry-detail').textContent = detail;
            },
            error(message, retry, proceed, proceedLabel='继续进入'){
                el.querySelector('[data-entry-message]').textContent = message;
                const actions = el.querySelector('[data-entry-actions]');
                actions.replaceChildren();
                for(const [label, action] of [['重试',retry],[proceedLabel,proceed]]){
                    if(!action) continue;
                    const button = document.createElement('button');
                    button.textContent = label; button.onclick = action; actions.appendChild(button);
                }
            },
            remove(){el.remove();}
        };
    }
    window.CanvasEntryProgress = {create};
})();
