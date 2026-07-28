(function () {
    'use strict';

    const invoke = (command, args) => {
        const call = window.__TAURI__?.core?.invoke || window.__TAURI_INTERNALS__?.invoke;
        if (!call) return Promise.reject(new Error('自动更新只在 Windows 桌面版中可用。'));
        return call(command, args);
    };

    let activeModal = null;
    let checking = false;

    function closeModal() {
        activeModal?.remove();
        activeModal = null;
    }

    function showModal(info) {
        closeModal();
        const version = `v${String(info.latestVersion || '').replace(/^v/i, '')}`;
        const notes = String(info.releaseNotes || '').trim() || '本次 Release 未提供更新说明。';
        const modal = document.createElement('div');
        modal.className = 'studio-modal';
        modal.innerHTML = `
            <div class="studio-modal-panel" role="dialog" aria-modal="true" aria-label="更新已下载完成">
                <div class="studio-modal-head"><div><div class="studio-modal-kicker">SHIYIN AI</div><h2 class="studio-modal-title">更新已下载完成</h2></div><button class="studio-modal-close" type="button" aria-label="关闭">×</button></div>
                <div class="studio-modal-body"><p class="studio-modal-copy">新版本 ${version} 已准备好。现在更新会关闭并重启软件；也可以安排到下次启动时更新。</p><div class="update-notes-box"><div class="update-notes-head"><strong>更新说明</strong><span class="update-notes-version">${version}</span></div><p class="update-notes-empty"></p></div></div>
                <div class="studio-modal-actions"><button class="studio-modal-btn" type="button" data-action="defer">下次启动更新</button><button class="studio-modal-btn primary" type="button" data-action="apply">立即更新</button></div>
            </div>`;
        modal.querySelector('.update-notes-empty').textContent = notes;
        modal.querySelector('.studio-modal-close').addEventListener('click', closeModal);
        modal.querySelector('[data-action="defer"]').addEventListener('click', async () => {
            try {
                await invoke('defer_downloaded_update');
                closeModal();
                alert(`已安排在下次启动时更新到 ${version}。`);
            } catch (error) { alert(`安排更新失败：${error.message || error}`); }
        });
        modal.querySelector('[data-action="apply"]').addEventListener('click', async event => {
            const button = event.currentTarget;
            button.disabled = true;
            button.textContent = '正在启动更新器…';
            try { await invoke('apply_downloaded_update'); } catch (error) { button.disabled = false; button.textContent = '立即更新'; alert(`启动更新失败：${error.message || error}`); }
        });
        document.body.append(modal);
        activeModal = modal;
    }

    function showStatusModal(title, message) {
        closeModal();
        const modal = document.createElement('div');
        modal.className = 'studio-modal';
        modal.innerHTML = `
            <div class="studio-modal-panel" role="dialog" aria-modal="true" aria-label="${title}">
                <div class="studio-modal-head"><div><div class="studio-modal-kicker">SHIYIN AI</div><h2 class="studio-modal-title"></h2></div><button class="studio-modal-close" type="button" aria-label="关闭">×</button></div>
                <div class="studio-modal-body"><p class="studio-modal-copy"></p></div>
                <div class="studio-modal-actions"><button class="studio-modal-btn primary" type="button" data-action="confirm">确定</button></div>
            </div>`;
        modal.querySelector('.studio-modal-title').textContent = title;
        modal.querySelector('.studio-modal-copy').textContent = message;
        modal.querySelector('.studio-modal-close').addEventListener('click', closeModal);
        modal.querySelector('[data-action="confirm"]').addEventListener('click', closeModal);
        document.body.append(modal);
        activeModal = modal;
    }

    async function checkAndDownload(options = {}) {
        if (checking) return;
        checking = true;
        const button = options.button;
        const originalText = button?.textContent;
        if (button) { button.disabled = true; button.textContent = '正在检查…'; }
        try {
            const result = await invoke('check_for_update');
            if (!result.available) {
                if (options.manual) showStatusModal('当前已是最新版本', `当前版本 v${result.currentVersion} 已是最新版本。`);
                return result;
            }
            if (button) button.textContent = '正在下载…';
            const downloaded = result.downloaded ? result : await invoke('download_update');
            showModal(downloaded);
            return downloaded;
        } catch (error) {
            if (options.manual) showStatusModal('检查更新失败', String(error?.message || error || '未知错误'));
            throw error;
        } finally {
            checking = false;
            if (button) { button.disabled = false; button.textContent = originalText || '检查更新'; }
        }
    }

    window.openDesktopUpdater = () => checkAndDownload({manual: true}).catch(() => {});

    function reply(target, origin, requestId, payload) {
        target?.postMessage({type: 'desktop-update-settings:response', requestId, ...payload}, origin || location.origin);
    }

    window.addEventListener('message', async event => {
        if (event.origin && event.origin !== location.origin) return;
        const data = event.data || {};
        if (data.type === 'desktop-update-settings:get') {
            try { reply(event.source, event.origin, data.requestId, {settings: await invoke('get_update_settings')}); }
            catch (error) { reply(event.source, event.origin, data.requestId, {error: error.message || String(error)}); }
        }
        if (data.type === 'desktop-update-settings:save') {
            try { reply(event.source, event.origin, data.requestId, {settings: await invoke('save_update_settings', {settings: data.settings})}); }
            catch (error) { reply(event.source, event.origin, data.requestId, {error: error.message || String(error)}); }
        }
        if (data.type === 'desktop-update:check') {
            checkAndDownload({manual: true}).then(result => reply(event.source, event.origin, data.requestId, {result})).catch(error => reply(event.source, event.origin, data.requestId, {error: error.message || String(error)}));
        }
    });

    document.addEventListener('DOMContentLoaded', async () => {
        try {
            const settings = await invoke('get_update_settings');
            if (settings.updatePolicy === 'automatic') {
                setTimeout(() => checkAndDownload().catch(() => {}), 1200);
            }
        } catch (_) {
            // 浏览器模式不加载桌面更新器，不影响正常使用。
        }
    }, {once: true});
})();
