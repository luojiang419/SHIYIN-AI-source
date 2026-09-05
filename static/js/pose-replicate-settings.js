(function(global){
    'use strict';
    let catalogPromise = null;
    function combinationKey(mode, hasModel, hasScene){
        const scenario = hasModel ? (hasScene ? 'model-full-look-scene' : 'model-wardrobe')
            : (hasScene ? 'base-wardrobe-scene' : 'base-wardrobe');
        return `${mode}:${scenario}`;
    }
    function promptPolicy(node, inputs){
        const key = combinationKey(inputs.mode || node.poseReplicateMode || 'skeleton', Boolean(inputs.modelSubject?.url), Boolean(inputs.scene?.url));
        const policy = {template_id:'pose-replicate.v3.1', locale:'zh-CN'};
        const overrides = node.poseReplicatePromptTemplates || {};
        if(Object.prototype.hasOwnProperty.call(overrides, key)){
            policy.custom_template = overrides[key];
            policy.custom_template_key = key;
        }
        return policy;
    }
    function loadCatalog(){
        if(!catalogPromise) catalogPromise = fetch('/api/canvas/pose-replicate-templates')
            .then(async response => {
                if(!response.ok) throw new Error('提示词列表加载失败，请关闭后重试');
                const data = await response.json();
                if(!Array.isArray(data.items) || data.items.length !== 8) throw new Error('提示词组合数据不完整');
                return data.items;
            }).catch(error => { catalogPromise = null; throw error; });
        return catalogPromise;
    }
    function open(node, {onChange=()=>{}, beforeChange=()=>{}}={}){
        if(document.querySelector('.pose-template-dialog')) return;
        const returnFocus = document.activeElement;
        const dialog = document.createElement('dialog');
        dialog.className = 'pose-template-dialog';
        dialog.setAttribute('aria-labelledby', 'poseTemplateTitle');
        dialog.innerHTML = `<header><div><h2 id="poseTemplateTitle">一键复刻 · 提示词设置</h2><p>当前节点的全部 8 种组合 · 修改后自动保存，立即用于下一次生成</p></div><button type="button" data-close aria-label="关闭提示词设置">关闭</button></header>
            <div class="pose-template-list"><p role="status">正在加载组合提示词…</p></div>
            <section class="pose-template-editor" hidden><div class="pose-template-editor-heading"><button type="button" data-back>返回组合列表</button><h3></h3><button type="button" data-reset>恢复此组合默认值</button></div>
            <p class="pose-template-role-help"></p><p>可使用 {{output_aspect_ratio}} 自动填入画幅、{{user_instruction}} 填入节点补充要求。自定义文本将完整替换内置提示词；未放入补充变量时，补充要求会附加到末尾。</p>
            <textarea aria-label="组合完整提示词" maxlength="30000" spellcheck="false"></textarea><footer><span role="status" aria-live="polite"></span><button type="button" data-done>应用并返回</button></footer></section>`;
        document.body.appendChild(dialog);
        let entries = [], active = null, undoRecorded = false;
        const list = dialog.querySelector('.pose-template-list');
        const editor = dialog.querySelector('.pose-template-editor');
        const textarea = editor.querySelector('textarea');
        const status = editor.querySelector('[role="status"]');
        const valueFor = entry => node.poseReplicatePromptTemplates?.[entry.key] ?? entry.prompt;
        const changed = () => { if(!undoRecorded){ beforeChange(); undoRecorded = true; } };
        function persist(){
            if(!active) return true;
            if(!textarea.value.trim()){
                status.textContent = '提示词不能为空；此前生效的版本已保留。';
                return false;
            }
            if(textarea.value !== valueFor(active)){
                changed();
                node.poseReplicatePromptTemplates = {...node.poseReplicatePromptTemplates, [active.key]:textarea.value};
                if(textarea.value === active.prompt) delete node.poseReplicatePromptTemplates[active.key];
                onChange(node);
            }
            status.textContent = '已应用到当前组合，下次生成立即使用';
            return true;
        }
        function drawList(){
            list.replaceChildren();
            entries.forEach(entry => {
                const card = document.createElement('button');
                card.type = 'button'; card.className = 'pose-template-card';
                const title = document.createElement('strong');
                title.textContent = `${entry.mode === 'depth' ? '深度图' : '骨架图'} · ${entry.title}`;
                const badge = document.createElement('span');
                badge.textContent = node.poseReplicatePromptTemplates?.[entry.key] != null ? '自定义' : '内置默认';
                const preview = document.createElement('p'); preview.textContent = valueFor(entry);
                card.append(title, badge, preview);
                card.onclick = () => {
                    active = entry; list.hidden = true; editor.hidden = false; dialog.classList.add('editing');
                    editor.querySelector('h3').textContent = title.textContent;
                    editor.querySelector('.pose-template-role-help').textContent = entry.reference_order.map(item => `图${item.index}：${item.label}`).join(' · ');
                    textarea.value = valueFor(entry); status.textContent = '编辑后立即应用到当前组合'; textarea.focus();
                };
                list.appendChild(card);
            });
        }
        function back(){
            if(!persist()){ textarea.focus(); return; }
            active = null; editor.hidden = true; list.hidden = false; dialog.classList.remove('editing'); drawList();
            list.querySelector('button')?.focus();
        }
        function close(){ if(persist()) dialog.close(); else textarea.focus(); }
        textarea.addEventListener('input', persist);
        dialog.querySelector('[data-close]').onclick = close;
        dialog.querySelector('[data-back]').onclick = back;
        dialog.querySelector('[data-done]').onclick = back;
        dialog.querySelector('[data-reset]').onclick = () => { textarea.value = active.prompt; persist(); };
        dialog.addEventListener('cancel', event => { event.preventDefault(); if(active) back(); else close(); });
        dialog.addEventListener('keydown', event => {
            event.stopPropagation();
            if((event.ctrlKey || event.metaKey) && event.key === 'Enter' && active){ event.preventDefault(); back(); }
        });
        dialog.addEventListener('close', () => { dialog.remove(); if(returnFocus?.isConnected) returnFocus.focus(); }, {once:true});
        dialog.showModal();
        loadCatalog().then(data => { if(dialog.isConnected){ entries = data; drawList(); } })
            .catch(error => { if(dialog.isConnected) list.textContent = error.message; });
    }
    global.PoseReplicateSettings = {open, promptPolicy, combinationKey};
})(window);
