(function(){
    'use strict';

    const MODES = Object.freeze({PERSON:'person', BUILDING:'building'});
    const PERSON_INPUT_SLOTS = Object.freeze([
        ['model-front','模特正面','image'], ['model-side','模特侧面','image'], ['model-back','模特背面','image'],
        ['product-upper-front','上装正面','image'], ['product-upper-side','上装侧面','image'], ['product-upper-back','上装背面','image'],
        ['product-lower-front','下装正面','image'], ['product-lower-side','下装侧面','image'], ['product-lower-back','下装背面','image'],
        ['front-detail','正面细节','image'], ['back-detail','背面细节','image'], ['accessory','配饰','image']
    ]);
    const BUILDING_INPUT_SLOTS = Object.freeze([
        ['building-sketch','线稿图','image'],
        ['building-front','建筑正面','image'],
        ['building-side','建筑侧视图','image'],
        ['building-back','建筑背视图','image'],
        ['building-top','建筑顶视图','image'],
        ['building-prompt','提示词','prompt']
    ]);
    const BUILDING_OUTPUT_SLOTS = Object.freeze([
        ['sketch','线稿图'],
        ['front','建筑正面'],
        ['side','建筑侧视图'],
        ['back','建筑背视图'],
        ['top','建筑顶视图']
    ]);
    const BUILDING_STAGES = Object.freeze({
        IDLE:'idle',
        PLANNING:'planning',
        SKETCH_GENERATING:'sketch-generating',
        AWAITING_SKETCH:'awaiting-sketch-confirmation',
        FRONT_GENERATING:'front-generating',
        AWAITING_FRONT:'awaiting-front-confirmation',
        VIEWS_GENERATING:'views-generating',
        DONE:'done',
        PARTIAL:'partial',
        ERROR:'error'
    });
    const BUSY_STAGES = new Set([
        BUILDING_STAGES.PLANNING,
        BUILDING_STAGES.SKETCH_GENERATING,
        BUILDING_STAGES.FRONT_GENERATING,
        BUILDING_STAGES.VIEWS_GENERATING
    ]);
    const ALL_INPUT_SLOTS = Object.freeze([...PERSON_INPUT_SLOTS, ...BUILDING_INPUT_SLOTS]);

    function mode(node){
        return node?.multiViewMode === MODES.BUILDING ? MODES.BUILDING : MODES.PERSON;
    }
    function normalizeNode(node){
        if(!node) return node;
        node.multiViewMode = mode(node);
        if(typeof node.buildingPrompt !== 'string') node.buildingPrompt = '';
        if(!Object.values(BUILDING_STAGES).includes(node.buildingStage)) node.buildingStage = BUILDING_STAGES.IDLE;
        if(!Array.isArray(node.multiViewOutputs)) node.multiViewOutputs = node.multiViewMode === MODES.PERSON && Array.isArray(node.generatedOutputs) ? [...node.generatedOutputs] : [];
        if(!Array.isArray(node.buildingOutputs)) node.buildingOutputs = [];
        if(!Array.isArray(node.buildingPendingTasks)) node.buildingPendingTasks = [];
        if(!node.buildingPlan || typeof node.buildingPlan !== 'object' || Array.isArray(node.buildingPlan)) node.buildingPlan = null;
        if(!node.buildingErrors || typeof node.buildingErrors !== 'object' || Array.isArray(node.buildingErrors)) node.buildingErrors = {};
        if(typeof node.buildingInputSignature !== 'string') node.buildingInputSignature = '';
        return node;
    }
    function inputSlots(nodeOrMode){
        const value = typeof nodeOrMode === 'string' ? nodeOrMode : mode(nodeOrMode);
        return value === MODES.BUILDING ? BUILDING_INPUT_SLOTS : PERSON_INPUT_SLOTS;
    }
    function outputSlots(nodeOrMode){
        const value = typeof nodeOrMode === 'string' ? nodeOrMode : mode(nodeOrMode);
        return value === MODES.BUILDING ? BUILDING_OUTPUT_SLOTS : [];
    }
    function roleDefinition(role){
        return ALL_INPUT_SLOTS.find(item => item[0] === role) || null;
    }
    function roleKind(role){
        return roleDefinition(role)?.[2] || '';
    }
    function isRoleActive(node, role){
        return inputSlots(node).some(item => item[0] === role);
    }
    function isBusy(node){
        return node?.multiViewStatus === 'running' || BUSY_STAGES.has(node?.buildingStage);
    }
    function setMode(node, nextMode){
        normalizeNode(node);
        if(isBusy(node)) return false;
        const normalized = nextMode === MODES.BUILDING ? MODES.BUILDING : MODES.PERSON;
        if(node.multiViewMode === normalized) return false;
        node.multiViewMode = normalized;
        node.generatedOutputs = normalized === MODES.BUILDING ? [...node.buildingOutputs] : [...node.multiViewOutputs];
        node.multiViewError = '';
        return true;
    }
    function groupLabel(role){
        if(role === 'building-sketch') return '设计锚点';
        if(role === 'building-prompt') return '文字需求';
        if(role.startsWith('building-')) return '实景视图';
        if(role.startsWith('model-')) return '模特主体';
        if(role.startsWith('product-upper-')) return '上装';
        if(role.startsWith('product-lower-')) return '下装';
        return '细节与配饰';
    }

    const BUILDING_VIEW_CAMERAS = Object.freeze({
        front:'Straight-on front elevation from eye level, camera centered on the primary facade, level verticals, restrained perspective and the complete building visible from foundation to roofline.',
        side:'Strict right-side elevation from eye level, camera perpendicular to the side facade, level verticals, restrained perspective and the complete building visible from foundation to roofline.',
        back:'Straight-on rear elevation from eye level, camera centered on the rear facade, level verticals, restrained perspective and the complete building visible from foundation to roofline.',
        top:'True overhead roof view, camera directly above the building looking vertically downward, showing the complete roof geometry, equipment, drainage and immediate site boundary.'
    });

    function compactPromptValue(value){
        const text = Array.isArray(value) ? value.filter(Boolean).join('; ') : String(value || '');
        return text.replace(/\s+/g, ' ').trim();
    }
    function buildingIdentity(plan={}){
        const fields = [
            ['type', plan.building_type], ['style and era', plan.style_and_era], ['massing', plan.massing],
            ['storeys', plan.storeys], ['roof', plan.roof], ['facade and openings', plan.fenestration],
            ['materials', plan.materials], ['structure', plan.structure], ['exterior equipment', plan.equipment],
            ['weathering', plan.weathering], ['site', plan.environment], ['lighting', plan.lighting], ['palette', plan.palette]
        ];
        const specification = fields.map(([label, value]) => {
            const text = compactPromptValue(value);
            return text ? `${label}: ${text}` : '';
        }).filter(Boolean).join('. ');
        const preserve = compactPromptValue(plan.must_preserve);
        const optimized = compactPromptValue(plan.optimized_prompt);
        return [optimized, specification, preserve ? `Identity anchors that must remain exact: ${preserve}.` : ''].filter(Boolean).join(' ');
    }
    function buildingReferenceAnchor(referenceRoles=[]){
        const labels = referenceRoles.map(role => {
            const normalized = String(role || '').replace(/^building-/, '');
            return BUILDING_OUTPUT_SLOTS.find(item => item[0] === normalized)?.[1] || '';
        }).filter(Boolean);
        if(!labels.length) return '';
        return `Treat the attached ${labels.join(', ')} reference image${labels.length > 1 ? 's' : ''} as canonical evidence of one exact building. Preserve all visible geometry, proportions, openings, material boundaries, equipment and weathering across views.`;
    }
    function buildBuildingPrompt(view, plan={}, referenceRoles=[]){
        const target = String(view || '').replace(/^building-/, '');
        const identity = buildingIdentity(plan);
        const referenceAnchor = buildingReferenceAnchor(referenceRoles);
        if(target === 'sketch'){
            return [
                'Create one professional architectural design board for a single coherent building, with four clearly separated orthographic drawings: front elevation, right-side elevation, rear elevation and roof plan.',
                identity,
                referenceAnchor,
                'Use precise black technical linework on clean white drafting paper, consistent scale and aligned floor and roof levels across every view. Show doors, windows, structural bays, facade joints, roof edges and fixed exterior equipment as buildable geometry. The board contains only the four line drawings on blank drafting paper; all surfaces and margins remain clean and unmarked.'
            ].filter(Boolean).join(' ');
        }
        const camera = BUILDING_VIEW_CAMERAS[target];
        if(!camera) throw new Error(`Unsupported building view: ${view}`);
        return [
            `Generate the ${target} view of the same exact building.`,
            camera,
            identity,
            referenceAnchor,
            'Represent a full-scale physically constructed building photographed on a real location. Use physically plausible structure and joints, true material microtexture, natural construction tolerances, subtle surface variation, credible weather exposure and grounded contact shadows. Natural photographic light response, restrained color, documentary location-scout realism and coherent surroundings. Use rule-of-thirds placement for the ground, sky and surrounding breathing room while keeping the required elevation or overhead camera axis exact. Keep facade identity, floor heights, bay spacing, openings, roof profile, materials, equipment and aging continuous with every supplied view.'
        ].filter(Boolean).join(' ');
    }
    function buildBuildingPromptSet(plan={}, referenceRoles=[], views=['sketch','front','side','back','top']){
        return Object.fromEntries(views.map(view => [view, buildBuildingPrompt(view, plan, referenceRoles)]));
    }
    function buildingActions(node){
        normalizeNode(node);
        const stage = node.buildingStage;
        if(BUSY_STAGES.has(stage)) return [{action:'busy', label:stage === BUILDING_STAGES.PLANNING ? '需求整合中' : '生成中', icon:'loader-2', disabled:true, primary:true}];
        if(stage === BUILDING_STAGES.AWAITING_SKETCH) return [
            {action:'confirm-sketch', label:'确认线稿', icon:'check', primary:true},
            {action:'regenerate-sketch', label:'重新生成', icon:'refresh-cw', primary:false}
        ];
        if(stage === BUILDING_STAGES.AWAITING_FRONT) return [
            {action:'confirm-front', label:'确认正面', icon:'check', primary:true},
            {action:'regenerate-front', label:'重新生成', icon:'refresh-cw', primary:false}
        ];
        if(stage === BUILDING_STAGES.DONE) return [{action:'done', label:'生成完成', icon:'check-circle-2', disabled:true, primary:true}];
        if(stage === BUILDING_STAGES.PARTIAL || stage === BUILDING_STAGES.ERROR) return [{action:'retry-missing', label:'重试缺失视图', icon:'refresh-cw', primary:true}];
        return [{action:'run', label:'生成多视图', icon:'sparkles', primary:true}];
    }

    window.CanvasBuildingMultiView = Object.freeze({
        MODES,
        PERSON_INPUT_SLOTS,
        BUILDING_INPUT_SLOTS,
        BUILDING_OUTPUT_SLOTS,
        BUILDING_STAGES,
        ALL_INPUT_SLOTS,
        mode,
        normalizeNode,
        inputSlots,
        outputSlots,
        roleDefinition,
        roleKind,
        isRoleActive,
        isBusy,
        setMode,
        groupLabel,
        BUILDING_VIEW_CAMERAS,
        buildBuildingPrompt,
        buildBuildingPromptSet,
        buildingActions
    });
})();
