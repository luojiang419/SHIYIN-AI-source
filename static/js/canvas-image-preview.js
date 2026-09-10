(function(){
    'use strict';
    const sessions = new WeakMap();

    function cancel(img){
        const session = sessions.get(img);
        if(!session) return;
        sessions.delete(img);
        session.dispose();
    }

    function open({img, stage, sourceImage, previewSrc, originalSrc, onReady}){
        cancel(img);
        img.onload = null;
        img.onerror = null;
        img.removeAttribute('src');
        // 原图地址已经由调用方归一为同源代理；与节点图片保持相同缓存模式。
        img.removeAttribute('crossorigin');
        img.style.visibility = 'hidden';
        img.dataset.editorLoadState = 'loading';
        const previousPosition = stage.style.position;
        stage.style.position = 'relative';
        stage.setAttribute('aria-busy', 'true');
        const layer = document.createElement('div');
        layer.style.cssText = 'position:absolute;inset:0;z-index:10;display:flex;align-items:center;justify-content:center;padding:18px;background:inherit;border-radius:inherit;overflow:hidden;';
        const status = document.createElement('div');
        status.setAttribute('role', 'status');
        status.style.cssText = 'position:absolute;bottom:16px;left:16px;right:16px;text-align:center;font-size:12px;line-height:1.5;color:var(--muted,#888);';
        status.textContent = '正在加载图片…';
        layer.append(status);
        stage.append(layer);
        let probe = null;
        let pixels = null;
        let disposed = false;
        const current = () => !disposed && sessions.get(img) === session;
        const releaseProbe = () => {
            if(!probe) return;
            probe.onload = null; probe.onerror = null;
            probe.removeAttribute('src'); probe = null;
        };
        const session = {dispose(){
            disposed = true;
            releaseProbe();
            layer.remove();
            stage.style.position = previousPosition;
            stage.removeAttribute('aria-busy');
            img.onload = null; img.onerror = null;
            img.removeAttribute('src');
            img.style.visibility = '';
            delete img.dataset.editorLoadState;
        }};
        sessions.set(img, session);

        function showPixels(source){
            // 节点升级高清 src 时 complete 可为 false，但上一张已解码的图仍在显示。
            if(!current() || !source?.naturalWidth || !source.naturalHeight) return false;
            const canvas = document.createElement('canvas');
            // 只复制屏幕预览所需像素，不序列化图片，也不创建全尺寸编辑缓冲区。
            const scale = Math.min(1, 1536 / Math.max(source.naturalWidth, source.naturalHeight));
            canvas.width = Math.max(1, Math.round(source.naturalWidth * scale));
            canvas.height = Math.max(1, Math.round(source.naturalHeight * scale));
            try { canvas.getContext('2d').drawImage(source, 0, 0, canvas.width, canvas.height); }
            catch(e){ return false; }
            canvas.dataset.editorPreviewPixels = '1';
            canvas.setAttribute('aria-label', '图片预览');
            canvas.style.cssText = 'display:block;width:100%;height:100%;max-width:1300px;max-height:840px;object-fit:contain;';
            pixels?.remove(); pixels = canvas;
            layer.prepend(canvas);
            if(img.dataset.editorLoadState !== 'error') status.textContent = '';
            return true;
        }

        if(!showPixels(sourceImage) && previewSrc && previewSrc !== originalSrc){
            probe = new Image();
            probe.decoding = 'async';
            probe.onload = () => showPixels(probe);
            probe.src = previewSrc;
        }
        img.decoding = 'async';
        img.fetchPriority = 'high';
        img.onload = async () => {
            try { await img.decode(); } catch(e){ if(!img.naturalWidth) return; }
            if(!current()) return;
            img.dataset.editorLoadState = 'ready';
            img.style.visibility = '';
            layer.remove();
            layer.replaceChildren();
            pixels = null;
            releaseProbe();
            img.onload = null; img.onerror = null;
            stage.removeAttribute('aria-busy');
            onReady();
        };
        img.onerror = () => {
            if(!current()) return;
            img.dataset.editorLoadState = 'error';
            stage.removeAttribute('aria-busy');
            status.textContent = pixels ? '原图加载失败，当前显示预览图。' : '图片加载失败。';
            const retry = document.createElement('button');
            retry.type = 'button'; retry.textContent = '重试';
            retry.style.cssText = 'margin-left:8px;text-decoration:underline;cursor:pointer;';
            retry.onclick = () => {
                if(!current()) return;
                img.dataset.editorLoadState = 'loading';
                stage.setAttribute('aria-busy','true');
                status.textContent = '正在重新加载图片…';
                img.removeAttribute('src'); img.src = originalSrc;
            };
            status.append(retry);
        };
        // 与即时显示并行，绝不通过定时替换 src 打断缩略图或暴露空白窗口。
        img.src = originalSrc;
    }
    window.CanvasImagePreview = {open, cancel};
})();
