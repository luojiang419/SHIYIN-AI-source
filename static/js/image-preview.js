(function(){
    'use strict';

    /* 一次性注入预览框样式 —— 所有页面共用同一套外观 */
    function injectStyles(){
        if(document.getElementById('studio-image-preview-css')) return;
        const style = document.createElement('style');
        style.id = 'studio-image-preview-css';
        style.textContent = `
            .studio-preview-frame {
                position: relative;
                width: min(1280px, 92vw);
                height: min(820px, 78vh);
                max-width: 100%;
                border-radius: 24px;
                overflow: hidden;
                background: color-mix(in srgb,var(--studio-panel,var(--panel,#fbf5ee)) 96%,transparent);
                border: 1px solid var(--studio-border,var(--line,rgba(91,74,54,.12)));
                box-shadow: var(--studio-shadow-raised,0 22px 54px rgba(104,80,52,.13),0 3px 10px rgba(92,70,46,.07),inset 0 1px 0 rgba(255,255,255,.82));
                cursor: grab;
                user-select: none;
                touch-action: none;
            }
            .studio-preview-frame.panning { cursor: grabbing; }
            .studio-preview-frame.panning .studio-preview-img { transition: none; }
            .studio-preview-img {
                display: block;
                width: 100%;
                height: 100%;
                object-fit: contain;
                transition: transform .12s ease-out;
                transform-origin: 0 0;
                -webkit-user-drag: none;
                user-select: none;
                pointer-events: none;
                background: transparent;
            }
            html.studio-theme-dark .studio-preview-frame,
            body.studio-theme-dark .studio-preview-frame,
            html.theme-dark .studio-preview-frame,
            body.theme-dark .studio-preview-frame,
            .theme-dark .studio-preview-frame {
                background: color-mix(in srgb,var(--studio-panel,var(--panel,#1e1e1e)) 96%,transparent);
                border-color: var(--studio-border,var(--line,rgba(255,255,255,.08)));
                box-shadow: var(--studio-shadow-raised,0 24px 62px rgba(0,0,0,.42),0 3px 12px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,255,255,.05));
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * 给一个容器绑定滚轮缩放 + 拖拽平移
     * @param {HTMLElement} container - 外框（必须 overflow:hidden）
     * @param {Object} [options]
     * @param {HTMLImageElement} [options.img] - 容器内的图片，默认取 .studio-preview-img 或第一个 img
     * @param {number} [options.minZoom=1]
     * @param {number} [options.maxZoom=6]
     * @returns {{reset:Function, apply:Function, getZoom:Function}|null}
     */
    function attach(container, options){
        if(!container) return null;
        options = options || {};
        const img = options.img
            || container.querySelector('.studio-preview-img')
            || container.querySelector('img');
        if(!img) return null;
        const minZoom = options.minZoom || 1;
        const maxZoom = options.maxZoom || 6;

        let zoom = 1;
        let pan = { x:0, y:0 };
        let drag = null;

        function apply(){
            img.style.transform = `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`;
            img.style.transformOrigin = '0 0';
        }
        function reset(){
            zoom = 1;
            pan = { x:0, y:0 };
            drag = null;
            container.classList.remove('panning');
            apply();
        }

        function onWheel(e){
            e.preventDefault();
            e.stopPropagation();
            const rect = container.getBoundingClientRect();
            const lx = e.clientX - rect.left;
            const ly = e.clientY - rect.top;
            const before = {
                x: (lx - pan.x) / zoom,
                y: (ly - pan.y) / zoom
            };
            const factor = e.deltaY > 0 ? 0.9 : 1.1;
            const nz = Math.max(minZoom, Math.min(maxZoom, zoom * factor));
            zoom = nz;
            pan = nz <= 1.001 ? { x:0, y:0 } : {
                x: lx - before.x * nz,
                y: ly - before.y * nz
            };
            apply();
        }

        function onDown(e){
            if(e.button !== 0 || zoom <= 1.001) return;
            if(e.target.closest('[data-no-pan], button, a, input, textarea')) return;
            drag = { sx:e.clientX, sy:e.clientY, ox:pan.x, oy:pan.y };
            container.classList.add('panning');
            e.preventDefault();
            e.stopPropagation();
        }
        function onMove(e){
            if(!drag) return;
            pan = {
                x: drag.ox + e.clientX - drag.sx,
                y: drag.oy + e.clientY - drag.sy
            };
            apply();
        }
        function onUp(){
            if(!drag) return;
            drag = null;
            container.classList.remove('panning');
        }

        /* 双击复位 —— 缩放后双击图片直接还原 */
        function onDblClick(e){
            if(zoom <= 1.001) return;
            e.preventDefault();
            e.stopPropagation();
            reset();
        }

        container.addEventListener('wheel', onWheel, { passive:false });
        container.addEventListener('mousedown', onDown);
        container.addEventListener('dblclick', onDblClick);
        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', onUp);

        return {
            reset,
            apply,
            getZoom: () => zoom
        };
    }

    injectStyles();
    window.StudioImagePreview = { attach };
})();
