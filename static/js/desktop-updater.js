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
                <div class="studio-modal-head"><div><div class="studio-modal-kicker">SHIYIN AI</div><h2 class="studio-modal-title">发现新更新</h2></div><button class="studio-modal-close" type="button" aria-label="关闭">×</button></div>
                <div class="studio-modal-body"><p class="studio-modal-copy">新版本 ${version} 已准备好。现在更新会关闭并重启软件；也可以安排到下次启动时更新。</p><div class="update-notes-box"><div class="update-notes-head"><strong>更新说明</strong><span class="update-notes-version">${version}</span></div><p class="update-notes-empty"></p></div></div>
                <div class="studio-modal-actions"><button class="studio-modal-btn" type="button" data-action="defer">下次启动更新</button><button class="studio-modal-btn primary" type="button" data-action="apply">立即更新</button></div>
            </div>`;
        modal.querySelector('.update-notes-empty').textContent = notes;
        modal.querySelector('.studio-modal-title').textContent = info.downloaded ? '更新已下载完成' : info.kind === 'hot' ? '发现局域网热更新' : '发现软件更新';
        modal.querySelector('.studio-modal-copy').textContent = `${info.kind === 'hot' ? '热更新' : '新版本'} ${version} · ${(Number(info.assetSize || 0) / 1048576).toFixed(1)} MB。点击立即更新后下载并验证，完成后自动退出、安装并重新启动。请先保存正在编辑的内容。`;
        modal.querySelector('[data-action="defer"]').textContent = info.downloaded ? '下次启动更新' : '稍后提醒';
        modal.querySelector('.studio-modal-close').addEventListener('click', closeModal);
        modal.querySelector('[data-action="defer"]').addEventListener('click', async () => {
            try {
                if (info.downloaded) await invoke('defer_downloaded_update');
                closeModal();
                if (info.downloaded) alert(`已安排在下次启动时更新到 ${version}。`);
            } catch (error) { alert(`安排更新失败：${error.message || error}`); }
        });
        const button = modal.querySelector('[data-action="apply"]');
        let applying = false;
        const applyUpdate = async () => {
            if (applying) return;
            applying = true;
            let activityTimer = 0;
            button.disabled = true;
            button.textContent = '正在启动更新器…';
            try {
                if (!info.downloaded) {
                    const started = Date.now();
                    const renderActivity = () => { button.textContent = `正在处理… ${Math.floor((Date.now() - started) / 1000)}秒`; };
                    renderActivity();
                    activityTimer = setInterval(renderActivity, 1000);
                    modal.querySelector('.studio-modal-copy').textContent = '正在下载单个增量包，并在本机解包、校验变化文件。较慢磁盘可能需要一些时间，中断后可重试并续传。';
                    await invoke('download_update');
                    info.downloaded = true;
                }
                clearInterval(activityTimer);
                button.textContent = '正在启动独立更新器…';
                await invoke('apply_downloaded_update');
            } catch (error) {
                applying = false;
                button.disabled = false;
                button.textContent = '重试更新';
                modal.querySelector('.studio-modal-close').hidden = false;
                alert(`更新失败：${error.message || error}`);
            }
            finally { clearInterval(activityTimer); }
        };
        button.addEventListener('click', applyUpdate);
        document.body.append(modal);
        activeModal = modal;
        if (info.continuation) {
            modal.querySelector('.studio-modal-title').textContent = '正在自动补齐更新';
            modal.querySelector('[data-action="defer"]').hidden = true;
            modal.querySelector('.studio-modal-close').hidden = true;
            setTimeout(applyUpdate, 0);
        }
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

    async function showHistoryModal(result) {
        showStatusModal('当前已是最新版本', `当前版本 v${result.currentVersion} · 每一次更新，都让创作更进一步。`);
        const modal = activeModal;
        const previousFocus = document.activeElement;
        modal.classList.add('update-history-modal');
        const style = document.createElement('style');
        style.textContent = `
            .update-history-modal { --history-line:color-mix(in srgb,currentColor 13%,transparent); }
            .update-history-modal .studio-modal-panel { width:min(720px,100%); border-radius:20px; }
            .update-history-modal .studio-modal-head { padding:26px 28px 20px; }
            .update-history-modal .studio-modal-body { padding:22px 28px; overscroll-behavior:contain; }
            .update-history-modal .studio-modal-title { font-size:23px; letter-spacing:-.5px; }
            .update-history-heading { display:flex; align-items:center; justify-content:space-between; margin:24px 0; gap:12px; }
            .update-history-heading h3 { margin:0; font-size:15px; }
            .update-history-count,.update-history-date { font-size:11px; opacity:.6; font-variant-numeric:tabular-nums; }
            .update-history-list { list-style:none; margin:0; padding:0 0 0 8px; }
            .update-history-entry { position:relative; border-left:1px solid var(--history-line); padding:0 0 26px 25px; }
            .update-history-entry:last-child { border-color:transparent; padding-bottom:4px; }
            .update-history-entry::before { content:''; position:absolute; left:-4px; top:8px; width:7px; height:7px; border-radius:50%; background:#99958e; }
            .update-history-entry:first-child::before { background:#22a06b; box-shadow:0 0 0 5px #22a06b18; }
            .update-history-meta { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:12px; }
            .update-history-meta strong { font-size:15px; letter-spacing:.2px; }
            .update-history-badge { padding:3px 8px; border-radius:20px; background:#22a06b18; color:#229765; font-size:10px; font-weight:600; }
            .update-history-type { font-size:10px; padding:3px 8px; border-radius:6px; border:1px solid var(--history-line); opacity:.75; }
            .update-history-type[data-kind="baseline"] { color:#ba873b; border-color:#ba873b55; background:#ba873b0b; }
            .update-history-filters { display:flex; gap:7px; flex-wrap:wrap; margin:0 0 24px; }
            .update-history-filters button { font:inherit; font-size:11px; color:inherit; border:1px solid var(--history-line); border-radius:20px; background:transparent; padding:6px 11px; cursor:pointer; }
            .update-history-filters button[aria-pressed="true"] { background:#22a06b18; color:#229765; border-color:#22976566; }
            .update-history-entry[hidden] { display:none; }
            .update-history-meta strong { overflow-wrap:anywhere; }
            .update-history-card { border:1px solid var(--history-line); background:color-mix(in srgb,currentColor 2%,transparent); border-radius:12px; padding:15px 17px; }
            .update-history-card ul { padding-left:16px; margin:0; font-size:12px; line-height:1.85; }
            .update-history-card li+li { margin-top:8px; }
            .update-history-card li::marker { color:#99958e; }
            .update-history-card p { margin:0; font-size:12px; opacity:.6; line-height:1.8; }
            .update-history-card details { margin-top:10px; }
            .update-history-card summary { cursor:pointer; font-size:12px; opacity:.7; padding:4px 0; }
            .update-history-state { font-size:13px; line-height:1.8; opacity:.65; padding:20px 0; }
            @media(max-width:540px) { .update-history-modal { padding:12px; } .update-history-modal .studio-modal-head,.update-history-modal .studio-modal-body { padding:20px; } .update-history-entry { padding-left:19px; } }
        `;
        modal.append(style);
        const body = modal.querySelector('.studio-modal-body');
        const heading = document.createElement('div');
        heading.className = 'update-history-heading';
        heading.innerHTML = '<h3>版本足迹</h3><span class="update-history-count"></span>';
        body.append(heading);
        const content = document.createElement('div');
        content.setAttribute('aria-live', 'polite');
        body.append(content);
        const state = text => {
            content.replaceChildren();
            const message = document.createElement('p');
            message.className = 'update-history-state';
            message.textContent = text;
            content.append(message);
        };
        state('正在整理版本记录…');
        const close = () => { if (activeModal === modal) closeModal(); previousFocus?.focus(); };
        modal.addEventListener('keydown', event => {
            if (event.key === 'Escape') { event.preventDefault(); close(); }
            if (event.key === 'Tab') {
                const controls = [...modal.querySelectorAll('button, summary')].filter(node => node.getClientRects().length);
                const first = controls[0], last = controls[controls.length - 1];
                if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
                else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
            }
        });
        modal.querySelectorAll('button').forEach(button => button.addEventListener('click', () => previousFocus?.focus()));
        modal.querySelector('.studio-modal-close').focus();
        const read = async path => {
            const response = await fetch(path, {cache: 'no-store', signal: AbortSignal.timeout(8000)});
            if (!response.ok) throw new Error('日志读取失败');
            const data = await response.json();
            if (!data || typeof data !== 'object') throw new Error('日志格式异常');
            return data;
        };
        const loaded = await Promise.allSettled([read('/static/update-history.json'), read('/static/update-notes.json')]);
        if (activeModal !== modal) return;
        const entries = new Map();
        const add = entry => {
            if (!entry || typeof entry !== 'object' || !entry.version) return;
            const version = String(entry.version).replace(/^v/i, '');
            const identity = entry.id || `release:${version}`;
            if (!entries.has(identity)) entries.set(identity, {...entry, version});
        };
        const archive = loaded[0].status === 'fulfilled' ? loaded[0].value : {};
        (Array.isArray(archive.history) ? archive.history : []).forEach(add);
        const current = loaded[1].status === 'fulfilled' ? loaded[1].value : {};
        (Array.isArray(current.history) ? current.history : []).forEach(add);
        // 旧日志为累计列表；只把尚未归档的新内容归入新版本。
        if (current.version && ![...entries.values()].some(entry => entry.kind !== 'component' && entry.version === String(current.version).replace(/^v/i, ''))) {
            const known = new Set([...entries.values()].flatMap(e => Array.isArray(e.items) ? e.items : []).map(x => typeof x === 'string' ? x : x?.text));
            add({...current, items: (Array.isArray(current.items) ? current.items : []).filter(x => !known.has(typeof x === 'string' ? x : x?.text))});
        }
        if (!entries.size) {
            state(loaded.some(x => x.status === 'rejected') ? '已确认当前没有更新。版本日志暂时无法读取，请关闭后重新检查。' : '已确认当前没有更新，暂时还没有版本日志。');
            return;
        }
        content.replaceChildren();
        if (loaded.some(x => x.status === 'rejected')) {
            const warning = document.createElement('p');
            warning.className = 'update-history-state';
            warning.textContent = '部分日志暂时无法读取，以下为已读取的版本记录。';
            content.append(warning);
        }
        const list = document.createElement('ol');
        list.className = 'update-history-list';
        const ordered = [...entries.values()].sort((a,b) => (Date.parse(b.updated_at) || 0) - (Date.parse(a.updated_at) || 0) || b.version.localeCompare(a.version, undefined, {numeric:true}));
        const filters = document.createElement('div');
        filters.className = 'update-history-filters';
        filters.setAttribute('role', 'group');
        filters.setAttribute('aria-label', '日志类型');
        const labels = {baseline:'基线切换', hot:'完整热更新', web:'纯前端热更新', 'hot-updater':'更新器热更新', 'hot-bootstrap':'历史引导更新', component:'组件更新', release:'版本更新'};
        const components = {'person-depth':'人物深度模型', 'video-depth':'深度视频模型', 'video-depth-runtime':'深度视频运行时', 'cutout-runtime':'抠图运行时'};
        const group = entry => ['hot','web','hot-updater','hot-bootstrap'].includes(entry.kind) ? 'hot' : entry.kind || 'release';
        const select = value => {
            let count = 0;
            [...list.children].forEach(row => { row.hidden = value !== 'all' && row.dataset.group !== value; if (!row.hidden) count++; });
            filters.querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === value)));
            heading.querySelector('span').textContent = `${count} 条记录 · 由新到旧`;
        };
        for (const [value,label] of [['all','全部'],['baseline','基线切换'],['hot','热更新'],['component','组件'],['release','版本更新']]) {
            const button = document.createElement('button');
            button.type = 'button'; button.dataset.filter = value; button.textContent = label;
            button.addEventListener('click', () => select(value));
            filters.append(button);
        }
        heading.after(filters);
        for (const entry of ordered) {
            const row = document.createElement('li');
            row.className = 'update-history-entry';
            row.dataset.group = group(entry);
            row.innerHTML = '<div class="update-history-meta"><strong></strong><time class="update-history-date"></time></div><div class="update-history-card"></div>';
            row.querySelector('strong').textContent = entry.kind === 'component' ? `${components[entry.component] || '组件'} · ${entry.version}` : /^\d{14}$/.test(entry.version) ? entry.version : `v${entry.version}`;
            const type = document.createElement('span');
            type.className = 'update-history-type'; type.dataset.kind = entry.kind || 'release';
            type.textContent = labels[entry.kind] || labels.release;
            row.querySelector('.update-history-meta').append(type);
            const date = row.querySelector('time');
            const timestamp = Date.parse(entry.updated_at);
            date.textContent = Number.isFinite(timestamp) ? new Intl.DateTimeFormat('zh-CN', {year:'numeric',month:'2-digit',day:'2-digit',timeZone:'Asia/Shanghai'}).format(timestamp) : '日期未记录';
            if (Number.isFinite(timestamp)) date.dateTime = new Date(timestamp).toISOString();
            if (entry.kind !== 'component' && entry.record_status !== 'failed' && entry.version === String(result.currentVersion).replace(/^v/i,'')) {
                const badge = document.createElement('span');
                badge.className = 'update-history-badge';
                badge.textContent = '当前版本';
                row.querySelector('.update-history-meta').append(badge);
            }
            if (['built', 'failed'].includes(entry.record_status)) {
                const status = document.createElement('span');
                status.className = 'update-history-type';
                status.textContent = entry.record_status === 'failed' ? '未发布 · 校验失败' : '构建记录';
                row.querySelector('.update-history-meta').append(status);
            }
            const card = row.querySelector('.update-history-card');
            const items = (Array.isArray(entry.items) ? entry.items : []).map(x => typeof x === 'string' ? x : x?.text || x?.title).filter(x => typeof x === 'string' && x.trim());
            const renderItems = values => {
                const ul = document.createElement('ul');
                for (const text of values) { const li = document.createElement('li'); li.textContent = text; ul.append(li); }
                return ul;
            };
            if (!items.length) { const p = document.createElement('p'); p.textContent = '该版本未单独记录更新说明。'; card.append(p); }
            else {
                card.append(renderItems(items.slice(0,4)));
                if (items.length > 4) {
                    const details = document.createElement('details');
                    const summary = document.createElement('summary');
                    summary.textContent = `展开其余 ${items.length - 4} 条更新`;
                    details.append(summary, renderItems(items.slice(4)));
                    card.append(details);
                }
            }
            list.append(row);
        }
        content.append(list);
        select('all');
    }

    async function checkAndDownload(options = {}) {
        if (checking) return;
        checking = true;
        const button = options.button;
        const originalText = button?.textContent;
        if (button) { button.disabled = true; button.textContent = '正在检查…'; }
        try {
            const result = await invoke('check_for_update');
            // 补齐计划跨重启续跑时静默处理，避免每个中间版本都弹出一次提示。
            // 即使当前清单暂时不可用，也要保留续跑状态并交给后台重试。
            if (result.continuation) {
                if (!result.available) return result;
                if (!result.downloaded) await invoke('download_update');
                await invoke('apply_downloaded_update');
                return result;
            }
            if (!result.available) {
                if (options.manual) await showHistoryModal(result);
                return result;
            }
            if (options.continuationOnly && !result.continuation) return result;
            showModal(result);
            return result;
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

    async function saveCanvasDownloads(items = []) {
        const directory = await invoke('choose_download_directory');
        if (!directory) return {cancelled: true, count: 0};
        let count = 0;
        for (const item of Array.isArray(items) ? items : []) {
            const url = String(item?.url || '').trim();
            const name = String(item?.name || '').trim();
            if (!url || !name) continue;
            const response = await fetch(url);
            if (!response.ok) throw new Error(`下载 ${name} 失败（HTTP ${response.status}）`);
            const bytes = Array.from(new Uint8Array(await response.arrayBuffer()));
            await invoke('write_download_file', {directory, filename: name, data: bytes});
            count += 1;
        }
        return {cancelled: false, count};
    }

    function replyCanvasDownload(target, origin, requestId, payload) {
        target?.postMessage({type: 'desktop-canvas-download:response', requestId, ...payload}, origin || location.origin);
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
        if (data.type === 'desktop-canvas-download:save') {
            try {
                const result = await saveCanvasDownloads(data.items);
                replyCanvasDownload(event.source, event.origin, data.requestId, result);
            } catch (error) {
                replyCanvasDownload(event.source, event.origin, data.requestId, {error: error.message || String(error)});
            }
        }
    });

    document.addEventListener('DOMContentLoaded', async () => {
        try {
            const settings = await invoke('get_update_settings');
            if (settings.updatePolicy === 'automatic') {
                setTimeout(() => checkAndDownload().catch(() => {}), 1200);
                setInterval(async () => {
                    if (activeModal || document.hidden) return;
                    try {
                        if ((await invoke('get_update_settings')).updatePolicy === 'automatic') await checkAndDownload();
                    } catch (_) {}
                }, 60000);
            } else if (settings.updatePolicy !== 'disabled') {
                setTimeout(() => checkAndDownload({continuationOnly: true}).catch(() => {}), 1200);
            }
        } catch (_) {
            // 浏览器模式不加载桌面更新器，不影响正常使用。
        }
    }, {once: true});
})();
