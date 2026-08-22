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
        if(!Array.isArray(node.buildingOutputs)) node.buildingOutputs = [];
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
        groupLabel
    });
})();
