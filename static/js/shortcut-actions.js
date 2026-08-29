(function(global){
    'use strict';

    const actions = [
        {id:'canvas.run', category:'画布操作', name:'运行选中节点', context:'canvas', defaultBinding:'Ctrl+Enter'},
        {id:'canvas.runCascade', category:'画布操作', name:'一键运行工作流', context:'canvas', defaultBinding:'Ctrl+Shift+Enter'},
        {id:'canvas.undo', category:'画布操作', name:'撤销', context:'canvas', defaultBinding:'Ctrl+Z'},
        {id:'canvas.redo', category:'画布操作', name:'恢复', context:'canvas', defaultBinding:'Ctrl+Shift+Z'},
        {id:'canvas.copy', category:'画布操作', name:'复制选中节点', context:'canvas', defaultBinding:'Ctrl+C'},
        {id:'canvas.paste', category:'画布操作', name:'粘贴节点', context:'canvas', defaultBinding:'Ctrl+V'},
        {id:'canvas.delete', category:'画布操作', name:'删除选中节点', context:'canvas', defaultBinding:'Delete'},
        {id:'canvas.selectAll', category:'画布操作', name:'全选节点', context:'canvas', defaultBinding:'Ctrl+A'},
        {id:'canvas.clearSelection', category:'画布操作', name:'取消选择', context:'canvas', defaultBinding:'Escape'},
        {id:'canvas.group', category:'画布操作', name:'编组选中节点', context:'canvas', defaultBinding:'Ctrl+G'},
        {id:'canvas.ungroup', category:'画布操作', name:'解散选中分组', context:'canvas', defaultBinding:'Ctrl+Shift+G'},
        {id:'canvas.arrange', category:'画布操作', name:'整理选中节点', context:'canvas', defaultBinding:'Ctrl+Shift+A'},
        {id:'canvas.createMenu', category:'画布操作', name:'打开节点创建菜单', context:'canvas', defaultBinding:'N'},
        {id:'canvas.toolSelect', category:'画布操作', name:'切换到选择工具', context:'canvas', defaultBinding:'V'},
        {id:'canvas.toolPan', category:'画布操作', name:'切换到移动工具', context:'canvas', defaultBinding:'H'},
        {id:'canvas.temporaryControlTool', category:'画布操作', name:'按住 Ctrl 临时反转工具', context:'canvas', defaultBinding:'Ctrl', hold:true},
        {id:'canvas.temporaryTool', category:'画布操作', name:'临时反转选择/移动工具', context:'canvas', defaultBinding:'Space', hold:true},
        {id:'canvas.temporarySelect', category:'画布操作', name:'临时切换到选择工具', context:'canvas', defaultBinding:'R', hold:true},
        {id:'canvas.fitAll', category:'视图与面板', name:'适应全部节点', context:'canvas', defaultBinding:'F'},
        {id:'canvas.overview', category:'视图与面板', name:'缩小画布视图', context:'canvas', defaultBinding:'Z'},
        {id:'canvas.toggleAssets', category:'视图与面板', name:'打开/关闭素材库', context:'canvas', defaultBinding:'A'},
        {id:'canvas.toggleLogs', category:'视图与面板', name:'打开/关闭日志', context:'canvas', defaultBinding:''},
        {id:'canvas.toggleShortcuts', category:'视图与面板', name:'打开/关闭快捷键说明', context:'canvas', defaultBinding:'Ctrl+/'},
        {id:'canvas.toggleWorkflow', category:'视图与面板', name:'打开/关闭工作流导入导出', context:'canvas', defaultBinding:''},
        {id:'canvas.promptPresets', category:'视图与面板', name:'打开提示词预设', context:'canvas', defaultBinding:''},
        {id:'canvas.promptTemplates', category:'视图与面板', name:'打开提示词模板库', context:'canvas', defaultBinding:''},

        {id:'create.image', category:'创建节点', name:'创建图片节点', context:'canvas', defaultBinding:''},
        {id:'create.group', category:'创建节点', name:'创建智能分组节点', context:'canvas', defaultBinding:''},
        {id:'create.prompt', category:'创建节点', name:'创建提示词节点', context:'canvas', defaultBinding:''},
        {id:'create.h3Video', category:'创建节点', name:'创建 MiniMax H3 视频节点', context:'canvas', defaultBinding:''},
        {id:'create.panorama', category:'创建节点', name:'创建 720° 取景器节点', context:'canvas', defaultBinding:''},
        {id:'create.dwpose', category:'创建节点', name:'创建动作提取节点', context:'canvas', defaultBinding:''},
        {id:'create.poseReplicate', category:'创建节点', name:'创建一键复刻节点', context:'canvas', defaultBinding:''},
        {id:'create.multiView', category:'创建节点', name:'创建三视图节点', context:'canvas', defaultBinding:''},
        {id:'create.batch', category:'创建节点', name:'创建批量处理节点', context:'canvas', defaultBinding:''},

        {id:'selected.preview', category:'选中节点功能', name:'预览选中素材', context:'canvas', defaultBinding:'Enter'},
        {id:'selected.download', category:'选中节点功能', name:'下载选中素材/分组', context:'canvas', defaultBinding:''},
        {id:'selected.duplicateMedia', category:'选中节点功能', name:'将选中素材复制到画布', context:'canvas', defaultBinding:''},
        {id:'selected.crop', category:'选中节点功能', name:'裁剪选中图片', context:'canvas', defaultBinding:''},
        {id:'selected.outpaint', category:'选中节点功能', name:'扩图选中图片', context:'canvas', defaultBinding:''},
        {id:'selected.mask', category:'选中节点功能', name:'遮罩编辑选中图片', context:'canvas', defaultBinding:''},
        {id:'selected.brush', category:'选中节点功能', name:'画笔编辑选中图片', context:'canvas', defaultBinding:''},
        {id:'selected.grid', category:'选中节点功能', name:'宫格切分/拼接选中素材', context:'canvas', defaultBinding:''},
        {id:'selected.multiView', category:'选中节点功能', name:'从选中图片创建三视图', context:'canvas', defaultBinding:''},
        {id:'selected.batch', category:'选中节点功能', name:'批量处理选中图片/分组', context:'canvas', defaultBinding:''},
        {id:'selected.arrangeGroup', category:'选中节点功能', name:'整理选中分组内容', context:'canvas', defaultBinding:''},

        {id:'editor.previous', category:'预览与编辑', name:'上一张/上一帧', context:'editor', defaultBinding:'ArrowLeft'},
        {id:'editor.next', category:'预览与编辑', name:'下一张/下一帧', context:'editor', defaultBinding:'ArrowRight'},
        {id:'editor.close', category:'预览与编辑', name:'关闭预览或编辑器', context:'editor', defaultBinding:'Escape'},
        {id:'editor.apply', category:'预览与编辑', name:'应用当前编辑', context:'editor', defaultBinding:'Ctrl+Enter'},
        {id:'editor.download', category:'预览与编辑', name:'下载当前素材', context:'editor', defaultBinding:''},
        {id:'editor.downloadAll', category:'预览与编辑', name:'下载当前分组全部素材', context:'editor', defaultBinding:''},
        {id:'editor.compare', category:'预览与编辑', name:'切换原图对比', context:'editor', defaultBinding:''},
        {id:'editor.panorama', category:'预览与编辑', name:'切换 360° 全景预览', context:'editor', defaultBinding:''},
        {id:'editor.exportPanorama', category:'预览与编辑', name:'导出全景当前画面', context:'editor', defaultBinding:''},
        {id:'editor.undoDrawing', category:'预览与编辑', name:'撤销绘制', context:'editor', defaultBinding:'Ctrl+Z'},
        {id:'editor.redoDrawing', category:'预览与编辑', name:'恢复绘制', context:'editor', defaultBinding:'Ctrl+Shift+Z'},
        {id:'editor.clearDrawing', category:'预览与编辑', name:'清空绘制', context:'editor', defaultBinding:''},
        {id:'editor.videoFirstFrame', category:'预览与编辑', name:'导出视频首帧', context:'editor', defaultBinding:''},
        {id:'editor.videoCurrentFrame', category:'预览与编辑', name:'导出视频当前帧', context:'editor', defaultBinding:''},
        {id:'editor.videoLastFrame', category:'预览与编辑', name:'导出视频尾帧', context:'editor', defaultBinding:''}
    ];

    const byId = new Map(actions.map(action => [action.id, Object.freeze({...action})]));
    const modifierOrder = ['Ctrl', 'Alt', 'Shift', 'Meta'];
    const modifierAliases = new Map([
        ['control', 'Ctrl'], ['ctrl', 'Ctrl'], ['alt', 'Alt'], ['option', 'Alt'],
        ['shift', 'Shift'], ['meta', 'Meta'], ['cmd', 'Meta'], ['command', 'Meta'], ['win', 'Meta']
    ]);
    const keyAliases = new Map([
        [' ', 'Space'], ['spacebar', 'Space'], ['space', 'Space'], ['esc', 'Escape'],
        ['del', 'Delete'], ['return', 'Enter'], ['arrowup', 'ArrowUp'], ['arrowdown', 'ArrowDown'],
        ['arrowleft', 'ArrowLeft'], ['arrowright', 'ArrowRight'], ['plus', 'Plus'], ['minus', 'Minus'],
        ['slash', '/'], ['backslash', '\\'], ['comma', ','], ['period', '.']
    ]);
    const reserved = new Set(['Alt+F4', 'Ctrl+Alt+Delete', 'Ctrl+Shift+Escape']);

    function normalizeKey(value){
        const raw = String(value || '').trim();
        const alias = keyAliases.get(raw.toLowerCase());
        if(alias) return alias;
        if(/^key[a-z]$/i.test(raw)) return raw.slice(3).toUpperCase();
        if(/^digit[0-9]$/i.test(raw)) return raw.slice(5);
        if(/^f(?:[1-9]|1[0-9]|2[0-4])$/i.test(raw)) return raw.toUpperCase();
        if(raw.length === 1) return raw.toUpperCase();
        return raw ? raw[0].toUpperCase() + raw.slice(1) : '';
    }

    function canonicalize(binding){
        const raw = String(binding || '').trim();
        if(!raw) return '';
        const parts = raw.split('+').map(part => part.trim()).filter(Boolean);
        const modifiers = new Set();
        let key = '';
        parts.forEach(part => {
            const modifier = modifierAliases.get(part.toLowerCase());
            if(modifier) modifiers.add(modifier);
            else key = normalizeKey(part);
        });
        if(!key) return modifiers.size === 1 ? modifierOrder.find(item => modifiers.has(item)) || '' : '';
        return [...modifierOrder.filter(item => modifiers.has(item)), key].join('+');
    }

    function keyFromEvent(event){
        const code = String(event?.code || '');
        if(/^Key[A-Z]$/.test(code)) return code.slice(3);
        if(/^Digit[0-9]$/.test(code)) return code.slice(5);
        if(/^Numpad[0-9]$/.test(code)) return code.slice(6);
        const codeMap = {
            Space:'Space', Escape:'Escape', Enter:'Enter', NumpadEnter:'Enter', Tab:'Tab',
            Backspace:'Backspace', Delete:'Delete', Insert:'Insert', Home:'Home', End:'End',
            PageUp:'PageUp', PageDown:'PageDown', ArrowUp:'ArrowUp', ArrowDown:'ArrowDown',
            ArrowLeft:'ArrowLeft', ArrowRight:'ArrowRight', Slash:'/', NumpadDivide:'/',
            Backslash:'\\', Minus:'Minus', NumpadSubtract:'Minus', Equal:'Plus', NumpadAdd:'Plus',
            Comma:',', Period:'.', NumpadDecimal:'.', Semicolon:';', Quote:"'", Backquote:'`',
            BracketLeft:'[', BracketRight:']'
        };
        if(codeMap[code]) return codeMap[code];
        if(/^F(?:[1-9]|1[0-9]|2[0-4])$/.test(code)) return code;
        return normalizeKey(event?.key);
    }

    function fromEvent(event, options={}){
        const modifierCode = String(event?.code || '').replace(/(?:Left|Right)$/, '');
        if(['Control', 'Alt', 'Shift', 'Meta'].includes(modifierCode)){
            return options.allowModifierOnly ? (modifierCode === 'Control' ? 'Ctrl' : modifierCode) : '';
        }
        const key = keyFromEvent(event);
        if(!key || ['Control', 'Shift', 'Alt', 'Meta'].includes(key)) return '';
        const parts = [];
        if(event.ctrlKey) parts.push('Ctrl');
        if(event.altKey) parts.push('Alt');
        if(event.shiftKey) parts.push('Shift');
        if(event.metaKey) parts.push('Meta');
        parts.push(key);
        return canonicalize(parts.join('+'));
    }

    function validate(binding, options={}){
        const canonical = canonicalize(binding);
        if(!canonical) return {ok:false, binding:'', error:'请按下一个非修饰键'};
        if(modifierOrder.includes(canonical) && !options.allowModifierOnly) return {ok:false, binding:canonical, error:'请同时按下一个普通按键'};
        if(canonical.includes('Meta+')) return {ok:false, binding:canonical, error:'Windows 系统键组合不可用'};
        if(reserved.has(canonical)) return {ok:false, binding:canonical, error:'该组合键由系统保留'};
        return {ok:true, binding:canonical, error:''};
    }

    function sanitizeOverrides(value){
        if(!value || typeof value !== 'object' || Array.isArray(value)) return {};
        const result = {};
        for(const [id, binding] of Object.entries(value)){
            if(!byId.has(id) || typeof binding !== 'string') continue;
            const raw = binding.trim();
            result[id] = raw ? canonicalize(raw) : '';
        }
        return result;
    }

    function resolvedBindings(overrides={}){
        const clean = sanitizeOverrides(overrides);
        const result = {};
        actions.forEach(action => {
            result[action.id] = Object.prototype.hasOwnProperty.call(clean, action.id)
                ? clean[action.id]
                : canonicalize(action.defaultBinding);
        });
        return result;
    }

    function conflicts(overrides={}, actionId, binding){
        const target = byId.get(actionId);
        const canonical = canonicalize(binding);
        if(!target || !canonical) return [];
        const resolved = resolvedBindings(overrides);
        return actions.filter(action => action.id !== actionId && action.context === target.context && resolved[action.id] === canonical);
    }

    function findAction(event, context, overrides={}, options={}){
        const binding = fromEvent(event, {allowModifierOnly:Boolean(options.hold)});
        if(!binding) return null;
        const resolved = resolvedBindings(overrides);
        return actions.find(action => action.context === context
            && Boolean(action.hold) === Boolean(options.hold)
            && resolved[action.id] === binding) || null;
    }

    global.ShortcutActions = Object.freeze({
        actions:Object.freeze(actions.map(action => Object.freeze({...action}))),
        get:id => byId.get(id) || null,
        canonicalize,
        fromEvent,
        validate,
        sanitizeOverrides,
        resolvedBindings,
        conflicts,
        findAction,
        storageKey:'shiyin_shortcut_bindings_v1',
        channelName:'shiyin-shortcuts'
    });
})(window);
