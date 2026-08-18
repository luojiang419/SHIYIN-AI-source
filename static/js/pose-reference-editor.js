(function(){
    'use strict';

    const THREE_MODULE_URL = '/static/vendor/js/three-0.160.0.module.js';
    const EDITOR_VERSION = 1;
    const DEFAULT_BACKGROUND = '#171927';
    const DEFAULT_SELECTED_BONE = 'chest';
    const DEFAULT_CAMERA = {theta:0.12, phi:1.42, radius:3.05, target:[0,0.12,0]};
    const DEFAULT_SCENE = {
        background:DEFAULT_BACKGROUND,
        grid:true,
        shadows:true,
        keyIntensity:2.1,
        fillIntensity:0.75,
        modelColor:'#d3aa84'
    };
    const ASPECTS = ['1:1','16:9','9:16','4:3','3:4','3:2','2:3'];
    const RESOLUTIONS = [1024,1536,2048];

    const BONES = [
        {name:'root', label:'整体', parent:null, position:[0,0,0]},
        {name:'pelvis', label:'骨盆', parent:'root', position:[0,0,0], limits:{x:[-45,45],y:[-180,180],z:[-40,40]}},
        {name:'spine', label:'下脊柱', parent:'pelvis', position:[0,0.16,0], limits:{x:[-40,40],y:[-55,55],z:[-30,30]}},
        {name:'chest', label:'胸部', parent:'spine', position:[0,0.22,0], limits:{x:[-35,35],y:[-65,65],z:[-30,30]}},
        {name:'neck', label:'颈部', parent:'chest', position:[0,0.24,0], limits:{x:[-40,40],y:[-60,60],z:[-30,30]}},
        {name:'head', label:'头部', parent:'neck', position:[0,0.11,0], limits:{x:[-35,35],y:[-75,75],z:[-30,30]}},
        {name:'leftShoulder', label:'左肩', parent:'chest', position:[-0.18,0.10,0], limits:{x:[-45,45],y:[-45,45],z:[-35,35]}},
        {name:'leftUpperArm', label:'左上臂', parent:'leftShoulder', position:[-0.07,0,0], rotation:[0,0,-5], limits:{x:[-180,80],y:[-110,110],z:[-100,180]}},
        {name:'leftForeArm', label:'左前臂', parent:'leftUpperArm', position:[-0.28,0,0], limits:{x:[-5,150],y:[-85,85],z:[-20,20]}},
        {name:'leftHand', label:'左手', parent:'leftForeArm', position:[-0.24,0,0], limits:{x:[-75,75],y:[-45,45],z:[-75,75]}},
        {name:'rightShoulder', label:'右肩', parent:'chest', position:[0.18,0.10,0], limits:{x:[-45,45],y:[-45,45],z:[-35,35]}},
        {name:'rightUpperArm', label:'右上臂', parent:'rightShoulder', position:[0.07,0,0], rotation:[0,0,5], limits:{x:[-180,80],y:[-110,110],z:[-180,100]}},
        {name:'rightForeArm', label:'右前臂', parent:'rightUpperArm', position:[0.28,0,0], limits:{x:[-5,150],y:[-85,85],z:[-20,20]}},
        {name:'rightHand', label:'右手', parent:'rightForeArm', position:[0.24,0,0], limits:{x:[-75,75],y:[-45,45],z:[-75,75]}},
        {name:'leftHip', label:'左髋', parent:'pelvis', position:[-0.10,-0.02,0], limits:{x:[-35,35],y:[-45,45],z:[-35,35]}},
        {name:'leftThigh', label:'左大腿', parent:'leftHip', position:[0,-0.07,0], limits:{x:[-125,45],y:[-70,70],z:[-55,55]}},
        {name:'leftShin', label:'左小腿', parent:'leftThigh', position:[0,-0.34,0], limits:{x:[0,150],y:[-15,15],z:[-15,15]}},
        {name:'leftFoot', label:'左脚', parent:'leftShin', position:[0,-0.32,0], limits:{x:[-45,65],y:[-40,40],z:[-30,30]}},
        {name:'rightHip', label:'右髋', parent:'pelvis', position:[0.10,-0.02,0], limits:{x:[-35,35],y:[-45,45],z:[-35,35]}},
        {name:'rightThigh', label:'右大腿', parent:'rightHip', position:[0,-0.07,0], limits:{x:[-125,45],y:[-70,70],z:[-55,55]}},
        {name:'rightShin', label:'右小腿', parent:'rightThigh', position:[0,-0.34,0], limits:{x:[0,150],y:[-15,15],z:[-15,15]}},
        {name:'rightFoot', label:'右脚', parent:'rightShin', position:[0,-0.32,0], limits:{x:[-45,65],y:[-40,40],z:[-30,30]}}
    ];
    const BONE_MAP = new Map(BONES.map(bone => [bone.name, bone]));

    function pose(overrides={}){
        const rotations = {};
        BONES.forEach(bone => { rotations[bone.name] = [...(bone.rotation || [0,0,0])]; });
        Object.entries(overrides).forEach(([name, rotation]) => { if(BONE_MAP.has(name)) rotations[name] = [...rotation]; });
        return rotations;
    }

    const PRESETS = [
        {id:'stand', name:'自然站立', icon:'🧍', pose:{leftUpperArm:[0,0,-20],rightUpperArm:[0,0,20],leftForeArm:[10,0,0],rightForeArm:[10,0,0]}},
        {id:'catwalk', name:'走秀步', icon:'👠', pose:{pelvis:[0,8,3],spine:[-3,5,2],chest:[-2,3,1],head:[0,-8,0],leftThigh:[-35,5,3],rightThigh:[18,-3,-2],leftShin:[12,0,0],rightShin:[25,0,0],leftUpperArm:[15,0,-18],rightUpperArm:[-20,0,18],leftForeArm:[25,0,0],rightForeArm:[30,0,0]}},
        {id:'hand_hip', name:'单手叉腰', icon:'💁', pose:{pelvis:[0,0,8],spine:[0,0,5],neck:[0,15,-3],head:[0,20,-5],leftThigh:[0,0,12],rightThigh:[0,0,-8],leftUpperArm:[0,-30,-80],leftForeArm:[90,0,0],rightUpperArm:[0,0,22],rightForeArm:[15,0,0]}},
        {id:'both_hips', name:'双手叉腰', icon:'🦸', pose:{pelvis:[0,0,5],spine:[-3,0,3],chest:[-2,0,2],head:[-5,0,0],leftUpperArm:[0,-35,-85],leftForeArm:[95,0,0],rightUpperArm:[0,35,85],rightForeArm:[95,0,0],leftThigh:[0,0,10],rightThigh:[0,0,-10]}},
        {id:'s_curve', name:'S 型曲线', icon:'🌊', pose:{pelvis:[0,0,12],spine:[0,0,-8],chest:[0,0,6],neck:[0,10,-4],head:[0,15,-6],leftThigh:[0,0,15],rightThigh:[5,0,-5],leftShin:[8,0,0],leftUpperArm:[0,0,-22],rightUpperArm:[0,0,28],rightForeArm:[20,0,0]}},
        {id:'side_glance', name:'侧身回眸', icon:'✨', pose:{pelvis:[0,40,0],spine:[0,35,0],chest:[0,25,0],neck:[0,-30,5],head:[0,-35,8],leftThigh:[5,0,8],rightThigh:[-5,0,-5],leftUpperArm:[0,0,-20],rightUpperArm:[0,0,25]}},
        {id:'cross_legs', name:'交叉腿', icon:'🦋', pose:{pelvis:[0,0,10],spine:[0,0,6],chest:[0,0,4],neck:[0,20,-3],head:[0,25,-5],leftThigh:[0,-15,12],rightThigh:[0,15,-5],leftShin:[5,0,0],rightShin:[8,0,0],leftUpperArm:[0,0,-20],rightUpperArm:[0,0,25]}},
        {id:'arms_open', name:'展臂大片', icon:'🦅', pose:{spine:[-5,0,0],chest:[-3,0,0],neck:[-8,0,0],head:[-10,0,0],leftUpperArm:[0,0,10],rightUpperArm:[0,0,-10],leftForeArm:[15,0,0],rightForeArm:[15,0,0],leftThigh:[0,0,8],rightThigh:[0,0,-8]}},
        {id:'sit', name:'自然坐姿', icon:'🪑', pose:{pelvis:[-5,0,0],leftThigh:[-90,0,5],rightThigh:[-90,0,-5],leftShin:[90,0,0],rightShin:[90,0,0],leftUpperArm:[0,0,-25],rightUpperArm:[0,0,25]}},
        {id:'elegant_sit', name:'优雅坐姿', icon:'👑', pose:{pelvis:[-5,0,8],spine:[-5,0,5],chest:[-3,0,3],neck:[-3,15,-2],head:[-3,20,-3],leftThigh:[-88,0,12],rightThigh:[-88,0,-5],leftShin:[88,0,0],rightShin:[88,0,0],leftUpperArm:[0,-15,-50],leftForeArm:[85,0,0],rightUpperArm:[0,0,28]}},
        {id:'hug_knees', name:'抱膝坐', icon:'🧘', pose:{pelvis:[-20,0,0],spine:[25,0,0],chest:[15,0,0],neck:[10,0,0],head:[5,0,0],leftThigh:[-110,0,10],rightThigh:[-110,0,-10],leftShin:[120,0,0],rightShin:[120,0,0],leftUpperArm:[-30,20,-40],rightUpperArm:[-30,-20,40],leftForeArm:[110,0,0],rightForeArm:[110,0,0]}},
        {id:'half_squat', name:'半蹲', icon:'💎', pose:{pelvis:[-8,0,5],spine:[5,0,3],chest:[3,0,2],neck:[0,15,0],head:[0,20,0],leftThigh:[-45,0,10],rightThigh:[-30,0,-8],leftShin:[55,0,0],rightShin:[40,0,0],leftUpperArm:[0,-20,-60],leftForeArm:[80,0,0],rightUpperArm:[0,0,25]}},
        {id:'walk', name:'行走', icon:'🚶', pose:{spine:[5,0,0],leftThigh:[-30,0,0],rightThigh:[20,0,0],leftShin:[10,0,0],rightShin:[30,0,0],leftUpperArm:[20,0,-15],rightUpperArm:[-25,0,15],leftForeArm:[20,0,0],rightForeArm:[30,0,0]}},
        {id:'run', name:'奔跑', icon:'🏃', pose:{spine:[15,0,0],leftThigh:[-60,0,0],rightThigh:[40,0,0],leftShin:[20,0,0],rightShin:[80,0,0],leftUpperArm:[50,0,-20],rightUpperArm:[-60,0,20],leftForeArm:[80,0,0],rightForeArm:[60,0,0]}},
        {id:'raise_both', name:'双手举起', icon:'🙌', pose:{leftUpperArm:[-150,0,-30],rightUpperArm:[-150,0,30],leftForeArm:[10,0,0],rightForeArm:[10,0,0]}},
        {id:'wave', name:'挥手', icon:'👋', pose:{leftUpperArm:[-120,0,-30],leftForeArm:[30,0,0],rightUpperArm:[0,0,20],head:[0,-20,0]}},
        {id:'pray', name:'祈祷', icon:'🙏', pose:{spine:[10,0,0],neck:[15,0,0],head:[20,0,0],leftUpperArm:[-20,30,-40],rightUpperArm:[-20,-30,40],leftForeArm:[100,0,0],rightForeArm:[100,0,0]}},
        {id:'think', name:'思考', icon:'🤔', pose:{head:[5,15,5],neck:[5,10,0],leftUpperArm:[0,0,-20],rightUpperArm:[-30,20,30],rightForeArm:[100,0,0]}},
        {id:'point', name:'向前指', icon:'👉', pose:{spine:[5,10,0],rightUpperArm:[-80,20,20],rightForeArm:[10,0,0],leftUpperArm:[0,0,-20]}},
        {id:'cheer', name:'欢呼', icon:'🎉', pose:{head:[-10,0,0],leftUpperArm:[-130,-20,-40],rightUpperArm:[-130,20,40],leftForeArm:[20,0,0],rightForeArm:[20,0,0]}},
        {id:'fight', name:'格斗架', icon:'🥊', pose:{pelvis:[5,20,0],spine:[8,15,0],head:[0,-15,0],leftThigh:[-15,0,8],rightThigh:[10,0,-5],leftShin:[20,0,0],rightShin:[15,0,0],leftUpperArm:[-50,-20,-30],rightUpperArm:[-30,20,25],leftForeArm:[100,0,0],rightForeArm:[80,0,0]}},
        {id:'dance_a', name:'舞姿 A', icon:'💃', pose:{pelvis:[0,20,5],spine:[5,15,8],head:[-5,-20,10],leftUpperArm:[-100,-30,-50],rightUpperArm:[-60,40,60],leftForeArm:[30,0,0],rightForeArm:[50,0,0],leftThigh:[-20,0,10],rightThigh:[30,0,-5],rightShin:[40,0,0]}},
        {id:'kick', name:'踢腿', icon:'🦵', pose:{spine:[10,0,0],leftThigh:[-80,0,5],leftShin:[10,0,0],rightThigh:[10,0,-5],leftUpperArm:[30,0,-20],rightUpperArm:[-40,0,20],leftForeArm:[40,0,0],rightForeArm:[50,0,0]}},
        {id:'kneel', name:'跪姿', icon:'🧎', pose:{pelvis:[-10,0,0],leftThigh:[-100,0,5],rightThigh:[-100,0,-5],leftShin:[130,0,0],rightShin:[130,0,0],leftFoot:[-30,0,0],rightFoot:[-30,0,0]}},
        {id:'bow', name:'鞠躬', icon:'🙇', pose:{spine:[40,0,0],chest:[20,0,0],neck:[-20,0,0],leftUpperArm:[0,0,-15],rightUpperArm:[0,0,15]}},
        {id:'look_up', name:'仰望', icon:'🌟', pose:{spine:[-8,0,0],chest:[-5,0,0],neck:[-20,0,0],head:[-25,0,0],leftUpperArm:[0,0,-25],rightUpperArm:[0,0,25]}},
        {id:'tpose', name:'T-Pose', icon:'＋', pose:{}}
    ];

    function clamp(value, min, max){ return Math.max(min, Math.min(max, Number(value) || 0)); }
    function clone(value){ return JSON.parse(JSON.stringify(value)); }
    function esc(value){ return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }
    function normalizeTriplet(value, fallback=[0,0,0]){
        return [0,1,2].map(index => Number.isFinite(Number(value?.[index])) ? Number(value[index]) : Number(fallback[index] || 0));
    }
    function normalizeState(input={}){
        const raw = input && typeof input === 'object' ? input : {};
        const rotations = pose();
        BONES.forEach(bone => {
            const next = normalizeTriplet(raw.rotations?.[bone.name], rotations[bone.name]);
            rotations[bone.name] = next.map((value, axis) => {
                const limits = bone.limits?.[['x','y','z'][axis]] || [-180,180];
                return clamp(value, limits[0], limits[1]);
            });
        });
        const camera = raw.camera || {};
        const scene = raw.scene || {};
        return {
            version:EDITOR_VERSION,
            rotations,
            selectedBone:BONE_MAP.has(raw.selectedBone) ? raw.selectedBone : DEFAULT_SELECTED_BONE,
            camera:{
                theta:Number.isFinite(Number(camera.theta)) ? Number(camera.theta) : DEFAULT_CAMERA.theta,
                phi:clamp(Number.isFinite(Number(camera.phi)) ? camera.phi : DEFAULT_CAMERA.phi, 0.28, Math.PI - 0.28),
                radius:clamp(Number.isFinite(Number(camera.radius)) ? camera.radius : DEFAULT_CAMERA.radius, 1.5, 6),
                target:normalizeTriplet(camera.target, DEFAULT_CAMERA.target)
            },
            scene:{
                background:/^#[0-9a-f]{6}$/i.test(scene.background || '') ? scene.background : DEFAULT_SCENE.background,
                grid:scene.grid !== false,
                shadows:scene.shadows !== false,
                keyIntensity:clamp(Number.isFinite(Number(scene.keyIntensity)) ? scene.keyIntensity : DEFAULT_SCENE.keyIntensity, 0, 5),
                fillIntensity:clamp(Number.isFinite(Number(scene.fillIntensity)) ? scene.fillIntensity : DEFAULT_SCENE.fillIntensity, 0, 3),
                modelColor:/^#[0-9a-f]{6}$/i.test(scene.modelColor || '') ? scene.modelColor : DEFAULT_SCENE.modelColor
            },
            aspect:ASPECTS.includes(raw.aspect) ? raw.aspect : '1:1',
            resolution:RESOLUTIONS.includes(Number(raw.resolution)) ? Number(raw.resolution) : 1536
        };
    }
    function aspectNumber(value){
        const parts = String(value || '1:1').split(':').map(Number);
        return parts[0] > 0 && parts[1] > 0 ? parts[0] / parts[1] : 1;
    }
    function exportDimensions(state){
        const ratio = aspectNumber(state.aspect);
        const long = Number(state.resolution) || 1536;
        return ratio >= 1 ? [long, Math.max(256, Math.round(long / ratio))] : [Math.max(256, Math.round(long * ratio)), long];
    }
    function presetRotations(preset){ return pose(preset?.pose || {}); }
    function mirrorRotations(rotations){
        const result = pose();
        BONES.forEach(bone => {
            let source = bone.name;
            if(source.startsWith('left')) source = `right${source.slice(4)}`;
            else if(source.startsWith('right')) source = `left${source.slice(5)}`;
            const sourceRotation = rotations[source] || rotations[bone.name] || [0,0,0];
            result[bone.name] = [sourceRotation[0], -sourceRotation[1], -sourceRotation[2]];
        });
        return result;
    }
    function boneGroup(name){
        if(['root','pelvis','spine','chest','neck','head'].includes(name)) return '躯干与头部';
        if(name.startsWith('left')) return '左侧肢体';
        return '右侧肢体';
    }
    function boneButtonsHtml(selected){
        const groups = ['躯干与头部','左侧肢体','右侧肢体'];
        return groups.map(group => `<div class="pose-ref-bone-group"><div class="pose-ref-section-label">${group}</div><div class="pose-ref-bone-grid">${BONES.filter(bone => boneGroup(bone.name) === group).map(bone => `<button type="button" data-pose-bone="${bone.name}" class="${selected === bone.name ? 'active' : ''}">${esc(bone.label)}</button>`).join('')}</div></div>`).join('');
    }
    function presetsHtml(){
        return PRESETS.map(item => `<button type="button" class="pose-ref-preset" data-pose-preset="${item.id}"><span>${item.icon}</span><b>${esc(item.name)}</b></button>`).join('');
    }
    function editorHtml(state, theme){
        const selected = BONE_MAP.get(state.selectedBone) || BONE_MAP.get(DEFAULT_SELECTED_BONE);
        return `<div class="pose-ref-editor" data-theme="${theme === 'light' ? 'light' : 'dark'}" role="dialog" aria-modal="true" aria-label="姿势参考编辑器">
            <header class="pose-ref-editor-head">
                <div class="pose-ref-editor-brand"><span class="pose-ref-brand-icon"><i data-lucide="person-standing"></i></span><div><strong>姿势参考编辑器</strong><small>3D 人形 · 关节微调 · 高清导出</small></div></div>
                <div class="pose-ref-head-actions">
                    <button type="button" data-pose-action="mirror" title="左右镜像"><i data-lucide="flip-horizontal-2"></i><span>镜像</span></button>
                    <button type="button" data-pose-action="reset" title="恢复自然站立"><i data-lucide="rotate-ccw"></i><span>复位</span></button>
                    <button type="button" class="pose-ref-close" data-pose-action="close" title="关闭"><i data-lucide="x"></i></button>
                </div>
            </header>
            <div class="pose-ref-editor-layout">
                <aside class="pose-ref-sidebar pose-ref-presets-panel">
                    <div class="pose-ref-panel-head"><div><strong>动作预设</strong><small>选择后仍可逐关节微调</small></div></div>
                    <div class="pose-ref-preset-list">${presetsHtml()}</div>
                </aside>
                <main class="pose-ref-stage-column">
                    <div class="pose-ref-stage-shell" data-pose-stage-shell style="--pose-aspect:${aspectNumber(state.aspect)}">
                        <div class="pose-ref-stage" data-pose-stage></div>
                        <div class="pose-ref-stage-help"><span><i data-lucide="mouse-pointer-2"></i> 点击选关节</span><span>拖动旋转视角</span><span>滚轮缩放</span></div>
                        <div class="pose-ref-stage-badge" data-pose-selected-badge>${esc(selected.label)}</div>
                        <div class="pose-ref-loading" data-pose-loading><span></span><b>正在载入 3D 编辑器…</b></div>
                    </div>
                    <div class="pose-ref-view-toolbar">
                        <button type="button" data-pose-view="front">正面</button><button type="button" data-pose-view="side">侧面</button><button type="button" data-pose-view="back">背面</button><button type="button" data-pose-view="three-quarter">3/4</button>
                        <span></span>
                        <button type="button" data-pose-action="frame"><i data-lucide="scan"></i>适配人物</button>
                    </div>
                </main>
                <aside class="pose-ref-sidebar pose-ref-controls-panel">
                    <div class="pose-ref-panel-head"><div><strong>关节控制</strong><small data-pose-selected-label>${esc(selected.label)}</small></div></div>
                    <div class="pose-ref-bones" data-pose-bones>${boneButtonsHtml(state.selectedBone)}</div>
                    <div class="pose-ref-axis-controls">
                        ${['x','y','z'].map((axis,index) => `<label data-pose-axis-row="${axis}"><span><i>${axis.toUpperCase()}</i><b>${index === 0 ? '前后' : index === 1 ? '扭转' : '侧摆'}</b></span><input type="range" data-pose-axis="${axis}" value="${state.rotations[state.selectedBone][index]}"><output data-pose-axis-output="${axis}">${Math.round(state.rotations[state.selectedBone][index])}°</output></label>`).join('')}
                    </div>
                    <details class="pose-ref-scene" open>
                        <summary>画面与灯光</summary>
                        <div class="pose-ref-scene-grid">
                            <label><span>画幅</span><select data-pose-setting="aspect">${ASPECTS.map(value => `<option value="${value}" ${state.aspect === value ? 'selected' : ''}>${value}</option>`).join('')}</select></label>
                            <label><span>长边像素</span><select data-pose-setting="resolution">${RESOLUTIONS.map(value => `<option value="${value}" ${state.resolution === value ? 'selected' : ''}>${value}px</option>`).join('')}</select></label>
                            <label><span>背景</span><input type="color" data-pose-setting="background" value="${state.scene.background}"></label>
                            <label><span>人形颜色</span><input type="color" data-pose-setting="modelColor" value="${state.scene.modelColor}"></label>
                            <label class="pose-ref-wide"><span>主光 <output data-pose-light-output="key">${state.scene.keyIntensity.toFixed(1)}</output></span><input type="range" min="0" max="5" step="0.1" data-pose-setting="keyIntensity" value="${state.scene.keyIntensity}"></label>
                            <label class="pose-ref-wide"><span>补光 <output data-pose-light-output="fill">${state.scene.fillIntensity.toFixed(1)}</output></span><input type="range" min="0" max="3" step="0.05" data-pose-setting="fillIntensity" value="${state.scene.fillIntensity}"></label>
                        </div>
                        <div class="pose-ref-switches"><label><input type="checkbox" data-pose-setting="grid" ${state.scene.grid ? 'checked' : ''}><span>地面网格</span></label><label><input type="checkbox" data-pose-setting="shadows" ${state.scene.shadows ? 'checked' : ''}><span>实时阴影</span></label></div>
                    </details>
                </aside>
            </div>
            <footer class="pose-ref-editor-foot">
                <div class="pose-ref-export-status" data-pose-status><i data-lucide="info"></i><span>姿势参数会随画布自动保存</span></div>
                <div><button type="button" data-pose-action="save-close">保存并关闭</button><button type="button" class="pose-ref-primary" data-pose-action="export"><i data-lucide="camera"></i><span>导出姿势参考图</span></button></div>
            </footer>
        </div>`;
    }

    function nodeBodyHtml(node, output){
        const item = output?.url ? output : null;
        return `<div class="special-node pose-reference-special" data-special-node="pose-reference">
            <div class="pose-reference-preview ${item ? 'has-output' : ''}">
                ${item ? `<img src="${esc(item.url)}" alt="姿势参考图" draggable="false">` : `<div class="special-empty"><i data-lucide="person-standing"></i><strong>创建 3D 姿势</strong><span>预设动作 · 关节微调 · 自由镜头</span></div>`}
                <button type="button" class="pose-reference-edit" data-special-action="edit-pose-reference"><i data-lucide="pencil-ruler"></i><span>${item ? '编辑动作' : '开始编辑'}</span></button>
            </div>
            <div class="pose-reference-meta"><span><i data-lucide="box"></i>${node.poseEditorState?.selectedBone ? '可继续编辑' : '尚未设置姿势'}</span><b>${esc(node.poseEditorState?.aspect || '1:1')} · ${Number(node.poseEditorState?.resolution) || 1536}px</b></div>
            <div class="special-output-row"><span>${item ? `姿势参考图已就绪 · ${esc(item.name || 'pose-reference.png')}` : '导出后可直接连接图片/视频生成节点'}</span>${item ? '<i data-lucide="check-circle-2"></i>' : ''}</div>
        </div>`;
    }

    let activeEditor = null;
    let threePromise = null;
    function loadThree(){
        if(!threePromise) threePromise = import(THREE_MODULE_URL);
        return threePromise;
    }
    function iconRefresh(root){ try { window.lucide?.createIcons({nodes:root ? [root] : undefined}); } catch(_){} }

    function open(options={}){
        activeEditor?.close?.({save:true});
        const state = normalizeState(options.state || {});
        const overlay = document.createElement('div');
        overlay.className = 'pose-ref-editor-overlay';
        overlay.innerHTML = editorHtml(state, options.theme || document.documentElement.dataset.theme || 'dark');
        document.body.appendChild(overlay);
        document.body.classList.add('pose-ref-editor-open');
        iconRefresh(overlay);

        const editor = overlay.firstElementChild;
        const stage = editor.querySelector('[data-pose-stage]');
        const shell = editor.querySelector('[data-pose-stage-shell]');
        const loading = editor.querySelector('[data-pose-loading]');
        const status = editor.querySelector('[data-pose-status] span');
        const exportButton = editor.querySelector('[data-pose-action="export"]');
        const disposers = [];
        let closed = false;
        let runtime = null;
        let saveTimer = 0;

        function setStatus(message, error=false){
            if(status) status.textContent = String(message || '');
            editor.querySelector('[data-pose-status]')?.classList.toggle('error', Boolean(error));
        }
        function scheduleStateSave(){
            clearTimeout(saveTimer);
            saveTimer = setTimeout(() => { if(!closed) options.onSave?.(clone(state)); }, 180);
        }
        function updateStageAspect(){ shell.style.setProperty('--pose-aspect', String(aspectNumber(state.aspect))); runtime?.resize?.(); }
        function axisIndex(axis){ return axis === 'x' ? 0 : axis === 'y' ? 1 : 2; }
        function updateJointControls(){
            const bone = BONE_MAP.get(state.selectedBone) || BONE_MAP.get(DEFAULT_SELECTED_BONE);
            state.selectedBone = bone.name;
            editor.querySelector('[data-pose-selected-label]').textContent = bone.label;
            editor.querySelector('[data-pose-selected-badge]').textContent = bone.label;
            editor.querySelectorAll('[data-pose-bone]').forEach(button => button.classList.toggle('active', button.dataset.poseBone === bone.name));
            ['x','y','z'].forEach((axis,index) => {
                const input = editor.querySelector(`[data-pose-axis="${axis}"]`);
                const limits = bone.limits?.[axis] || [-180,180];
                input.min = String(limits[0]); input.max = String(limits[1]); input.step = '1'; input.value = String(state.rotations[bone.name][index]);
                editor.querySelector(`[data-pose-axis-output="${axis}"]`).textContent = `${Math.round(state.rotations[bone.name][index])}°`;
            });
            runtime?.selectBone?.(bone.name);
        }
        function selectBone(name){
            if(!BONE_MAP.has(name)) return;
            state.selectedBone = name;
            updateJointControls();
            scheduleStateSave();
        }
        function applyRotations(rotations){
            state.rotations = normalizeState({...state, rotations}).rotations;
            runtime?.applyPose?.();
            updateJointControls();
            scheduleStateSave();
        }
        function close({save=true}={}){
            if(closed) return;
            closed = true;
            clearTimeout(saveTimer);
            if(save) options.onSave?.(clone(state));
            runtime?.dispose?.();
            disposers.splice(0).forEach(dispose => { try { dispose(); } catch(_){} });
            overlay.remove();
            document.body.classList.remove('pose-ref-editor-open');
            if(activeEditor?.overlay === overlay) activeEditor = null;
            options.onClose?.();
        }
        activeEditor = {overlay, close};

        editor.querySelectorAll('[data-pose-bone]').forEach(button => button.addEventListener('click', () => selectBone(button.dataset.poseBone)));
        editor.querySelectorAll('[data-pose-axis]').forEach(input => input.addEventListener('input', () => {
            const axis = input.dataset.poseAxis;
            const index = axisIndex(axis);
            state.rotations[state.selectedBone][index] = Number(input.value);
            editor.querySelector(`[data-pose-axis-output="${axis}"]`).textContent = `${Math.round(Number(input.value))}°`;
            runtime?.applyPose?.(); scheduleStateSave();
        }));
        editor.querySelectorAll('[data-pose-preset]').forEach(button => button.addEventListener('click', () => {
            const selected = PRESETS.find(item => item.id === button.dataset.posePreset);
            if(!selected) return;
            editor.querySelectorAll('[data-pose-preset]').forEach(item => item.classList.toggle('active', item === button));
            applyRotations(presetRotations(selected));
            setStatus(`已应用“${selected.name}”，可继续微调关节`);
        }));
        editor.querySelectorAll('[data-pose-setting]').forEach(control => control.addEventListener(control.type === 'range' || control.type === 'color' ? 'input' : 'change', () => {
            const key = control.dataset.poseSetting;
            if(key === 'aspect'){ state.aspect = ASPECTS.includes(control.value) ? control.value : '1:1'; updateStageAspect(); }
            else if(key === 'resolution') state.resolution = Number(control.value);
            else if(key === 'grid' || key === 'shadows') state.scene[key] = control.checked;
            else if(key === 'keyIntensity' || key === 'fillIntensity') state.scene[key] = Number(control.value);
            else state.scene[key] = control.value;
            if(key === 'keyIntensity') editor.querySelector('[data-pose-light-output="key"]').textContent = Number(control.value).toFixed(1);
            if(key === 'fillIntensity') editor.querySelector('[data-pose-light-output="fill"]').textContent = Number(control.value).toFixed(1);
            runtime?.applyScene?.(); scheduleStateSave();
        }));
        editor.querySelectorAll('[data-pose-view]').forEach(button => button.addEventListener('click', () => runtime?.setView?.(button.dataset.poseView)));
        editor.querySelector('[data-pose-action="mirror"]').addEventListener('click', () => { applyRotations(mirrorRotations(state.rotations)); setStatus('姿势已左右镜像'); });
        editor.querySelector('[data-pose-action="reset"]').addEventListener('click', () => { applyRotations(presetRotations(PRESETS[0])); runtime?.setView?.('front'); setStatus('已恢复自然站立'); });
        editor.querySelector('[data-pose-action="frame"]').addEventListener('click', () => runtime?.frame?.());
        editor.querySelector('[data-pose-action="close"]').addEventListener('click', () => close({save:true}));
        editor.querySelector('[data-pose-action="save-close"]').addEventListener('click', () => close({save:true}));
        overlay.addEventListener('mousedown', event => { if(event.target === overlay) close({save:true}); });
        editor.addEventListener('mousedown', event => event.stopPropagation());
        editor.addEventListener('wheel', event => event.stopPropagation(), {passive:true});
        const onKeyDown = event => {
            if(event.key === 'Escape'){ event.preventDefault(); close({save:true}); }
            if((event.key === 'Delete' || event.key === 'Backspace') && !event.target.matches('input,textarea,select')){
                event.preventDefault(); const defaults = pose(); state.rotations[state.selectedBone] = [...defaults[state.selectedBone]]; runtime?.applyPose?.(); updateJointControls(); scheduleStateSave();
            }
        };
        document.addEventListener('keydown', onKeyDown, true);
        disposers.push(() => document.removeEventListener('keydown', onKeyDown, true));

        exportButton.addEventListener('click', async () => {
            if(!runtime?.exportBlob || exportButton.disabled) return;
            exportButton.disabled = true;
            exportButton.classList.add('loading');
            setStatus('正在渲染高清姿势参考图…');
            try {
                const [width,height] = exportDimensions(state);
                const blob = await runtime.exportBlob(width, height);
                if(!blob) throw new Error('浏览器没有生成图片数据');
                options.onSave?.(clone(state));
                await options.onExport?.(blob, clone(state), {width,height, name:`pose-reference-${width}x${height}.png`});
                setStatus(`已导出 ${width}×${height} 姿势参考图`);
                if(options.closeAfterExport !== false) close({save:true});
            } catch(error){ setStatus(error?.message || '姿势参考图导出失败', true); }
            finally { exportButton.disabled = false; exportButton.classList.remove('loading'); }
        });

        loadThree().then(THREE => {
            if(closed) return;
            runtime = createThreeRuntime(THREE, stage, state, {
                onSelectBone:selectBone,
                onCameraChange:() => scheduleStateSave()
            });
            loading?.remove();
            updateJointControls();
            updateStageAspect();
        }).catch(error => {
            loading?.classList.add('failed');
            const label = loading?.querySelector('b'); if(label) label.textContent = '3D 编辑器载入失败';
            setStatus(error?.message || 'Three.js 载入失败', true);
        });
        return activeEditor;
    }

    function createThreeRuntime(THREE, container, state, callbacks={}){
        const scene = new THREE.Scene();
        const renderer = new THREE.WebGLRenderer({antialias:true, alpha:false, preserveDrawingBuffer:true});
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.05;
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
        renderer.domElement.className = 'pose-ref-webgl';
        container.appendChild(renderer.domElement);

        const camera = new THREE.PerspectiveCamera(34, 1, 0.01, 100);
        const ambient = new THREE.HemisphereLight(0xe6edff, 0x352b2a, state.scene.fillIntensity);
        const key = new THREE.DirectionalLight(0xfff4e4, state.scene.keyIntensity);
        key.position.set(2.8,3.8,3.2); key.castShadow = true;
        key.shadow.mapSize.set(2048,2048); key.shadow.camera.left = -2; key.shadow.camera.right = 2; key.shadow.camera.top = 2; key.shadow.camera.bottom = -2;
        const rim = new THREE.DirectionalLight(0xaeb9ff, 0.6); rim.position.set(-2,2,-2.5);
        scene.add(ambient,key,rim);

        const groundMaterial = new THREE.MeshStandardMaterial({color:0x202231, roughness:0.92, metalness:0});
        const ground = new THREE.Mesh(new THREE.PlaneGeometry(12,12), groundMaterial);
        ground.rotation.x = -Math.PI / 2; ground.position.y = -0.91; ground.receiveShadow = true; scene.add(ground);
        const grid = new THREE.GridHelper(10,40,0x6972a8,0x34384f);
        grid.position.y = -0.905; grid.material.transparent = true; grid.material.opacity = 0.34; scene.add(grid);

        const figure = new THREE.Group();
        figure.position.y = -0.02;
        scene.add(figure);
        const boneGroups = new Map();
        const boneMeshes = new Map();
        const selectableMeshes = [];
        const materials = new Map();
        const degrees = Math.PI / 180;

        function materialFor(name){
            const material = new THREE.MeshStandardMaterial({color:state.scene.modelColor, roughness:0.48, metalness:0.02});
            materials.set(name, material); return material;
        }
        function registerMesh(name, mesh){
            mesh.userData.boneName = name; mesh.castShadow = true; mesh.receiveShadow = true;
            if(!boneMeshes.has(name)) boneMeshes.set(name, []);
            boneMeshes.get(name).push(mesh); selectableMeshes.push(mesh); return mesh;
        }
        function segment(name, group, vector, radius, taper=0.82){
            const direction = new THREE.Vector3(...vector);
            const length = direction.length();
            const geometry = new THREE.CylinderGeometry(radius * taper, radius, length, 18, 2, false);
            const mesh = registerMesh(name, new THREE.Mesh(geometry, materialFor(name)));
            mesh.position.copy(direction).multiplyScalar(0.5);
            mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0), direction.clone().normalize());
            group.add(mesh);
            const joint = registerMesh(name, new THREE.Mesh(new THREE.SphereGeometry(radius * 1.02,18,12), mesh.material));
            joint.position.copy(direction); group.add(joint);
        }
        function bodyMesh(name, group, geometry, position=[0,0,0], scale=[1,1,1]){
            const mesh = registerMesh(name, new THREE.Mesh(geometry, materialFor(name)));
            mesh.position.set(...position); mesh.scale.set(...scale); group.add(mesh); return mesh;
        }
        BONES.forEach(bone => {
            const group = new THREE.Group();
            group.name = bone.name; group.position.set(...bone.position);
            (bone.parent ? boneGroups.get(bone.parent) : figure).add(group);
            boneGroups.set(bone.name, group);
        });
        bodyMesh('pelvis', boneGroups.get('pelvis'), new THREE.SphereGeometry(0.16,24,16), [0,0.04,0], [1.05,0.72,0.72]);
        bodyMesh('spine', boneGroups.get('spine'), new THREE.SphereGeometry(0.15,24,16), [0,0.10,0], [0.86,1.0,0.62]);
        bodyMesh('chest', boneGroups.get('chest'), new THREE.SphereGeometry(0.19,24,16), [0,0.10,0], [1.12,1.05,0.65]);
        segment('neck', boneGroups.get('neck'), [0,0.11,0], 0.065, 0.9);
        const head = bodyMesh('head', boneGroups.get('head'), new THREE.SphereGeometry(0.115,28,20), [0,0.10,0], [0.82,1.08,0.88]);
        const nose = new THREE.Mesh(new THREE.ConeGeometry(0.022,0.065,12), new THREE.MeshStandardMaterial({color:state.scene.modelColor,roughness:0.5}));
        nose.rotation.x = Math.PI / 2; nose.position.set(0,0.105,0.112); nose.castShadow = true; head.parent.add(nose);
        ['leftShoulder','rightShoulder','leftHip','rightHip'].forEach(name => bodyMesh(name, boneGroups.get(name), new THREE.SphereGeometry(0.065,18,12)));
        segment('leftUpperArm', boneGroups.get('leftUpperArm'), [-0.28,0,0], 0.058);
        segment('leftForeArm', boneGroups.get('leftForeArm'), [-0.24,0,0], 0.049);
        segment('rightUpperArm', boneGroups.get('rightUpperArm'), [0.28,0,0], 0.058);
        segment('rightForeArm', boneGroups.get('rightForeArm'), [0.24,0,0], 0.049);
        bodyMesh('leftHand', boneGroups.get('leftHand'), new THREE.BoxGeometry(0.12,0.065,0.045), [-0.06,0,0]);
        bodyMesh('rightHand', boneGroups.get('rightHand'), new THREE.BoxGeometry(0.12,0.065,0.045), [0.06,0,0]);
        segment('leftThigh', boneGroups.get('leftThigh'), [0,-0.34,0], 0.075);
        segment('leftShin', boneGroups.get('leftShin'), [0,-0.32,0], 0.059);
        segment('rightThigh', boneGroups.get('rightThigh'), [0,-0.34,0], 0.075);
        segment('rightShin', boneGroups.get('rightShin'), [0,-0.32,0], 0.059);
        bodyMesh('leftFoot', boneGroups.get('leftFoot'), new THREE.BoxGeometry(0.105,0.07,0.24), [0,-0.025,0.075]);
        bodyMesh('rightFoot', boneGroups.get('rightFoot'), new THREE.BoxGeometry(0.105,0.07,0.24), [0,-0.025,0.075]);

        function applyPose(){
            BONES.forEach(bone => {
                const rotation = state.rotations[bone.name] || [0,0,0];
                boneGroups.get(bone.name)?.rotation.set(rotation[0] * degrees, rotation[1] * degrees, rotation[2] * degrees, 'XYZ');
            });
        }
        function selectBone(name){
            materials.forEach((material, boneName) => {
                material.color.set(state.scene.modelColor);
                material.emissive.set(boneName === name ? 0x5d3a00 : 0x000000);
                material.emissiveIntensity = boneName === name ? 0.7 : 0;
            });
        }
        function updateCamera(){
            const {theta,phi,radius,target} = state.camera;
            const sinPhi = Math.sin(phi);
            camera.position.set(target[0] + radius * sinPhi * Math.sin(theta), target[1] + radius * Math.cos(phi), target[2] + radius * sinPhi * Math.cos(theta));
            camera.lookAt(...target);
        }
        function applyScene(){
            scene.background = new THREE.Color(state.scene.background);
            groundMaterial.color.set(state.scene.background).offsetHSL(0,0,-0.035);
            grid.visible = state.scene.grid;
            renderer.shadowMap.enabled = state.scene.shadows;
            key.castShadow = state.scene.shadows;
            key.intensity = state.scene.keyIntensity;
            ambient.intensity = state.scene.fillIntensity;
            materials.forEach((material, name) => {
                material.color.set(state.scene.modelColor);
                material.emissive.set(name === state.selectedBone ? 0x5d3a00 : 0x000000);
                material.needsUpdate = true;
            });
            nose.material.color.set(state.scene.modelColor);
        }
        function frame(){ state.camera.radius = 3.05; state.camera.target = [0,0.1,0]; updateCamera(); callbacks.onCameraChange?.(); }
        function setView(view){
            state.camera.theta = view === 'side' ? Math.PI / 2 : view === 'back' ? Math.PI : view === 'three-quarter' ? Math.PI / 4 : 0;
            state.camera.phi = 1.42; frame();
        }
        function resize(){
            const rect = container.getBoundingClientRect();
            const width = Math.max(1,Math.round(rect.width)); const height = Math.max(1,Math.round(rect.height));
            renderer.setSize(width,height,false); camera.aspect = width / height; camera.updateProjectionMatrix();
        }
        const resizeObserver = new ResizeObserver(resize); resizeObserver.observe(container);
        resize(); applyPose(); applyScene(); selectBone(state.selectedBone); updateCamera();

        const raycaster = new THREE.Raycaster();
        const pointer = new THREE.Vector2();
        let drag = null;
        function pointerPoint(event){ const rect = renderer.domElement.getBoundingClientRect(); return {x:event.clientX - rect.left,y:event.clientY - rect.top,width:rect.width,height:rect.height}; }
        function onPointerDown(event){
            if(event.button !== 0 && event.button !== 1 && event.button !== 2) return;
            event.preventDefault(); event.stopPropagation(); renderer.domElement.setPointerCapture?.(event.pointerId);
            drag = {id:event.pointerId,x:event.clientX,y:event.clientY,theta:state.camera.theta,phi:state.camera.phi,target:[...state.camera.target],moved:false,pan:event.shiftKey || event.button === 1};
        }
        function onPointerMove(event){
            if(!drag || drag.id !== event.pointerId) return;
            event.preventDefault(); event.stopPropagation();
            const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
            if(Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
            if(drag.pan){ state.camera.target[0] = drag.target[0] - dx * 0.0025; state.camera.target[1] = drag.target[1] + dy * 0.0025; }
            else { state.camera.theta = drag.theta - dx * 0.008; state.camera.phi = clamp(drag.phi + dy * 0.008,0.28,Math.PI - 0.28); }
            updateCamera();
        }
        function onPointerUp(event){
            if(!drag || drag.id !== event.pointerId) return;
            event.preventDefault(); event.stopPropagation(); renderer.domElement.releasePointerCapture?.(event.pointerId);
            const wasMoved = drag.moved; drag = null; callbacks.onCameraChange?.();
            if(wasMoved || event.button !== 0) return;
            const point = pointerPoint(event); pointer.set((point.x / point.width) * 2 - 1, -(point.y / point.height) * 2 + 1);
            raycaster.setFromCamera(pointer,camera); const hit = raycaster.intersectObjects(selectableMeshes,false)[0];
            if(hit?.object?.userData?.boneName) callbacks.onSelectBone?.(hit.object.userData.boneName);
        }
        function onWheel(event){ event.preventDefault(); event.stopPropagation(); state.camera.radius = clamp(state.camera.radius * Math.exp(event.deltaY * 0.001),1.5,6); updateCamera(); callbacks.onCameraChange?.(); }
        function onContextMenu(event){ event.preventDefault(); }
        renderer.domElement.addEventListener('pointerdown',onPointerDown);
        renderer.domElement.addEventListener('pointermove',onPointerMove);
        renderer.domElement.addEventListener('pointerup',onPointerUp);
        renderer.domElement.addEventListener('pointercancel',onPointerUp);
        renderer.domElement.addEventListener('wheel',onWheel,{passive:false});
        renderer.domElement.addEventListener('contextmenu',onContextMenu);

        let frameId = 0, disposed = false;
        function animate(){ if(disposed) return; frameId = requestAnimationFrame(animate); renderer.render(scene,camera); }
        animate();
        async function exportBlob(width,height){
            const previousSize = new THREE.Vector2(); renderer.getSize(previousSize); const previousRatio = renderer.getPixelRatio();
            renderer.setPixelRatio(1); renderer.setSize(width,height,false); camera.aspect = width / height; camera.updateProjectionMatrix(); renderer.render(scene,camera);
            const blob = await new Promise(resolve => renderer.domElement.toBlob(resolve,'image/png',1));
            renderer.setPixelRatio(previousRatio); renderer.setSize(previousSize.x,previousSize.y,false); camera.aspect = previousSize.x / Math.max(1,previousSize.y); camera.updateProjectionMatrix();
            return blob;
        }
        function dispose(){
            disposed = true; cancelAnimationFrame(frameId); resizeObserver.disconnect();
            renderer.domElement.removeEventListener('pointerdown',onPointerDown); renderer.domElement.removeEventListener('pointermove',onPointerMove); renderer.domElement.removeEventListener('pointerup',onPointerUp); renderer.domElement.removeEventListener('pointercancel',onPointerUp); renderer.domElement.removeEventListener('wheel',onWheel); renderer.domElement.removeEventListener('contextmenu',onContextMenu);
            scene.traverse(object => { object.geometry?.dispose?.(); if(Array.isArray(object.material)) object.material.forEach(material => material?.dispose?.()); else object.material?.dispose?.(); });
            renderer.dispose(); renderer.forceContextLoss?.(); renderer.domElement.remove();
        }
        return {applyPose,selectBone,applyScene,resize,frame,setView,exportBlob,dispose};
    }

    window.PoseReferenceEditor = {
        BONES, PRESETS, ASPECTS, RESOLUTIONS,
        normalizeState, exportDimensions, nodeBodyHtml, open,
        close(){ activeEditor?.close?.({save:true}); }
    };
})();
