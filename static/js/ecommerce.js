(function(){
    'use strict';

    const WORKSPACE_VARIANT = new URLSearchParams(window.location.search).get('workspace') || 'ecommerce';
    const IS_FREE_CREATION = WORKSPACE_VARIANT === 'free-creation';
    const SETTINGS_KEY = IS_FREE_CREATION ? 'studio_free_creation_settings_v1' : 'studio_ecommerce_settings_v2';
    const LEGACY_SETTINGS_KEY = IS_FREE_CREATION ? '' : 'studio_ecommerce_settings_v1';
    const CURRENT_TASK_KEY = IS_FREE_CREATION ? 'free_creation_current_task' : 'ecommerce_current_task';
    const SETTINGS_SCHEMA_VERSION = 4;
    const DEFAULT_OPERATION = 'universal';
    const ASPECT_RATIOS = ['source','1:1','2:3','3:2','3:4','4:3','4:5','9:16','16:9'];
    const RESOLUTIONS = ['auto','1k','2k','4k'];
    const QUALITIES = ['auto','low','medium','high'];
    const ECOMMERCE_TASK_MEMORY_LIMIT = 300;
    const MAX_REFERENCE_UPLOAD_BYTES = 50 * 1024 * 1024;
    const STUDIO_REFERENCE_TYPES = [
        {id:'studio_white', labelKey:'ecommerce.studioWhite', descKey:'ecommerce.studioWhiteHint', tone:'white', colors:['#fffef8','#f1f1ec','#d7d7cf']},
        {id:'studio_gray', labelKey:'ecommerce.studioGray', descKey:'ecommerce.studioGrayHint', tone:'gray', colors:['#f0f0ed','#cfcfca','#8d8d88']},
        {id:'studio_black', labelKey:'ecommerce.studioBlack', descKey:'ecommerce.studioBlackHint', tone:'black', colors:['#151515','#333331','#f2f0e7']},
        {id:'studio_warm', labelKey:'ecommerce.studioWarm', descKey:'ecommerce.studioWarmHint', tone:'warm', colors:['#fff3df','#dfba89','#9a6636']},
        {id:'studio_cool', labelKey:'ecommerce.studioCool', descKey:'ecommerce.studioCoolHint', tone:'cool', colors:['#edf7ff','#9ebbd2','#415a70']},
        {id:'studio_pink', labelKey:'ecommerce.studioPink', descKey:'ecommerce.studioPinkHint', tone:'pink', colors:['#fff0f5','#e7a5bd','#9c5a70']},
        {id:'studio_red_gold', labelKey:'ecommerce.studioRedGold', descKey:'ecommerce.studioRedGoldHint', tone:'red', colors:['#8f1d22','#d6a650','#fff2cf']},
        {id:'studio_cutout', labelKey:'ecommerce.studioCutout', descKey:'ecommerce.studioCutoutHint', tone:'cutout', colors:['#ffffff','#e9ecef','#c8ccd0']},
    ];
    const OPERATION_CONFIG = {
        universal: {
            titleKey:'ecommerce.universal',
            inputs:[],
            universal:true,
        },
        try_on: {
            titleKey:'ecommerce.tryOn',
            inputs:[
                {role:'source', labelKey:'ecommerce.modelImage', required:true},
                {role:'upper_garment', labelKey:'ecommerce.refUpper', required:false},
                {role:'lower_garment', labelKey:'ecommerce.refLower', required:false},
                {role:'full_garment', labelKey:'ecommerce.refFullGarment', required:false},
                {role:'shoes', labelKey:'ecommerce.refShoes', required:false},
                {role:'accessory', labelKey:'ecommerce.refAccessory', required:false},
                {role:'pose', labelKey:'ecommerce.poseImage', required:false},
            ],
        },
        pose_transfer: {
            titleKey:'ecommerce.poseTransfer',
            inputs:[
                {role:'source', labelKey:'ecommerce.personImage', required:true},
                {role:'pose', labelKey:'ecommerce.poseImage', required:false},
            ],
        },
        prop_replace: {
            titleKey:'ecommerce.propReplace',
            inputs:[
                {role:'source', labelKey:'ecommerce.sourceImage', required:true},
                {role:'prop', labelKey:'ecommerce.propImage', required:true},
            ],
        },
        angle_change: {
            titleKey:'ecommerce.angleChange',
            inputs:[
                {role:'source', labelKey:'ecommerce.subjectImage', required:true},
            ],
        },
        background_change: {
            titleKey:'ecommerce.backgroundChange',
            inputs:[
                {role:'source', labelKey:'ecommerce.sourceImage', required:true},
                {role:'background', labelKey:'ecommerce.backgroundImage', required:false},
            ],
        },
    };

    const UNIVERSAL_PRESET_ROLES = ['subject','model_identity','full_garment','accessory'];
    const LEGACY_UNIVERSAL_PRESET_ROLES = [...UNIVERSAL_PRESET_ROLES,'pose','scene'];
    const UNIVERSAL_CANONICAL_ROLE_ORDER = ['subject','model_identity','upper_garment','lower_garment','full_garment','shoes','accessory','prop','scene_prop','detail','pose','scene','style'];
    const UNIVERSAL_EXCLUSIVE_ROLES = new Set(['subject','model_identity','upper_garment','lower_garment','full_garment','shoes','pose','scene','style']);
    const UNIVERSAL_PRODUCT_ROLES = new Set(['upper_garment','lower_garment','full_garment','shoes','accessory','prop','scene_prop']);
    const TRY_ON_OUTFIT_ROLES = [
        {role:'upper_garment', labelKey:'ecommerce.refUpper', stageKey:'ecommerce.tryOnUpperStage', number:'02'},
        {role:'lower_garment', labelKey:'ecommerce.refLower', stageKey:'ecommerce.tryOnLowerStage', number:'03'},
        {role:'full_garment', labelKey:'ecommerce.refFullGarment', stageKey:'ecommerce.tryOnFullStage', number:'04'},
        {role:'shoes', labelKey:'ecommerce.refShoes', stageKey:'ecommerce.tryOnShoesStage', number:'05'},
        {role:'accessory', labelKey:'ecommerce.refAccessory', stageKey:'ecommerce.tryOnAccessoryStage', number:'06'},
    ];
    const TRY_ON_POSE_ROLE = {role:'pose', labelKey:'ecommerce.poseImage', stageKey:'ecommerce.tryOnPoseStage', number:'07'};
    const TRY_ON_WARDROBE_ROLES = [...TRY_ON_OUTFIT_ROLES, TRY_ON_POSE_ROLE];
    const TRY_ON_DEFAULT_WARDROBE_SLOT_COUNT = 3;
    const TRY_ON_PREVIEW_LAYER_ORDER = ['full_garment','upper_garment','lower_garment','shoes','accessory','garment'];
    const TRY_ON_REQUEST_ROLES = ['model_identity', ...TRY_ON_PREVIEW_LAYER_ORDER, 'detail', 'pose'];
    const TRY_ON_MULTI_REFERENCE_ROLES = ['source', ...TRY_ON_REQUEST_ROLES];
    const tryOnCutoutCache = new Map();

    const DEFAULT_OPTIONS = {
        universal:{instruction:'', studio_reference:''},
        try_on:{garment_category:'auto', instruction:'', slot_order:[], visible_slot_count:TRY_ON_DEFAULT_WARDROBE_SLOT_COUNT, studio_reference:''},
        pose_transfer:{pose_source:'preset', pose_preset:'standing_front', instruction:'', studio_reference:''},
        prop_replace:{target_description:'', instruction:'', studio_reference:''},
        angle_change:{azimuth:45, elevation:0, distance:'medium', instruction:'', studio_reference:''},
        background_change:{background_mode:'preset', background_preset:'studio_white', background_prompt:'', instruction:'', studio_reference:''},
    };

    const createWorkspace = () => ({
        inputs:{},
        taskId:'',
        currentTask:null,
        selectedOutput:0,
        compareValue:50,
        zoom:1,
    });

    const state = {
        operation:DEFAULT_OPERATION,
        mode:'standard',
        inputs:{},
        options:JSON.parse(JSON.stringify(DEFAULT_OPTIONS)),
        capabilities:null,
        providerId:'',
        model:'',
        aspectRatio:'source',
        resolution:'auto',
        quality:'auto',
        count:0,
        modelPanelCollapsed:false,
        currentTask:null,
        tasks:[],
        selectedOutput:0,
        activeUploadRole:'',
        compareValue:50,
        zoom:1,
        tasksById:new Map(),
        activeTaskIds:new Set(),
        taskPollTimer:null,
        taskPollInflight:false,
        routeActive:window.top === window,
        submissionsInFlight:0,
        generationTimer:null,
        candidateTimer:null,
        assetLibrary:null,
        assetDialogMode:'select',
        referenceSlotTypes:[],
        referencePreview:{key:'', versions:[], selectedIndex:0, mode:'preview', ratio:'free', cropRect:{x:.05,y:.05,w:.9,h:.9}, drag:null},
        tryOnSwitches:{},
        compareViewer:null,
        viewportWidth:window.innerWidth,
        settingsNeedsMigration:false,
        workspaces:Object.fromEntries(Object.keys(OPERATION_CONFIG).map(operation => [operation, createWorkspace()])),
        settingsSerialized:'',
        settingsPersistTimer:null,
        preferenceWriteChain:Promise.resolve(),
        preferenceEchoGuardUntil:0,
        lastPointerDownAt:0,
        initializing:true,
    };

    const el = {};
    let referenceTypeOpenTimer = 0;
    const byId = id => document.getElementById(id);
    const t = (key, vars={}) => {
        let value = window.StudioI18n?.t?.(key) || key;
        Object.entries(vars).forEach(([name,replacement]) => { value = value.replaceAll(`{${name}}`, String(replacement)); });
        return value;
    };
    const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
    const formatName = value => {
        const clean = String(value || '').trim();
        return clean.length > 36 ? `${clean.slice(0,33)}…` : clean;
    };

    function cacheElements(){
        [
            'ecommercePage','ecommerceWorkspace','controlPanel','controlInputMount','controlActionMount',
            'inputModule','universalDock','universalDockInputs','universalDockActions','generateActions',
            'operationTabs','modeToggle','capabilityStatus','routeSummary','inputSlots','inputProgress',
            'operationControls','advancedSettings','modelPanelToggle','modelPanelBody',
            'modelPanelSelection','providerSelect','modelSelect','ratioSelect','resolutionSelect','qualitySelect','countSelect',
            'addUniversalReference','formError','generateButton','emptyResult','emptyResultNotice','emptyResultNoticeTitle','emptyResultNoticeMessage',
            'resultWorkspace','compareReset','historyToggle',
            'compareStage','afterClip','compareHandle','beforeBackdrop','beforeImage','afterBackdrop','afterImage','compareBeforeLabel','candidateList','resultMeta',
            'generationOverlay','generationTimer','generationMessage','resultErrorOverlay','resultErrorTitle','resultErrorMessage','resultErrorClear',
            'taskDrawer','taskList','drawerBackdrop','closeHistory',
            'assetDialog','assetLibrarySelect',
            'assetCategorySelect','assetReferenceTypeSelect','assetGrid','assetDialogTitle','assetSaveConfirm','qualityDialog','qualityForm',
            'studioDialog','studioReferenceGrid','studioClear',
            'qualityChecks','qualityNote','cancelQuality','zoomIn','zoomOut','zoomReset','compareFullscreen','toast',
            'referencePreview','referencePreviewTitle','referencePreviewMode','referenceCropMode','referenceCropRatios',
            'referencePreviewStage','referencePreviewImage','referenceCropStage','referenceCropImage','referenceCropBox',
            'referenceVersionList','useReferenceVersion','applyReferenceCrop',
        ].forEach(id => { el[id] = byId(id); });
    }

    function configureWorkspaceVariant(){
        if(!IS_FREE_CREATION) return;
        document.title = t('freeCreation.title');
        el.ecommercePage?.classList.add('is-free-creation');
        el.operationTabs?.setAttribute('aria-label', t('freeCreation.title'));
        el.operationTabs?.querySelectorAll('[data-operation]').forEach(button => {
            if(button.dataset.operation !== 'universal') button.remove();
        });
        el.universalDock?.setAttribute('aria-label', t('freeCreation.referenceAssets'));
        const emptyTitle = el.emptyResult?.querySelector('h3');
        const emptyHint = el.emptyResult?.querySelector('h3 + p');
        emptyTitle?.setAttribute('data-i18n', 'freeCreation.emptyTitle');
        emptyHint?.setAttribute('data-i18n', 'freeCreation.emptyHint');
        if(emptyTitle) emptyTitle.textContent = t('freeCreation.emptyTitle');
        if(emptyHint) emptyHint.textContent = t('freeCreation.emptyHint');
        const sourceRatioOption = el.ratioSelect?.querySelector('option[value="source"]');
        sourceRatioOption?.setAttribute('data-i18n', 'freeCreation.sourceRatio');
        if(sourceRatioOption) sourceRatioOption.textContent = t('freeCreation.sourceRatio');
    }

    function cleanCropHistory(values){
        if(!Array.isArray(values)) return [];
        return values.filter(value => value && typeof value === 'object' && value.url).map(value => ({
            url:String(value.url || ''), name:String(value.name || ''), source_url:String(value.source_url || ''),
            width:Number(value.width || 0), height:Number(value.height || 0), ratio:String(value.ratio || ''),
            created_at:Number(value.created_at || 0), crop:value.crop && typeof value.crop === 'object' ? {...value.crop} : {},
        }));
    }

    function isLocalPreviewUrl(url){
        return String(url || '').startsWith('blob:');
    }

    function referenceDisplayUrl(item){
        return String(item?.preview_url || item?.url || '');
    }

    function hasReferenceDisplay(item){
        return Boolean(referenceDisplayUrl(item));
    }

    function revokeReferencePreviewUrl(item){
        const previewUrl = String(item?.preview_url || '');
        if(isLocalPreviewUrl(previewUrl)) URL.revokeObjectURL(previewUrl);
    }

    function revokeInputPreviewUrls(input){
        revokeReferencePreviewUrl(input);
        if(Array.isArray(input?.alternates)) input.alternates.forEach(revokeReferencePreviewUrl);
    }

    function stripUploadPreviewFields(value){
        if(!value || typeof value !== 'object') return value;
        const clean = {...value};
        delete clean.preview_url;
        delete clean.uploading;
        delete clean.upload_token;
        if(Array.isArray(clean.alternates)) clean.alternates = clean.alternates.map(stripUploadPreviewFields).filter(item => item?.url);
        return clean;
    }

    function serializableInputs(inputs){
        return Object.fromEntries(Object.entries(inputs || {}).map(([role,input]) => [role, stripUploadPreviewFields(input)]));
    }

    function cloneSerializableInput(input){
        if(!input || typeof input !== 'object') return null;
        return JSON.parse(JSON.stringify(stripUploadPreviewFields(input)));
    }

    function cleanInputCandidate(value){
        if(!value || typeof value !== 'object' || (!value.url && !value.preview_url)) return null;
        return {
            url:String(value.url || ''),
            preview_url:String(value.preview_url || ''),
            uploading:value.uploading === true,
            upload_token:String(value.upload_token || ''),
            name:String(value.name || ''),
            kind:'image',
            mime:String(value.mime || ''),
            width:Number(value.width || 0),
            height:Number(value.height || 0),
            original_url:String(value.original_url || value.url || ''),
            original_name:String(value.original_name || value.name || ''),
            original_width:Number(value.original_width || value.width || 0),
            original_height:Number(value.original_height || value.height || 0),
            crop_history:cleanCropHistory(value.crop_history),
        };
    }

    function cleanInputCandidates(value){
        if(!value || typeof value !== 'object') return [];
        const candidates = [];
        const seen = new Set();
        const append = candidate => {
            const normalized = cleanInputCandidate(candidate);
            const key = normalized?.url || normalized?.preview_url || '';
            if(!key) return;
            if(seen.has(key)) {
                const existingIndex = candidates.findIndex(item => (item.url || item.preview_url) === key);
                if(existingIndex >= 0) candidates[existingIndex] = {...candidates[existingIndex], ...normalized};
                return;
            }
            seen.add(key);
            candidates.push(normalized);
        };
        if(Array.isArray(value.alternates)) value.alternates.forEach(append);
        append(value);
        return candidates;
    }

    function cleanSavedInput(value, role){
        if(!value || typeof value !== 'object') return null;
        const input = {
            url:String(value.url || ''), name:String(value.name || ''), role:String(value.role || role || ''),
            kind:'image', mime:String(value.mime || ''), width:Number(value.width || 0), height:Number(value.height || 0),
            reference_id:String(value.reference_id || role || ''), reference_type:String(value.reference_type || ''),
            slot_type:String(value.slot_type || ''),
            custom_type_label:String(value.custom_type_label || ''),
            label:String(value.label || ''), instruction:String(value.instruction || ''), order:Number(value.order || 0),
            original_url:String(value.original_url || value.url || ''), original_name:String(value.original_name || value.name || ''),
            original_width:Number(value.original_width || value.width || 0), original_height:Number(value.original_height || value.height || 0),
            crop_history:cleanCropHistory(value.crop_history),
        };
        const candidates = cleanInputCandidates(value);
        if(Array.isArray(value.alternates) || candidates.length > 1) {
            const selectedByUrl = candidates.findIndex(candidate => candidate.url === input.url);
            const rawSelected = Number(value.selected_index || 0);
            input.alternates = candidates;
            input.selected_index = selectedByUrl >= 0
                ? selectedByUrl
                : Math.max(0, Math.min(candidates.length - 1, Number.isFinite(rawSelected) ? rawSelected : 0));
        }
        return input;
    }

    function loadSettings(serialized=''){
        try {
            const raw = serialized || localStorage.getItem(SETTINGS_KEY) || localStorage.getItem(LEGACY_SETTINGS_KEY) || '{}';
            const saved = JSON.parse(raw);
            const schemaVersion = Number(saved.schema_version || 0);
            state.settingsNeedsMigration = schemaVersion !== SETTINGS_SCHEMA_VERSION;
            if(IS_FREE_CREATION) state.operation = DEFAULT_OPERATION;
            else if(schemaVersion === SETTINGS_SCHEMA_VERSION && OPERATION_CONFIG[saved.operation]) state.operation = saved.operation;
            else state.operation = DEFAULT_OPERATION;
            state.mode = 'standard';
            if(saved.options && typeof saved.options === 'object') {
                Object.keys(DEFAULT_OPTIONS).forEach(key => {
                    if(saved.options[key] && typeof saved.options[key] === 'object') {
                        state.options[key] = {...state.options[key], ...saved.options[key]};
                    }
                });
            }
            state.providerId = String(saved.provider_id || '');
            state.model = String(saved.model || '');
            state.aspectRatio = ASPECT_RATIOS.includes(saved.aspect_ratio) ? saved.aspect_ratio : 'source';
            state.resolution = RESOLUTIONS.includes(saved.resolution) ? saved.resolution : 'auto';
            state.quality = QUALITIES.includes(saved.quality) ? saved.quality : 'auto';
            state.count = [0,1,2,3,4].includes(Number(saved.count)) ? Number(saved.count) : 0;
            state.modelPanelCollapsed = saved.model_panel_collapsed === true;
            if(saved.workspaces && typeof saved.workspaces === 'object') {
                Object.keys(OPERATION_CONFIG).forEach(operation => {
                    const value = saved.workspaces[operation];
                    if(!value || typeof value !== 'object') return;
                    const workspace = state.workspaces[operation] || createWorkspace();
                    workspace.inputs = Object.fromEntries(Object.entries(value.inputs || {}).map(([role,input]) => [role,cleanSavedInput(input,role)]).filter(([,input]) => input));
                    workspace.taskId = String(value.current_task_id || value.task_id || '');
                    workspace.selectedOutput = Math.max(0, Number(value.selected_output || 0));
                    workspace.compareValue = Math.max(0, Math.min(100, Number(value.compare_value ?? 50)));
                    workspace.zoom = Math.max(1, Math.min(3, Number(value.zoom || 1)));
                    state.workspaces[operation] = workspace;
                });
            }
            state.settingsSerialized = raw;
        } catch(e) {}
    }

    function activeWorkspace(){
        if(!state.workspaces[state.operation]) state.workspaces[state.operation] = createWorkspace();
        return state.workspaces[state.operation];
    }

    function captureWorkspace(){
        const workspace = activeWorkspace();
        workspace.inputs = state.inputs;
        workspace.currentTask = state.currentTask;
        workspace.taskId = String(state.currentTask?.id || state.currentTask?.task_id || workspace.taskId || '');
        workspace.selectedOutput = state.selectedOutput;
        workspace.compareValue = state.compareValue;
        workspace.zoom = state.zoom;
        return workspace;
    }

    function restoreWorkspace(operation=state.operation){
        const workspace = state.workspaces[operation] || createWorkspace();
        state.workspaces[operation] = workspace;
        state.inputs = workspace.inputs || {};
        state.currentTask = workspace.currentTask || null;
        state.selectedOutput = Number(workspace.selectedOutput || 0);
        state.compareValue = Number(workspace.compareValue ?? 50);
        state.zoom = Number(workspace.zoom || 1);
        return workspace;
    }

    function serializableWorkspaces(){
        captureWorkspace();
        return Object.fromEntries(Object.entries(state.workspaces).map(([operation,workspace]) => [operation,{
            inputs:serializableInputs(workspace.inputs || {}),
            current_task_id:String(workspace.currentTask?.id || workspace.currentTask?.task_id || workspace.taskId || ''),
            selected_output:Number(workspace.selectedOutput || 0),
            compare_value:Number(workspace.compareValue ?? 50),
            zoom:Number(workspace.zoom || 1),
        }]));
    }

    function persistSettings(options={}){
        const shouldSync = options.sync !== false;
        if(state.settingsPersistTimer) {
            clearTimeout(state.settingsPersistTimer);
            state.settingsPersistTimer = null;
        }
        const snapshot = {
            schema_version:SETTINGS_SCHEMA_VERSION,
            operation:state.operation,
            mode:state.mode,
            options:state.options,
            provider_id:state.providerId,
            model:state.model,
            aspect_ratio:state.aspectRatio,
            resolution:state.resolution,
            quality:state.quality,
            count:state.count,
            model_panel_collapsed:state.modelPanelCollapsed,
            workspaces:serializableWorkspaces(),
        };
        const serialized = JSON.stringify(snapshot);
        state.settingsSerialized = serialized;
        state.preferenceEchoGuardUntil = Math.max(state.preferenceEchoGuardUntil, Date.now() + 1500);
        try { localStorage.setItem(SETTINGS_KEY, serialized); } catch(e) {}
        if(shouldSync) syncPreferenceSnapshot(serialized);
        else scheduleSettingsPersistence(Number(options.delay || 700));
    }

    function scheduleSettingsPersistence(delay=240){
        clearTimeout(state.settingsPersistTimer);
        state.settingsPersistTimer = setTimeout(() => {
            state.settingsPersistTimer = null;
            persistSettings();
        }, delay);
    }

    function flushScheduledSettingsPersistence(){
        if(!state.settingsPersistTimer) return;
        clearTimeout(state.settingsPersistTimer);
        state.settingsPersistTimer = null;
        persistSettings();
    }

    function syncPreferenceSnapshot(serialized, attempt=0){
        if(IS_FREE_CREATION) return;
        let runtime = window.RuntimeSync || null;
        if(!runtime) {
            try { runtime = window.top?.RuntimeSync || null; } catch(e) { runtime = null; }
        }
        if(runtime?.setPreference) {
            const write = () => Promise.resolve(runtime.setPreference('ecommerce_settings', serialized)).catch(() => {
                if(attempt < 5) setTimeout(() => syncPreferenceSnapshot(serialized, attempt + 1), 120);
            });
            state.preferenceWriteChain = state.preferenceWriteChain.then(write, write);
            return;
        }
        if(attempt < 20) setTimeout(() => syncPreferenceSnapshot(serialized, attempt + 1), 120);
    }

    async function waitForPreferenceBootstrap(timeout=1800){
        if(IS_FREE_CREATION) return;
        const deadline = Date.now() + timeout;
        let runtime = null;
        while(Date.now() < deadline && !runtime) {
            try { runtime = window.top?.RuntimeSync || window.RuntimeSync || null; } catch(e) { runtime = window.RuntimeSync || null; }
            if(!runtime) await new Promise(resolve => setTimeout(resolve, 25));
        }
        if(!runtime?.ready) return;
        const remaining = Math.max(0, deadline - Date.now());
        await Promise.race([
            Promise.resolve(runtime.ready()).catch(() => {}),
            new Promise(resolve => setTimeout(resolve, remaining)),
        ]);
    }

    function isTextEditingElement(node=document.activeElement){
        if(!node) return false;
        const tag = String(node.tagName || '').toUpperCase();
        if(tag === 'TEXTAREA') return true;
        if(tag !== 'INPUT') return false;
        const type = String(node.type || 'text').toLowerCase();
        return ['text','search','url','tel','email','password','number'].includes(type);
    }

    function shouldIgnoreIncomingSettings(){
        return Date.now() < state.preferenceEchoGuardUntil || isTextEditingElement();
    }

    function applyIncomingSettings(serialized){
        if(IS_FREE_CREATION) return;
        if(!serialized || serialized === state.settingsSerialized) return;
        clearTimeout(state.settingsPersistTimer);
        state.settingsPersistTimer = null;
        loadSettings(String(serialized));
        restoreWorkspace(state.operation);
        state.settingsNeedsMigration = false;
        updateTabs();
        renderInputs();
        renderOperationControls();
        syncGenerationParameterControls();
        if(state.capabilities) {
            populateModelSelectors();
            updateRouteSummary();
        } else updateModelPanelSelection();
        if(state.currentTask) renderTaskResult(state.currentTask); else hideResult();
    }

    function currentConfig(){ return OPERATION_CONFIG[state.operation]; }
    function currentOptions(){ return state.options[state.operation]; }

    function updateTabs(){
        el.operationTabs?.querySelectorAll('[data-operation]').forEach(button => {
            const active = button.dataset.operation === state.operation;
            button.classList.toggle('active', active);
            button.setAttribute('aria-current', active ? 'page' : 'false');
        });
        el.modeToggle?.querySelectorAll('[data-mode]').forEach(button => {
            button.classList.toggle('active', button.dataset.mode === state.mode);
        });
        const generateLabel = el.generateButton?.querySelector('span');
        if(generateLabel) generateLabel.textContent = t('ecommerce.generate');
        const universalLabel = el.operationTabs?.querySelector('[data-operation="universal"] b');
        if(universalLabel) universalLabel.textContent = t(IS_FREE_CREATION ? 'freeCreation.title' : 'ecommerce.universal');
        if(IS_FREE_CREATION) {
            document.title = t('freeCreation.title');
            el.operationTabs?.setAttribute('aria-label', t('freeCreation.title'));
            el.universalDock?.setAttribute('aria-label', t('freeCreation.referenceAssets'));
        }
        syncUniversalLayout();
        const inputHeading = el.inputModule?.querySelector('.ec-section-head h2');
        if(inputHeading) inputHeading.textContent = t(IS_FREE_CREATION ? 'freeCreation.referenceAssets' : (currentConfig()?.universal ? 'ecommerce.referenceAssets' : 'ecommerce.inputs'));
    }

    function syncUniversalLayout(){
        const universal = Boolean(currentConfig()?.universal);
        const tryOn = state.operation === 'try_on';
        el.ecommercePage?.classList.toggle('is-universal', universal);
        el.ecommercePage?.classList.toggle('is-try-on', tryOn);
        if(!universal) el.ecommercePage?.classList.remove('has-many-universal-references');
        el.universalDock?.classList.toggle('hidden', !universal);
        if(!universal) el.universalDock?.classList.remove('has-many-references');
        el.universalDock?.setAttribute('aria-hidden', universal ? 'false' : 'true');
        el.addUniversalReference?.classList.toggle('hidden', !universal);
        const inputTarget = universal ? el.universalDockInputs : el.controlInputMount;
        const tryOnActionSlot = tryOn ? byId('tryOnMessageActionSlot') : null;
        const actionTarget = universal ? el.universalDockActions : (tryOnActionSlot || el.controlActionMount);
        if(inputTarget && el.inputModule?.parentElement !== inputTarget) inputTarget.appendChild(el.inputModule);
        if(actionTarget && el.generateActions?.parentElement !== actionTarget) actionTarget.appendChild(el.generateActions);
    }

    function renderInputs(){
        if(window.StudioFocusGuard?.shouldDeferDomUpdate?.(el.inputSlots)) {
            window.StudioFocusGuard.deferDomUpdate('ecommerce-render-inputs', renderInputs);
            return;
        }
        const focusSnapshot = window.StudioFocusGuard?.capture?.();
        const editingControl = isTextEditingElement() ? document.activeElement : null;
        const config = currentConfig();
        if(config.universal) {
            renderUniversalInputs();
            if(focusSnapshot) window.StudioFocusGuard?.restore?.(focusSnapshot);
            if(editingControl) restoreEditingFocus(editingControl);
            return;
        }
        if(state.operation === 'try_on') {
            renderTryOnInputs();
            if(focusSnapshot) window.StudioFocusGuard?.restore?.(focusSnapshot);
            if(editingControl) restoreEditingFocus(editingControl);
            return;
        }
        el.inputSlots.innerHTML = config.inputs.map(input => inputSlotHtml(input)).join('') + studioReferenceCardHtml();
        const required = config.inputs.filter(item => item.required);
        const completed = required.filter(item => state.inputs[item.role]?.url).length;
        el.inputProgress.textContent = `${completed}/${required.length}`;
        bindInputSlots();
        bindStudioReferenceControls();
        if(focusSnapshot) window.StudioFocusGuard?.restore?.(focusSnapshot);
        if(editingControl) restoreEditingFocus(editingControl);
    }

    const UNIVERSAL_FALLBACK_ROLES = [
        ['subject','subject','ecommerce.refSubject'],['model_identity','model_identity','ecommerce.refModelIdentity'],['upper_garment','upper_garment','ecommerce.refUpper'],['lower_garment','lower_garment','ecommerce.refLower'],
        ['full_garment','full_garment','ecommerce.refFullGarment'],['shoes','shoes','ecommerce.refShoes'],['accessory','accessory','ecommerce.refAccessory'],
        ['prop','prop','ecommerce.refProp'],['scene_prop','scene_prop','ecommerce.refSceneProp'],['detail','detail','ecommerce.refDetail'],['pose','pose','ecommerce.refPose'],['scene','scene','ecommerce.refScene'],['style','style','ecommerce.refStyle'],
    ];
    const TRY_ON_SELECTABLE_REFERENCE_ROLES = new Set(['subject','model_identity','upper_garment','lower_garment','full_garment','shoes','accessory','prop','detail','pose']);

    function newUniversalKey(){
        return `ref_${crypto.randomUUID?.().replaceAll('-','').slice(0,12) || Math.random().toString(36).slice(2,14)}`;
    }

    function universalEntries(){
        return Object.entries(state.inputs).filter(([key,item]) => key.startsWith('ref_') && item && typeof item === 'object').sort((a,b) => Number(a[1].order || 0) - Number(b[1].order || 0));
    }

    function universalTypedEntries(){
        const roleOrder = new Map(UNIVERSAL_CANONICAL_ROLE_ORDER.map((role,index) => [role,index]));
        return universalEntries().filter(([,item]) => item.url).sort((a,b) => {
            const roleA = String(a[1].reference_type || a[1].role || 'prop');
            const roleB = String(b[1].reference_type || b[1].role || 'prop');
            return (roleOrder.get(roleA) ?? roleOrder.size) - (roleOrder.get(roleB) ?? roleOrder.size) || Number(a[1].order || 0) - Number(b[1].order || 0);
        });
    }

    function universalHasUserSupplement(){
        return !IS_FREE_CREATION && Boolean(String(currentOptions()?.instruction || '').trim());
    }

    function universalReferenceItemLabel(item, fallback=''){
        return requestReferenceLabel(item, fallback || referenceTypeDisplayLabel(item, item?.reference_type || item?.role || 'prop'));
    }

    function resolveUniversalReferencePlan(){
        const userSupplement = universalHasUserSupplement();
        const entries = userSupplement ? universalEntries().filter(([,item]) => item.url) : universalTypedEntries();
        const byRole = Object.fromEntries(UNIVERSAL_CANONICAL_ROLE_ORDER.map(role => [role,[]]));
        entries.forEach(entry => {
            const role = String(entry[1].reference_type || entry[1].role || 'prop');
            if(!byRole[role]) byRole[role] = [];
            byRole[role].push(entry);
        });
        const products = entries.filter(([,item]) => UNIVERSAL_PRODUCT_ROLES.has(String(item.reference_type || item.role || '')));
        const conflicts = [];
        UNIVERSAL_EXCLUSIVE_ROLES.forEach(role => {
            if((byRole[role] || []).length > 1) {
                const roleLabel = referenceSlotTypeById(role)?.label || role;
                conflicts.push(t('ecommerce.referenceDuplicateConflict',{role:roleLabel}));
            }
        });
        if(byRole.full_garment.length && (byRole.upper_garment.length || byRole.lower_garment.length)) conflicts.push(t('ecommerce.outfitTypeConflict'));
        if(byRole.scene.length && String(currentOptions()?.studio_reference || '').trim()) conflicts.push(t('ecommerce.sceneStudioConflict'));
        const productIds = new Set(products.map(([,item]) => item.reference_id));
        byRole.detail.forEach(([,item]) => {
            const targetId = String(item.detail_target_id || '').trim();
            if(!products.length) conflicts.push(t('ecommerce.detailMissingProduct'));
            else if(targetId && !productIds.has(targetId)) conflicts.push(t('ecommerce.detailTargetMissing'));
            else if(!targetId && products.length > 1) conflicts.push(t('ecommerce.detailTargetRequired'));
        });
        const subject = byRole.subject[0]?.[1] || null;
        const identity = byRole.model_identity[0]?.[1] || null;
        const garmentItems = byRole.full_garment.length ? byRole.full_garment : [...byRole.upper_garment,...byRole.lower_garment];
        const accessoryItems = [...byRole.shoes,...byRole.accessory,...byRole.prop,...byRole.scene_prop];
        const scene = byRole.scene[0]?.[1] || null;
        const pose = byRole.pose[0]?.[1] || null;
        const studio = currentStudioReference();
        let mode = '';
        if(subject) mode = 'subject_edit';
        else if(identity) mode = 'visible_model';
        else if(garmentItems.length && pose) mode = 'invisible_outfit';
        else if(products.length) mode = 'product_showcase';
        else conflicts.push(t('ecommerce.automaticTargetRequired'));

        let summary = [];
        if(mode === 'subject_edit') {
            summary = [
                [t('ecommerce.planBody'), universalReferenceItemLabel(subject)],
                [t('ecommerce.planIdentity'), identity ? universalReferenceItemLabel(identity) : t('ecommerce.planUseSubjectIdentity')],
                [t('ecommerce.planGarment'), garmentItems.length ? garmentItems.map(([,item]) => universalReferenceItemLabel(item)).join(' + ') : t('ecommerce.planKeepSubjectGarment')],
                [t('ecommerce.planAccessory'), accessoryItems.length ? accessoryItems.map(([,item]) => universalReferenceItemLabel(item)).join(' + ') : t('ecommerce.planKeepSubjectAccessory')],
                [t('ecommerce.planScene'), scene ? universalReferenceItemLabel(scene) : (studio?.label || t('ecommerce.planKeepSubjectScene'))],
                [t('ecommerce.planPose'), pose ? universalReferenceItemLabel(pose) : t('ecommerce.planUseSubjectPose')],
            ];
        } else if(mode === 'visible_model') {
            summary = [
                [t('ecommerce.planBody'), t('ecommerce.planSystemModel')],
                [t('ecommerce.planIdentity'), universalReferenceItemLabel(identity)],
                [t('ecommerce.planGarment'), garmentItems.length ? garmentItems.map(([,item]) => universalReferenceItemLabel(item)).join(' + ') : t('ecommerce.planSystemGarment')],
                [t('ecommerce.planAccessory'), accessoryItems.length ? accessoryItems.map(([,item]) => universalReferenceItemLabel(item)).join(' + ') : t('ecommerce.planNoAccessory')],
                [t('ecommerce.planScene'), scene ? universalReferenceItemLabel(scene) : (studio?.label || t('ecommerce.planSystemStudio'))],
                [t('ecommerce.planPose'), pose ? universalReferenceItemLabel(pose) : t('ecommerce.planSystemPose')],
            ];
        } else if(mode === 'invisible_outfit') {
            summary = [
                [t('ecommerce.planBody'), t('ecommerce.planInvisibleBody')],
                [t('ecommerce.planIdentity'), t('ecommerce.planNoIdentity')],
                [t('ecommerce.planGarment'), garmentItems.map(([,item]) => universalReferenceItemLabel(item)).join(' + ')],
                [t('ecommerce.planAccessory'), accessoryItems.length ? accessoryItems.map(([,item]) => universalReferenceItemLabel(item)).join(' + ') : t('ecommerce.planNoAccessory')],
                [t('ecommerce.planScene'), scene ? universalReferenceItemLabel(scene) : (studio?.label || t('ecommerce.planSystemStudio'))],
                [t('ecommerce.planPose'), universalReferenceItemLabel(pose)],
            ];
        } else if(mode === 'product_showcase') {
            summary = [
                [t('ecommerce.planBody'), t('ecommerce.planProductOnly')],
                [t('ecommerce.planIdentity'), t('ecommerce.planNoIdentity')],
                [t('ecommerce.planGarment'), garmentItems.length ? garmentItems.map(([,item]) => universalReferenceItemLabel(item)).join(' + ') : t('ecommerce.planNoGarment')],
                [t('ecommerce.planAccessory'), accessoryItems.length ? accessoryItems.map(([,item]) => universalReferenceItemLabel(item)).join(' + ') : t('ecommerce.planNoAccessory')],
                [t('ecommerce.planScene'), scene ? universalReferenceItemLabel(scene) : (studio?.label || t('ecommerce.planProductStudio'))],
                [t('ecommerce.planPose'), t('ecommerce.planProductArrangement')],
            ];
        } else {
            summary = [[t('ecommerce.planGenerationMode'), t('ecommerce.planMissingTarget')]];
        }
        return {
            mode, userSupplement, entries, byRole, products, conflicts, summary,
        };
    }

    function syncUniversalPromptModeUi(){
        if(state.operation !== 'universal' || IS_FREE_CREATION) return;
        const plan = resolveUniversalReferencePlan();
        el.inputSlots?.querySelectorAll('.ec-detail-target').forEach(node => node.classList.remove('hidden'));
    }

    function detailTargetIdForItem(item, plan){
        const explicit = String(item?.detail_target_id || '').trim();
        if(explicit) return explicit;
        return plan.products.length === 1 ? String(plan.products[0][1].reference_id || '') : '';
    }

    function universalDetailTargetHtml(item, plan){
        if(IS_FREE_CREATION || String(item?.reference_type || item?.role || '') !== 'detail') return '';
        const selected = detailTargetIdForItem(item, plan);
        if(!plan.products.length) return `<div class="ec-detail-target is-error"><b>${escapeHtml(t('ecommerce.detailTarget'))}</b><span>${escapeHtml(t('ecommerce.detailMissingProduct'))}</span></div>`;
        const options = plan.products.map(([,product]) => `<option value="${escapeHtml(product.reference_id)}" ${product.reference_id === selected ? 'selected':''}>${escapeHtml(universalReferenceItemLabel(product))}</option>`).join('');
        return `<label class="ec-detail-target"><b>${escapeHtml(t('ecommerce.detailTarget'))}</b><select data-detail-target="${escapeHtml(item.reference_id)}"><option value="">${escapeHtml(t('ecommerce.detailTargetChoose'))}</option>${options}</select></label>`;
    }

    function createUniversalReference(role, order){
        const key = newUniversalKey();
        state.inputs[key] = {url:'',name:'',role,reference_type:role,slot_type:defaultSlotTypeIdForRole(role),reference_id:key,custom_type_label:'',label:'',instruction:'',order};
        return key;
    }

    function universalReferenceHasContent(item){
        return Boolean(
            item?.url || item?.preview_url || item?.name || item?.label || item?.instruction || item?.custom_type_label || item?.detail_target_id
        );
    }

    function seedUniversalPresetsIfEmpty(){
        const entries = universalEntries();
        if(entries.length) {
            const legacyPreset = entries.length === LEGACY_UNIVERSAL_PRESET_ROLES.length
                && entries.every(([,item], index) => String(item.reference_type || item.role || '') === LEGACY_UNIVERSAL_PRESET_ROLES[index]);
            if(legacyPreset) {
                entries.slice(UNIVERSAL_PRESET_ROLES.length).forEach(([key,item]) => {
                    if(!universalReferenceHasContent(item)) delete state.inputs[key];
                });
            }
            return;
        }
        UNIVERSAL_PRESET_ROLES.forEach((role, order) => createUniversalReference(role, order));
    }

    function fallbackReferenceSlotTypes(){
        return UNIVERSAL_FALLBACK_ROLES.map(([id,role,labelKey], index) => ({
            id, role, label:t(labelKey), order:index * 10, enabled:true, locked:true,
        }));
    }

    function normalizedReferenceSlotTypes(){
        const configured = Array.isArray(state.referenceSlotTypes) && state.referenceSlotTypes.length
            ? state.referenceSlotTypes
            : (Array.isArray(state.capabilities?.reference_slot_types) ? state.capabilities.reference_slot_types : []);
        const fallbacks = fallbackReferenceSlotTypes();
        const source = configured.length
            ? [...configured, ...fallbacks.filter(fallback => !configured.some(item => item && (item.id === fallback.id || item.role === fallback.role)))]
            : fallbacks;
        return source.filter(item => item && item.enabled !== false).map((item,index) => ({
            id:String(item.id || item.role || '').trim(),
            role:String(item.role || item.id || '').trim(),
            label:localizedLabel(item) || (typeof item.label === 'string' ? item.label : '') || item.label_zh || item.id || item.role || '',
            order:Number(item.order ?? index * 10),
            locked:item.locked === true,
        })).filter(item => item.id && item.role).sort((a,b) => a.order - b.order);
    }

    function referenceSlotTypeById(id){
        const value = String(id || '').trim();
        const types = normalizedReferenceSlotTypes();
        return types.find(item => item.id === value) || types.find(item => item.role === value) || null;
    }

    function defaultSlotTypeIdForRole(role){
        const canonical = role === 'source' ? 'subject' : String(role || 'prop');
        return normalizedReferenceSlotTypes().find(item => item.role === canonical)?.id || canonical;
    }

    function selectedSlotTypeId(item, fallbackRole){
        const selected = referenceSlotTypeById(item?.slot_type) || referenceSlotTypeById(item?.reference_type) || referenceSlotTypeById(item?.role);
        return selected?.id || defaultSlotTypeIdForRole(fallbackRole);
    }

    function customReferenceTypeLabel(item){
        return String(item?.custom_type_label || '').replace(/\s+/g, ' ').trim().slice(0, 160);
    }

    function referenceTypeBaseLabel(item, fallbackRole){
        const selected = referenceSlotTypeById(selectedSlotTypeId(item || {}, fallbackRole));
        return selected?.label || t(tryOnInputConfig(fallbackRole)?.labelKey || 'ecommerce.garmentImage');
    }

    function referenceTypeDisplayLabel(item, fallbackRole){
        return customReferenceTypeLabel(item) || referenceTypeBaseLabel(item, fallbackRole);
    }

    function requestReferenceLabel(item, fallback=''){
        const custom = customReferenceTypeLabel(item);
        const label = String(item?.label || '').replace(/\s+/g, ' ').trim().slice(0, 160);
        if(custom && label && custom !== label) return `${custom}；${label}`.slice(0, 160);
        return custom || label || fallback;
    }

    function editReferenceTypeName(item, fallbackRole='prop', value=''){
        if(!item) return false;
        item.custom_type_label = String(value || '').replace(/\s+/g, ' ').trim().slice(0, 160);
        return true;
    }

    function referenceSlotTypesForContext(context='universal', fallbackRole=''){
        const all = normalizedReferenceSlotTypes();
        if(context !== 'try_on') return all;
        if(fallbackRole === 'source') return all.filter(item => item.role === 'subject');
        return all.filter(item => TRY_ON_SELECTABLE_REFERENCE_ROLES.has(item.role) && item.role !== 'subject');
    }

    function referenceTypeOptionsHtml(selected, context='universal', fallbackRole='', item=null){
        const options = referenceSlotTypesForContext(context, fallbackRole);
        const customLabel = customReferenceTypeLabel(item);
        return options.map(option => {
            const label = option.id === selected && customLabel ? customLabel : option.label;
            return `<option value="${escapeHtml(option.id)}" ${option.id === selected ? 'selected':''}>${escapeHtml(label)}</option>`;
        }).join('');
    }

    function referenceTypeComboHtml({selected, context='universal', fallbackRole='prop', item={}, dataAttr='', dataValue='', disabled=false}){
        const typeOptions = referenceTypeOptionsHtml(selected, context, fallbackRole, item);
        const typeDisplayLabel = referenceTypeDisplayLabel(item, fallbackRole);
        const disabledAttr = disabled ? 'disabled' : '';
        return `<div class="ec-reference-type-combo" data-reference-type-combo>
            <button type="button" class="ec-reference-type-button" data-reference-type-button aria-label="${escapeHtml(`${t('ecommerce.referenceType')} ${typeDisplayLabel}`)}" aria-disabled="${disabled ? 'true' : 'false'}" title="${escapeHtml(t('ecommerce.customReferenceTypePrompt'))}">
                <span class="ec-reference-type-label" data-reference-type-inline="${escapeHtml(dataValue)}">${escapeHtml(typeDisplayLabel)}</span><i aria-hidden="true">⌄</i>
            </button>
            <select class="ec-reference-type-native" ${dataAttr}="${escapeHtml(dataValue)}" ${disabledAttr} tabindex="-1" aria-hidden="true">${typeOptions}</select>
        </div>`;
    }

    function clearReferenceTypeOpenTimer(){
        if(!referenceTypeOpenTimer) return;
        window.clearTimeout(referenceTypeOpenTimer);
        referenceTypeOpenTimer = 0;
    }

    function openReferenceTypeSelect(select){
        if(!select || select.disabled) return;
        try { select.focus({preventScroll:true}); } catch(error) { select.focus(); }
        if(typeof select.showPicker === 'function') {
            try { select.showPicker(); return; } catch(error) {}
        }
        select.click?.();
    }

    function scheduleReferenceTypeSelectOpen(select){
        clearReferenceTypeOpenTimer();
        referenceTypeOpenTimer = window.setTimeout(() => {
            referenceTypeOpenTimer = 0;
            openReferenceTypeSelect(select);
        }, 240);
    }

    function beginReferenceTypeInlineEdit(select, item, fallbackRole='prop', onCommit=()=>{}){
        if(!select || !item) return false;
        const combo = select.closest('[data-reference-type-combo]');
        const button = combo?.querySelector('[data-reference-type-button]');
        if(!combo || !button || combo.classList.contains('is-editing')) return false;
        const input = document.createElement('input');
        input.type = 'text';
        input.maxLength = 160;
        input.className = 'ec-reference-type-inline-input';
        input.dataset.referenceTypeEditing = 'true';
        input.value = referenceTypeDisplayLabel(item, fallbackRole);
        input.setAttribute('aria-label', t('ecommerce.customReferenceTypePrompt'));
        combo.classList.add('is-editing');
        combo.appendChild(input);
        let done = false;
        const finish = commit => {
            if(done) return;
            done = true;
            const next = input.value;
            input.remove();
            combo.classList.remove('is-editing');
            if(commit && editReferenceTypeName(item, fallbackRole, next)) onCommit();
        };
        input.addEventListener('pointerdown', event => event.stopPropagation());
        input.addEventListener('click', event => event.stopPropagation());
        input.addEventListener('keydown', event => {
            if(event.key === 'Enter') { event.preventDefault(); finish(true); }
            if(event.key === 'Escape') { event.preventDefault(); finish(false); }
        });
        input.addEventListener('blur', () => finish(true));
        window.setTimeout(() => { input.focus(); input.select(); }, 0);
        return true;
    }

    function bindReferenceTypeInlineControls(select, itemGetter, fallbackRoleGetter, onCommit){
        const combo = select.closest('[data-reference-type-combo]');
        const button = combo?.querySelector('[data-reference-type-button]');
        const label = combo?.querySelector('[data-reference-type-inline]');
        button?.addEventListener('click', event => {
            if(event.detail > 1) return;
            scheduleReferenceTypeSelectOpen(select);
        });
        label?.addEventListener('dblclick', event => {
            event.preventDefault();
            event.stopPropagation();
            clearReferenceTypeOpenTimer();
            const item = itemGetter();
            if(!item) return;
            const fallbackRole = typeof fallbackRoleGetter === 'function' ? fallbackRoleGetter(item) : fallbackRoleGetter;
            beginReferenceTypeInlineEdit(select, item, fallbackRole || 'prop', onCommit);
        });
    }

    function applySlotTypeToInput(item, slotTypeId, fallbackRole='prop'){
        if(!item) return null;
        const selected = referenceSlotTypeById(slotTypeId) || referenceSlotTypeById(defaultSlotTypeIdForRole(fallbackRole));
        const role = selected?.role || (fallbackRole === 'source' ? 'subject' : fallbackRole);
        item.slot_type = selected?.id || role;
        item.reference_type = role;
        item.role = role;
        return item;
    }

    function reconcileUniversalSlotTypes(){
        const workspace = state.workspaces.universal;
        let changed = false;
        Object.values(workspace?.inputs || {}).forEach(item => {
            const selected = referenceSlotTypeById(item?.slot_type);
            if(!selected || (item.role === selected.role && item.reference_type === selected.role)) return;
            applySlotTypeToInput(item, selected.id, selected.role);
            changed = true;
        });
        return changed;
    }

    function universalReferenceRoles(){
        return referenceSlotTypesForContext('universal').map(item => ({id:item.id, role:item.role, label:item.label}));
    }

    function universalUploadHtml(key,item,label){
        const displayUrl = referenceDisplayUrl(item);
        if(displayUrl) {
            const status = item.uploading ? t('ecommerce.uploading') : formatName(item.name || displayUrl);
            return `<div class="ec-upload-preview ${item.uploading ? 'is-uploading' : ''}"><button type="button" class="ec-upload-image-trigger" data-preview-reference="${escapeHtml(key)}" title="${escapeHtml(t('ecommerce.openReferencePreview'))}"><img src="${escapeHtml(displayUrl)}" alt="${escapeHtml(label)}"></button><div class="ec-upload-info"><b>${escapeHtml(label)}</b><span title="${escapeHtml(item.name || displayUrl)}">${escapeHtml(status)}</span><div class="ec-upload-actions"><button type="button" data-action="upload">${escapeHtml(t('ecommerce.replace'))}</button><button type="button" data-action="assets">${escapeHtml(t('ecommerce.fromAssets'))}</button><button type="button" data-action="remove">${escapeHtml(t('ecommerce.remove'))}</button></div></div></div>`;
        }
        return `<div class="ec-upload-empty" data-action="upload" role="button" tabindex="0"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4M7 9l5-5 5 5M5 20h14"></path></svg><b>${escapeHtml(label)}</b><small>${escapeHtml(t('ecommerce.dropOrChoose'))}</small><span class="ec-upload-actions"><button type="button" data-action="assets">${escapeHtml(t('ecommerce.fromAssets'))}</button></span></div>`;
    }

    function universalUploadLabel(role, fallback){
        const key = {
            subject:'ecommerce.presetModel',
            model_identity:'ecommerce.presetModelIdentity',
            full_garment:'ecommerce.presetGarment',
            shoes:'ecommerce.presetShoes',
            accessory:'ecommerce.presetAccessory',
            prop:'ecommerce.presetProp',
            scene_prop:'ecommerce.presetSceneProp',
            detail:'ecommerce.presetDetail',
            pose:'ecommerce.presetPose',
            scene:'ecommerce.presetScene',
            style:'ecommerce.presetStyle',
        }[role];
        return key ? t(key) : fallback;
    }

    function updateUniversalAddButton(count, limit){
        if(!el.addUniversalReference) return;
        const universal = Boolean(currentConfig()?.universal);
        el.addUniversalReference.classList.toggle('hidden', !universal);
        el.addUniversalReference.disabled = !universal || count >= limit;
        el.addUniversalReference.innerHTML = `<span>＋ ${escapeHtml(t('ecommerce.addReference'))}</span><small>${count}/${limit}</small>`;
    }

    function selectorValue(value){
        return String(value || '').replace(/\\/g, '\\\\').replace(/"/g, '\\"');
    }

    function matchingEditingControl(control){
        if(control?.isConnected) return control;
        const option = control?.dataset?.option || control?.option;
        if(option) return el.operationControls?.querySelector(`[data-option="${selectorValue(option)}"]`);
        const referenceField = control?.dataset?.referenceField || control?.referenceField;
        const referenceKey = control?.dataset?.referenceKey || control?.referenceKey;
        if(referenceField && referenceKey) {
            return el.inputSlots?.querySelector(`[data-reference-field="${selectorValue(referenceField)}"][data-reference-key="${selectorValue(referenceKey)}"]`);
        }
        return null;
    }

    function restoreEditingFocus(control){
        const marker = {
            control,
            option:control?.dataset?.option || '',
            referenceField:control?.dataset?.referenceField || '',
            referenceKey:control?.dataset?.referenceKey || '',
            selectionStart:typeof control?.selectionStart === 'number' ? control.selectionStart : null,
            selectionEnd:typeof control?.selectionEnd === 'number' ? control.selectionEnd : null,
            requestedAt:Date.now(),
        };
        [0, 80, 260].forEach(delay => setTimeout(() => {
            if(state.lastPointerDownAt > marker.requestedAt) return;
            const target = matchingEditingControl(marker);
            if(!target || document.activeElement === target) return;
            const active = document.activeElement;
            if(active && active !== document.body && active !== document.documentElement && isTextEditingElement(active)) return;
            try { target.focus({preventScroll:true}); } catch(e) { target.focus(); }
            if(typeof target.setSelectionRange === 'function') {
                const end = Number(target.value?.length || 0);
                const start = Number.isFinite(marker.selectionStart) ? Math.min(marker.selectionStart, end) : end;
                const finish = Number.isFinite(marker.selectionEnd) ? Math.min(marker.selectionEnd, end) : start;
                try { target.setSelectionRange(start, finish); } catch(e) {}
            }
        }, delay));
    }

    function bindComposingInput(control, update){
        let composing = false;
        control.addEventListener('compositionstart', () => { composing = true; });
        control.addEventListener('compositionend', () => { composing = false; update(); restoreEditingFocus(control); });
        control.addEventListener('input', () => { if(!composing) { update(); restoreEditingFocus(control); } });
    }

    function renderUniversalInputs(){
        seedUniversalPresetsIfEmpty();
        const entries = universalEntries();
        const limit = Number(state.capabilities?.universal_reference_limit || 14);
        const roles = universalReferenceRoles();
        const uploadedEntries = entries.filter(([,item]) => item.url);
        const plan = resolveUniversalReferencePlan();
        const manyReferences = entries.length > 6;
        el.ecommercePage?.classList.toggle('has-many-universal-references', manyReferences);
        el.universalDock?.classList.toggle('has-many-references', manyReferences);
        el.inputSlots?.classList.toggle('has-studio-reference', !IS_FREE_CREATION);
        const guideTitleKey = IS_FREE_CREATION ? 'freeCreation.guideTitle' : 'ecommerce.universalGuideTitle';
        const guideHintKey = IS_FREE_CREATION ? 'freeCreation.guideHint' : 'ecommerce.universalGuideHint';
        el.inputSlots.innerHTML = `<div class="ec-universal-guide"><strong>${escapeHtml(t(guideTitleKey))}</strong><p>${escapeHtml(t(guideHintKey))}</p></div>` + entries.map(([key,item],index) => {
            const selected = selectedSlotTypeId(item, item.reference_type || item.role || 'prop');
            const selectedType = referenceSlotTypeById(selected) || roles[0] || {};
            const role = selectedType.role || item.reference_type || item.role || 'prop';
            const roleLabel = selectedType.label || roles.find(item => item.role === role || item.id === role)?.label || role;
            const uploadLabel = universalUploadLabel(role, roleLabel);
            return `<article class="ec-universal-reference" data-reference-key="${escapeHtml(key)}" data-reference-role="${escapeHtml(role)}" data-reference-index="${index + 1}">
                <header><span class="ec-drag-handle" draggable="true" data-reference-drag-handle="${escapeHtml(key)}" title="${escapeHtml(t('ecommerce.dragReorder'))}">⋮⋮</span><b>${escapeHtml(t('ecommerce.imageNumber',{count:index + 1}))}</b><button type="button" data-remove-reference="${escapeHtml(key)}" aria-label="${escapeHtml(t('ecommerce.remove'))}">×</button></header>
                <div class="ec-upload-slot ${role==='subject' && !IS_FREE_CREATION?'required':''}" data-role="${escapeHtml(key)}">${universalUploadHtml(key,item,uploadLabel)}</div>
                <label class="ec-reference-type-row"><span>${escapeHtml(t('ecommerce.referenceType'))}</span>${referenceTypeComboHtml({selected, context:'universal', fallbackRole:role, item, dataAttr:'data-reference-type', dataValue:key})}</label>
                ${universalDetailTargetHtml(item, plan)}
                <div class="ec-reference-fields"><label><span>${escapeHtml(t('ecommerce.referenceLabel'))}</span><input data-reference-field="label" data-reference-key="${escapeHtml(key)}" maxlength="160" value="${escapeHtml(item.label || '')}" placeholder="${escapeHtml(t('ecommerce.referenceLabelHint'))}"></label><label><span>${escapeHtml(t('ecommerce.referenceInstruction'))}</span><input data-reference-field="instruction" data-reference-key="${escapeHtml(key)}" maxlength="300" value="${escapeHtml(item.instruction || '')}" placeholder="${escapeHtml(t('ecommerce.referenceInstructionHint'))}"></label></div>
            </article>`;
        }).join('') + (IS_FREE_CREATION ? '' : studioReferenceCardHtml('universal'));
        el.inputProgress.textContent = `${uploadedEntries.length}/${limit}`;
        updateUniversalAddButton(entries.length, limit);
        bindInputSlots();
        bindUniversalControls(limit);
        if(!IS_FREE_CREATION) bindStudioReferenceControls();
        syncUniversalPromptModeUi();
        if(state.capabilities) {
            populateModelSelectors();
            updateRouteSummary();
        }
    }

    function tryOnInputConfig(role){
        return currentConfig().inputs.find(input => input.role === role) || TRY_ON_WARDROBE_ROLES.find(item => item.role === role);
    }

    function tryOnOutfitEntries(){
        const entries = orderedTryOnWardrobeRoles()
            .filter(item => TRY_ON_OUTFIT_ROLES.some(base => base.role === tryOnRequestRoleForSlot(item.role, state.inputs[item.role])))
            .map(item => [item.role, state.inputs[item.role], item]);
        if(state.inputs.garment?.url && !entries.some(([,asset]) => asset?.url)) {
            entries.push(['garment', state.inputs.garment, {role:'garment', labelKey:'ecommerce.garmentImage', stageKey:'ecommerce.tryOnGarmentStage', number:'02'}]);
        }
        return entries;
    }

    function tryOnOutfitCount(){
        return tryOnOutfitEntries().filter(([,asset]) => asset?.url).length;
    }

    function tryOnReady(){
        return Boolean(state.inputs.source?.url) && tryOnOutfitCount() > 0;
    }

    function tryOnSlotOrder(){
        const base = TRY_ON_WARDROBE_ROLES.map(item => item.role);
        const saved = Array.isArray(currentOptions().slot_order) ? currentOptions().slot_order : [];
        const ordered = saved.filter(role => base.includes(role));
        base.forEach(role => { if(!ordered.includes(role)) ordered.push(role); });
        currentOptions().slot_order = ordered;
        return ordered;
    }

    function orderedTryOnWardrobeRoles(){
        const order = tryOnSlotOrder();
        return order.map(role => TRY_ON_WARDROBE_ROLES.find(item => item.role === role)).filter(Boolean);
    }

    function tryOnSlotHasUserContent(role){
        const item = state.inputs[role];
        if(!item) return false;
        const alternates = Array.isArray(item.alternates) ? item.alternates : [];
        return Boolean(
            item.url || item.preview_url || alternates.some(candidate => candidate?.url || candidate?.preview_url)
            || String(item.label || '').trim() || String(item.instruction || '').trim() || String(item.custom_type_label || '').trim()
            || (item.slot_type && item.slot_type !== defaultSlotTypeIdForRole(role))
        );
    }

    function visibleTryOnWardrobeRoles(){
        const ordered = orderedTryOnWardrobeRoles();
        const configured = Number(currentOptions().visible_slot_count);
        const requested = Number.isFinite(configured) ? Math.trunc(configured) : TRY_ON_DEFAULT_WARDROBE_SLOT_COUNT;
        const visibleCount = Math.max(TRY_ON_DEFAULT_WARDROBE_SLOT_COUNT, Math.min(ordered.length, requested));
        currentOptions().visible_slot_count = visibleCount;
        const visible = ordered.slice(0, visibleCount);
        ordered.slice(visibleCount).forEach(item => {
            if(tryOnSlotHasUserContent(item.role)) visible.push(item);
        });
        return visible;
    }

    function addTryOnReferenceSlot(){
        const ordered = orderedTryOnWardrobeRoles();
        const visibleRoles = new Set(visibleTryOnWardrobeRoles().map(item => item.role));
        const nextIndex = ordered.findIndex(item => !visibleRoles.has(item.role));
        if(nextIndex < 0) return false;
        currentOptions().visible_slot_count = Math.max(Number(currentOptions().visible_slot_count) || 0, nextIndex + 1);
        renderInputs();
        persistSettings();
        return true;
    }

    function tryOnInputEntriesForRequest(){
        const entries = [['source', state.inputs.source]];
        const orderedWardrobe = orderedTryOnWardrobeRoles();
        const visibleOutfit = orderedWardrobe.some(item => state.inputs[item.role]?.url);
        if(state.inputs.garment?.url && !visibleOutfit) entries.push(['garment', state.inputs.garment]);
        orderedWardrobe.forEach(item => entries.push([item.role, state.inputs[item.role]]));
        return entries;
    }

    function tryOnRequestRoleForSlot(slotRole, item={}){
        if(slotRole === 'source') return 'source';
        const selectedType = referenceSlotTypeById(item?.slot_type) || referenceSlotTypeById(item?.reference_type) || referenceSlotTypeById(slotRole);
        const role = selectedType?.role || item?.reference_type || slotRole;
        if(role === 'subject') return 'source';
        if(role === 'prop') return 'accessory';
        return TRY_ON_REQUEST_ROLES.includes(role) || role === 'garment' ? role : slotRole;
    }

    function tryOnSlotReferenceType(slotRole, item=state.inputs[slotRole] || {}){
        return referenceSlotTypeById(item?.slot_type) || referenceSlotTypeById(item?.reference_type) || referenceSlotTypeById(slotRole);
    }

    function tryOnSlotDisplayLabel(input, item=state.inputs[input?.role] || {}){
        const slotRole = input?.role || '';
        return referenceTypeDisplayLabel(item, slotRole) || t(input?.labelKey || input?.stageKey || 'ecommerce.garmentImage');
    }

    function tryOnSlotKickerLabel(input, stageKey){
        const slotRole = input?.role || '';
        const custom = customReferenceTypeLabel(state.inputs[slotRole]);
        if(custom) return custom;
        const selectedType = tryOnSlotReferenceType(slotRole);
        const defaultTypeId = defaultSlotTypeIdForRole(slotRole);
        if(selectedType?.label && selectedType.id !== defaultTypeId) return selectedType.label;
        return t(stageKey || input?.stageKey || input?.labelKey || 'ecommerce.garmentImage');
    }

    function isTryOnReferenceRole(role){
        return TRY_ON_MULTI_REFERENCE_ROLES.includes(String(role || ''));
    }

    function tryOnReferenceCandidates(item){
        return cleanInputCandidates(item);
    }

    function tryOnSelectedReferenceIndex(item, candidates=tryOnReferenceCandidates(item)){
        if(!candidates.length) return 0;
        const selectedKey = item?.url || item?.preview_url || '';
        const byKey = candidates.findIndex(candidate => (candidate.url || candidate.preview_url) === selectedKey);
        if(byKey >= 0) return byKey;
        const raw = Number(item?.selected_index || 0);
        return Math.max(0, Math.min(candidates.length - 1, Number.isFinite(raw) ? raw : 0));
    }

    function tryOnSwitchMeta(direction, fromItem){
        const from = cleanInputCandidate(fromItem);
        return {
            direction:Number(direction || 0) < 0 ? -1 : 1,
            token:Date.now(),
            from:referenceDisplayUrl(from) ? from : null,
        };
    }

    function buildTryOnInput(role, base={}, candidates=[], selectedIndex=0){
        const safeIndex = Math.max(0, Math.min(candidates.length - 1, Number(selectedIndex) || 0));
        const selected = candidates[safeIndex] || {};
        const slotType = base.slot_type || selected.slot_type || defaultSlotTypeIdForRole(role);
        const slotMeta = referenceSlotTypeById(slotType);
        return {
            ...base,
            ...selected,
            role,
            reference_id:base.reference_id || role,
            reference_type:slotMeta?.role || base.reference_type || (role === 'source' ? 'subject' : role),
            slot_type:slotMeta?.id || slotType,
            custom_type_label:base.custom_type_label || selected.custom_type_label || '',
            label:base.label || '',
            instruction:base.instruction || '',
            alternates:candidates,
            selected_index:safeIndex,
        };
    }

    function setTryOnInputCandidate(role, candidate){
        if(!isTryOnReferenceRole(role)) return null;
        const normalized = cleanInputCandidate(candidate);
        const normalizedKey = normalized?.url || normalized?.preview_url || '';
        if(!normalizedKey) return null;
        const existing = state.inputs[role] || {};
        const candidates = tryOnReferenceCandidates(existing);
        const currentIndex = tryOnSelectedReferenceIndex(existing, candidates);
        const fromCandidate = candidates[currentIndex] || cleanInputCandidate(existing);
        let nextIndex = candidates.findIndex(item => (item.url || item.preview_url) === normalizedKey || (normalized.upload_token && item.upload_token === normalized.upload_token));
        if(nextIndex >= 0) candidates[nextIndex] = {...candidates[nextIndex], ...normalized};
        else {
            candidates.push(normalized);
            nextIndex = candidates.length - 1;
        }
        state.tryOnSwitches[role] = tryOnSwitchMeta(nextIndex >= currentIndex ? 1 : -1, fromCandidate);
        state.inputs[role] = buildTryOnInput(role, existing, candidates, nextIndex);
        return state.inputs[role];
    }

    function syncTryOnCurrentCandidate(role){
        if(state.operation !== 'try_on' || !isTryOnReferenceRole(role)) return;
        const item = state.inputs[role];
        const selected = cleanInputCandidate(item);
        if(!referenceDisplayUrl(selected)) return;
        const candidates = tryOnReferenceCandidates(item);
        const selectedIndex = tryOnSelectedReferenceIndex(item, candidates);
        if(candidates[selectedIndex]) candidates[selectedIndex] = selected;
        state.inputs[role] = buildTryOnInput(role, item, candidates, selectedIndex);
    }

    function removeTryOnSelectedCandidate(role){
        if(state.operation !== 'try_on' || !isTryOnReferenceRole(role)) return false;
        const existing = state.inputs[role];
        const candidates = tryOnReferenceCandidates(existing);
        if(!candidates.length) return false;
        const selectedIndex = tryOnSelectedReferenceIndex(existing, candidates);
        revokeReferencePreviewUrl(candidates[selectedIndex] || existing);
        if(candidates.length <= 1) {
            const slotType = existing?.slot_type || defaultSlotTypeIdForRole(role);
            const slotMeta = referenceSlotTypeById(slotType);
            state.inputs[role] = {
                role:slotMeta?.role || (role === 'source' ? 'subject' : role),
                reference_type:slotMeta?.role || (role === 'source' ? 'subject' : role),
                slot_type:slotMeta?.id || slotType,
                reference_id:existing?.reference_id || role,
                custom_type_label:existing?.custom_type_label || '',
                label:existing?.label || '',
                instruction:existing?.instruction || '',
                url:'',
                name:'',
                kind:'image',
                mime:'',
                width:0,
                height:0,
                original_url:'',
                original_name:'',
                original_width:0,
                original_height:0,
                crop_history:[],
            };
            delete state.tryOnSwitches[role];
            return true;
        }
        const fromCandidate = candidates[selectedIndex] || cleanInputCandidate(existing);
        candidates.splice(selectedIndex, 1);
        const nextIndex = Math.max(0, Math.min(candidates.length - 1, selectedIndex));
        state.tryOnSwitches[role] = tryOnSwitchMeta(-1, fromCandidate);
        state.inputs[role] = buildTryOnInput(role, existing, candidates, nextIndex);
        return true;
    }

    function focusTryOnSlot(role){
        requestAnimationFrame(() => {
            const slot = el.inputSlots?.querySelector(`.ec-upload-slot[data-role="${selectorValue(role)}"]`);
            if(!slot) return;
            try { slot.focus({preventScroll:true}); } catch(error) { slot.focus(); }
        });
    }

    function selectTryOnReference(role, index, direction=0){
        if(state.operation !== 'try_on' || !isTryOnReferenceRole(role)) return false;
        const existing = state.inputs[role];
        const candidates = tryOnReferenceCandidates(existing);
        if(candidates.length <= 1) return false;
        const currentIndex = tryOnSelectedReferenceIndex(existing, candidates);
        const nextIndex = ((Number(index) || 0) % candidates.length + candidates.length) % candidates.length;
        if(nextIndex === currentIndex) return false;
        state.tryOnSwitches[role] = tryOnSwitchMeta(direction || (nextIndex > currentIndex ? 1 : -1), candidates[currentIndex] || existing);
        state.inputs[role] = buildTryOnInput(role, existing, candidates, nextIndex);
        renderInputs();
        validateForm(false);
        persistSettings();
        focusTryOnSlot(role);
        return true;
    }

    function shiftTryOnReference(role, step){
        const item = state.inputs[role];
        const candidates = tryOnReferenceCandidates(item);
        if(candidates.length <= 1) return false;
        const currentIndex = tryOnSelectedReferenceIndex(item, candidates);
        return selectTryOnReference(role, currentIndex + Number(step || 0), Number(step || 0));
    }

    function tryOnReferenceTypeRow(role){
        const item = state.inputs[role] || {};
        const selected = selectedSlotTypeId(item, role);
        const disabled = referenceSlotTypesForContext('try_on', role).length <= 1 ? 'disabled' : '';
        return `<label class="ec-reference-type-row ec-tryon-type-row"><span>${escapeHtml(t('ecommerce.referenceType'))}</span>${referenceTypeComboHtml({selected, context:'try_on', fallbackRole:role, item, dataAttr:'data-tryon-reference-type', dataValue:role, disabled:Boolean(disabled)})}</label>`;
    }

    function tryOnWardrobeCard(item){
        const input = tryOnInputConfig(item.role) || item;
        const kickerLabel = tryOnSlotKickerLabel(input, item.stageKey);
        return `<div class="ec-tryon-slot-card is-outfit" data-tryon-wardrobe-role="${escapeHtml(item.role)}" data-tryon-sort-role="${escapeHtml(item.role)}">
            <div class="ec-tryon-card-kicker"><b>${escapeHtml(item.number)}</b><span>${escapeHtml(kickerLabel)}</span><button type="button" class="ec-tryon-drag-handle" draggable="true" data-tryon-drag-handle="${escapeHtml(item.role)}" title="${escapeHtml(t('ecommerce.dragReorder'))}" aria-label="${escapeHtml(t('ecommerce.dragReorder'))}">⋮⋮</button></div>
            ${inputSlotHtml(input)}
            ${tryOnReferenceTypeRow(item.role)}
        </div>`;
    }

    function tryOnReorderedPreviewOrder(draggedRole, targetRole){
        const order = tryOnSlotOrder().slice();
        const from = order.indexOf(draggedRole);
        const to = order.indexOf(targetRole);
        if(from < 0 || to < 0 || from === to) return null;
        order.splice(to, 0, order.splice(from, 1)[0]);
        return order;
    }

    function clearTryOnDragPreview(){
        const grid = el.inputSlots?.querySelector('.ec-tryon-closet-grid');
        grid?.classList.remove('is-reordering');
        el.inputSlots?.querySelectorAll('[data-tryon-sort-role]').forEach(card => {
            card.style.transform = '';
            card.classList.remove('drag-target', 'is-drag-preview');
        });
    }

    function updateTryOnDragPreview(draggedRole, targetRole){
        const grid = el.inputSlots?.querySelector('.ec-tryon-closet-grid');
        const cards = Array.from(grid?.querySelectorAll('[data-tryon-sort-role]') || []);
        cards.forEach(card => {
            if(!card.classList.contains('dragging')) card.style.transform = '';
            card.classList.remove('drag-target', 'is-drag-preview');
        });
        const previewOrder = tryOnReorderedPreviewOrder(draggedRole, targetRole);
        if(!grid || !previewOrder) {
            grid?.classList.remove('is-reordering');
            return;
        }
        const currentOrder = tryOnSlotOrder();
        const byRole = new Map(cards.map(card => [card.dataset.tryonSortRole || '', card]));
        const rects = new Map(cards.map(card => [card.dataset.tryonSortRole || '', card.getBoundingClientRect()]));
        grid.classList.add('is-reordering');
        previewOrder.forEach((role, index) => {
            if(role === draggedRole) return;
            const card = byRole.get(role);
            const currentRect = rects.get(role);
            const targetRect = rects.get(currentOrder[index]);
            if(!card || !currentRect || !targetRect) return;
            const dx = targetRect.left - currentRect.left;
            const dy = targetRect.top - currentRect.top;
            card.style.transform = `translate(${Math.round(dx)}px,${Math.round(dy)}px)`;
            card.classList.add('is-drag-preview');
        });
        byRole.get(targetRole)?.classList.add('drag-target');
    }

    function bindTryOnSlotControls(){
        el.inputSlots.querySelector('[data-add-tryon-reference]')?.addEventListener('click', addTryOnReferenceSlot);
        el.inputSlots.querySelectorAll('[data-tryon-reference-type]').forEach(select => {
            const role = select.dataset.tryonReferenceType || '';
            bindReferenceTypeInlineControls(select, () => {
                if(!role) return null;
                if(!state.inputs[role]) {
                    const fallback = role === 'source' ? 'subject' : role;
                    state.inputs[role] = applySlotTypeToInput({role:fallback, reference_type:fallback, reference_id:role, label:'', instruction:''}, selectedSlotTypeId({}, role), role);
                }
                return state.inputs[role];
            }, role, () => {
                renderInputs();
                validateForm(false);
                persistSettings();
            });
            select.addEventListener('change', () => {
                if(!role) return;
                const existing = state.inputs[role] || {};
                state.inputs[role] = applySlotTypeToInput({
                    role:existing.role || role,
                    reference_type:existing.reference_type || (role === 'source' ? 'subject' : role),
                    reference_id:existing.reference_id || role,
                    label:existing.label || '',
                    instruction:existing.instruction || '',
                    ...existing,
                }, select.value, role);
                renderInputs();
                validateForm(false);
                persistSettings();
            });
        });
        let draggedRole = '';
        let dragTargetRole = '';
        el.inputSlots.querySelectorAll('[data-tryon-sort-role]').forEach(card => {
            const handle = card.querySelector('[data-tryon-drag-handle]');
            handle?.addEventListener('dragstart', event => {
                draggedRole = handle.dataset.tryonDragHandle || card.dataset.tryonSortRole || '';
                dragTargetRole = '';
                card.classList.add('dragging');
                event.dataTransfer.effectAllowed = 'move';
            });
            handle?.addEventListener('dragend', () => {
                draggedRole = '';
                dragTargetRole = '';
                card.classList.remove('dragging');
                clearTryOnDragPreview();
            });
            card.addEventListener('dragover', event => {
                if(!draggedRole) return;
                event.preventDefault();
                event.dataTransfer.dropEffect = 'move';
                dragTargetRole = card.dataset.tryonSortRole || '';
                updateTryOnDragPreview(draggedRole, dragTargetRole);
            });
            card.addEventListener('drop', event => {
                event.preventDefault();
                const targetRole = dragTargetRole || card.dataset.tryonSortRole || '';
                const order = tryOnReorderedPreviewOrder(draggedRole, targetRole);
                if(!order) { clearTryOnDragPreview(); return; }
                currentOptions().slot_order = order;
                draggedRole = '';
                dragTargetRole = '';
                renderInputs();
                persistSettings();
            });
        });
    }

    function renderTryOnInputs(){
        const config = currentConfig();
        const sourceInput = config.inputs.find(input => input.role === 'source') || config.inputs[0];
        const sourceReady = Boolean(state.inputs.source?.url);
        const outfitCount = tryOnOutfitCount();
        const ready = tryOnReady();
        const visibleWardrobe = visibleTryOnWardrobeRoles();
        const visibleReferenceCount = 1 + visibleWardrobe.length;
        const referenceLimit = 1 + TRY_ON_WARDROBE_ROLES.length;
        const canAddReference = visibleWardrobe.length < TRY_ON_WARDROBE_ROLES.length;
        const completedVisibleReferences = Number(sourceReady) + visibleWardrobe.filter(item => state.inputs[item.role]?.url).length;
        const steps = [
            {number:'01', label:t('ecommerce.tryOnStepModel'), className:sourceReady ? 'complete' : 'active'},
            {number:'02', label:t('ecommerce.tryOnStepGarment'), className:outfitCount ? 'complete' : (sourceReady ? 'active' : '')},
            {number:'03', label:t('ecommerce.tryOnPreviewTitle'), className:outfitCount ? 'active' : ''},
            {number:'04', label:t('ecommerce.tryOnStepGenerate'), className:ready ? 'active' : ''},
        ];
        const stepHtml = steps.map(step => `<span class="${escapeHtml(step.className)}"><b>${escapeHtml(step.number)}</b>${escapeHtml(step.label)}</span>`).join('');
        el.inputSlots.innerHTML = `<section class="ec-tryon-studio" aria-label="${escapeHtml(t('ecommerce.tryOnAtelier'))}">
            <div class="ec-tryon-stepbar">${stepHtml}</div>
            <div class="ec-tryon-materials">
                <div class="ec-tryon-reference-grid ec-tryon-closet-grid" aria-label="${escapeHtml(t('ecommerce.tryOnWardrobe'))}">
                    <div class="ec-tryon-slot-card is-model">
                        <div class="ec-tryon-card-kicker"><b>01</b><span>${escapeHtml(t('ecommerce.tryOnModelStage'))}</span></div>
                        ${inputSlotHtml(sourceInput)}
                        ${tryOnReferenceTypeRow('source')}
                    </div>
                    ${visibleWardrobe.map(tryOnWardrobeCard).join('')}
                    ${studioReferenceCardHtml('try_on')}
                </div>
                ${canAddReference ? `<button type="button" class="ec-tryon-add-reference" data-add-tryon-reference><span>＋ ${escapeHtml(t('ecommerce.addReference'))}</span><small>${visibleReferenceCount}/${referenceLimit}</small></button>` : ''}
            </div>
        </section>`;
        el.inputProgress.textContent = `${completedVisibleReferences}/${visibleReferenceCount}`;
        bindInputSlots();
        bindTryOnSlotControls();
        bindStudioReferenceControls();
        syncTryOnLookPreview();
    }

    function tryOnPreviewItems(){
        const items = orderedTryOnWardrobeRoles().slice();
        const hasStructuredOutfit = TRY_ON_OUTFIT_ROLES.some(item => state.inputs[item.role]?.url);
        if(state.inputs.garment?.url && !hasStructuredOutfit) {
            items.push({role:'garment', labelKey:'ecommerce.garmentImage', stageKey:'ecommerce.tryOnGarmentStage', number:'02'});
        }
        return items;
    }

    function tryOnPreviewItemHtml(item){
        const asset = state.inputs[item.role];
        const selected = Boolean(asset?.url);
        const label = tryOnSlotDisplayLabel(item, asset);
        const candidates = tryOnReferenceCandidates(asset);
        const selectedIndex = tryOnSelectedReferenceIndex(asset, candidates);
        const thumbnail = selected
            ? `<img src="${escapeHtml(asset.url)}" alt="${escapeHtml(label)}" data-tryon-cutout-src="${escapeHtml(asset.url)}">`
            : `<span aria-hidden="true"></span>`;
        return `<article class="ec-tryon-look-item ${selected ? 'is-selected' : 'is-empty'} is-${escapeHtml(item.role)}">
            <div class="ec-tryon-look-thumb">${thumbnail}${candidates.length > 1 ? `<em>${selectedIndex + 1}/${candidates.length}</em>` : ''}</div>
            <div class="ec-tryon-look-caption"><b>${escapeHtml(item.number || '')}</b><span>${escapeHtml(label)}</span><small>${escapeHtml(t(selected ? 'ecommerce.tryOnItemReady' : 'ecommerce.tryOnItemEmpty'))}</small></div>
        </article>`;
    }

    function tryOnAnchorHtml(item){
        const selected = Boolean(state.inputs[item.role]?.url);
        const label = tryOnSlotDisplayLabel(item);
        return `<span class="ec-tryon-body-anchor is-${escapeHtml(item.role)} ${selected ? 'is-selected' : ''}"><i></i><b>${escapeHtml(label)}</b></span>`;
    }

    function syncTryOnLookPreview(){
        if(!el.emptyResult) return;
        const active = state.operation === 'try_on';
        el.emptyResult.classList.toggle('has-tryon-preview', active);
        let stage = byId('tryOnLookPreview');
        if(!active) {
            stage?.remove();
            return;
        }
        if(!stage) {
            stage = document.createElement('div');
            stage.id = 'tryOnLookPreview';
            el.emptyResult.appendChild(stage);
        }
        const source = state.inputs.source;
        const outfitEntries = tryOnOutfitEntries().filter(([,asset]) => asset?.url);
        const sourceLayer = source?.url
            ? `<img class="ec-tryon-look-model" src="${escapeHtml(source.url)}" alt="${escapeHtml(t('ecommerce.modelImage'))}">`
            : `<div class="ec-tryon-look-mannequin" aria-hidden="true"><span></span></div>`;
        const previewItems = tryOnPreviewItems();
        const anchors = TRY_ON_OUTFIT_ROLES.map(tryOnAnchorHtml).join('');
        const itemCards = previewItems.map(tryOnPreviewItemHtml).join('');
        stage.innerHTML = `<section class="ec-tryon-look-stage">
            <header><div><small>LOOK STAGE</small><h3>${escapeHtml(t('ecommerce.tryOnPreviewTitle'))}</h3></div><em>${escapeHtml(t(source?.url ? (outfitEntries.length ? 'ecommerce.tryOnPreviewReady' : 'ecommerce.tryOnPreviewNeedOutfit') : 'ecommerce.tryOnPreviewNeedModel'))}</em></header>
            <div class="ec-tryon-dressup-board" aria-label="${escapeHtml(t('ecommerce.tryOnPreviewTitle'))}">
                <div class="ec-tryon-model-panel">
                    <div class="ec-tryon-body-guide" aria-hidden="true"></div>
                    <div class="ec-tryon-model-shell">
                        ${sourceLayer}
                        ${anchors}
                    </div>
                </div>
                <aside class="ec-tryon-look-rail" aria-label="${escapeHtml(t('ecommerce.tryOnLookRail'))}">
                    <div class="ec-tryon-look-rail-head"><span>${escapeHtml(t('ecommerce.tryOnLookRail'))}</span><b>${outfitEntries.length}/${previewItems.length}</b></div>
                    <div class="ec-tryon-look-items">${itemCards}</div>
                </aside>
            </div>
            <p>${escapeHtml(t('ecommerce.tryOnPreviewBoardHint'))}</p>
        </section>`;
        requestAnimationFrame(applyTryOnPreviewCutouts);
    }

    function backgroundDistance(pixel, bg){
        const dr = pixel[0] - bg[0];
        const dg = pixel[1] - bg[1];
        const db = pixel[2] - bg[2];
        return Math.sqrt(dr * dr + dg * dg + db * db);
    }

    function cutoutTryOnPreviewImage(url){
        if(tryOnCutoutCache.has(url)) return tryOnCutoutCache.get(url);
        const promise = new Promise(resolve => {
            const image = new Image();
            image.crossOrigin = 'anonymous';
            image.onload = () => {
                try {
                    const maxSide = 720;
                    const scale = Math.min(1, maxSide / Math.max(image.naturalWidth || 1, image.naturalHeight || 1));
                    const width = Math.max(1, Math.round((image.naturalWidth || 1) * scale));
                    const height = Math.max(1, Math.round((image.naturalHeight || 1) * scale));
                    const canvas = document.createElement('canvas');
                    canvas.width = width;
                    canvas.height = height;
                    const ctx = canvas.getContext('2d', {willReadFrequently:true});
                    ctx.drawImage(image, 0, 0, width, height);
                    const data = ctx.getImageData(0, 0, width, height);
                    const pixels = data.data;
                    const samples = [];
                    const sampleSize = Math.max(2, Math.round(Math.min(width, height) * .035));
                    const sampleCorner = (startX, startY) => {
                        for(let y = 0; y < sampleSize; y++) {
                            for(let x = 0; x < sampleSize; x++) {
                                const px = Math.min(width - 1, startX + x);
                                const py = Math.min(height - 1, startY + y);
                                const offset = (py * width + px) * 4;
                                if(pixels[offset + 3] > 16) samples.push([pixels[offset], pixels[offset + 1], pixels[offset + 2]]);
                            }
                        }
                    };
                    sampleCorner(0, 0);
                    sampleCorner(Math.max(0, width - sampleSize), 0);
                    sampleCorner(0, Math.max(0, height - sampleSize));
                    sampleCorner(Math.max(0, width - sampleSize), Math.max(0, height - sampleSize));
                    if(!samples.length) return resolve(url);
                    const bg = samples.reduce((acc, item) => [acc[0] + item[0], acc[1] + item[1], acc[2] + item[2]], [0,0,0]).map(value => value / samples.length);
                    for(let index = 0; index < pixels.length; index += 4) {
                        const distance = backgroundDistance([pixels[index], pixels[index + 1], pixels[index + 2]], bg);
                        if(distance < 30) pixels[index + 3] = 0;
                        else if(distance < 82) pixels[index + 3] = Math.round(pixels[index + 3] * ((distance - 30) / 52));
                    }
                    ctx.putImageData(data, 0, 0);
                    resolve(canvas.toDataURL('image/png'));
                } catch(error) {
                    resolve(url);
                }
            };
            image.onerror = () => resolve(url);
            image.src = url;
        });
        tryOnCutoutCache.set(url, promise);
        return promise;
    }

    function applyTryOnPreviewCutouts(){
        if(state.operation !== 'try_on') return;
        el.emptyResult?.querySelectorAll('[data-tryon-cutout-src]').forEach(image => {
            const original = image.dataset.tryonCutoutSrc || '';
            if(!original || image.dataset.tryonCutoutApplied === original) return;
            image.dataset.tryonCutoutApplied = original;
            cutoutTryOnPreviewImage(original).then(url => {
                if(image.dataset.tryonCutoutApplied !== original) return;
                image.src = url;
                image.classList.add('is-cutout');
            });
        });
    }

    function bindUniversalControls(limit){
        el.inputSlots.querySelectorAll('[data-reference-type]').forEach(select => {
            const key = select.dataset.referenceType || '';
            const afterCommit = () => {
                renderUniversalInputs();
                persistSettings();
                validateForm(false);
            };
            bindReferenceTypeInlineControls(select, () => state.inputs[key], item => item?.reference_type || item?.role || 'prop', afterCommit);
            select.addEventListener('change', () => {
                const item = state.inputs[key];
                if(item){
                    applySlotTypeToInput(item, select.value, item.reference_type || item.role || 'prop');
                    if(item.reference_type !== 'detail') delete item.detail_target_id;
                    if(item.reference_type === 'scene' && currentOptions().studio_reference) {
                        currentOptions().studio_reference = '';
                        showToast(t('ecommerce.sceneReplacedStudio'));
                    }
                    renderUniversalInputs(); persistSettings(); validateForm(false);
                }
            });
        });
        el.inputSlots.querySelectorAll('[data-detail-target]').forEach(select => select.addEventListener('change', () => {
            const item = Object.values(state.inputs).find(value => value?.reference_id === select.dataset.detailTarget);
            if(!item) return;
            item.detail_target_id = select.value;
            renderUniversalInputs();
            persistSettings();
            validateForm(false);
        }));
        el.inputSlots.querySelectorAll('[data-reference-field]').forEach(input => bindComposingInput(input, () => {
            const item=state.inputs[input.dataset.referenceKey]; if(item){ item[input.dataset.referenceField]=input.value; persistSettings({sync:false}); validateForm(false); }
        }));
        el.inputSlots.querySelectorAll('[data-remove-reference]').forEach(button => button.addEventListener('click', () => {
            const entries = universalEntries();
            if(entries.length <= 1) { showToast(t('ecommerce.minimumOneReference'), true); return; }
            delete state.inputs[button.dataset.removeReference]; renderUniversalInputs(); persistSettings(); validateForm(false);
        }));
        if(el.addUniversalReference) el.addUniversalReference.onclick = () => {
            const entries=universalEntries(); if(entries.length>=limit) return;
            createUniversalReference('prop', entries.length); renderUniversalInputs(); persistSettings();
        };
        let dragged='';
        el.inputSlots.querySelectorAll('[data-reference-key]').forEach(card => {
            const handle = card.querySelector('[data-reference-drag-handle]');
            handle?.addEventListener('dragstart',event=>{dragged=card.dataset.referenceKey;card.classList.add('dragging');event.dataTransfer.effectAllowed='move';});
            handle?.addEventListener('dragend',()=>{dragged='';card.classList.remove('dragging');});
            card.addEventListener('dragover',event=>{if(!dragged)return;event.preventDefault();card.classList.add('drag-target');});
            card.addEventListener('dragleave',()=>card.classList.remove('drag-target'));
            card.addEventListener('drop',event=>{event.preventDefault();card.classList.remove('drag-target');const target=card.dataset.referenceKey;if(!dragged||dragged===target)return;const keys=universalEntries().map(([key])=>key);const from=keys.indexOf(dragged),to=keys.indexOf(target);keys.splice(to,0,keys.splice(from,1)[0]);keys.forEach((key,index)=>state.inputs[key].order=index);renderUniversalInputs();persistSettings();});
        });
    }

    function isSupportedImageFile(file){
        const allowedTypes = new Set(['image/png','image/jpeg','image/webp']);
        const type = String(file?.type || '').toLowerCase();
        return (!type || allowedTypes.has(type)) && /\.(png|jpe?g|webp)$/i.test(file?.name || '');
    }

    function droppedFiles(dataTransfer){
        const files = Array.from(dataTransfer?.files || []);
        Array.from(dataTransfer?.items || []).forEach(item => {
            if(item?.kind !== 'file') return;
            const file = item.getAsFile?.();
            if(file && !files.includes(file)) files.push(file);
        });
        return files;
    }

    function isFileDrag(event){
        return Array.from(event.dataTransfer?.types || []).includes('Files')
            || Array.from(event.dataTransfer?.items || []).some(item => item?.kind === 'file');
    }

    function nearestEmptyUniversalRole(clientX, clientY){
        const emptySlots = Array.from(el.inputSlots?.querySelectorAll('.ec-upload-slot') || [])
            .filter(slot => !hasReferenceDisplay(state.inputs[slot.dataset.role]));
        if(!emptySlots.length) return '';
        const x = Number(clientX);
        const y = Number(clientY);
        if(!Number.isFinite(x) || !Number.isFinite(y)) return emptySlots[0].dataset.role || '';
        const distanceToSlot = slot => {
            const rect = slot.getBoundingClientRect();
            const dx = x < rect.left ? rect.left - x : (x > rect.right ? x - rect.right : 0);
            const dy = y < rect.top ? rect.top - y : (y > rect.bottom ? y - rect.bottom : 0);
            return (dx * dx) + (dy * dy);
        };
        return emptySlots.reduce((nearest, slot) => (
            distanceToSlot(slot) < distanceToSlot(nearest) ? slot : nearest
        )).dataset.role || '';
    }

    async function handleDroppedUniversalFiles(files, preferredRole=''){
        const dropped = Array.from(files || []);
        const images = dropped.filter(isSupportedImageFile);
        if(!images.length) {
            if(dropped.length) showFormError(t('ecommerce.invalidImage'));
            return;
        }
        clearFormError();
        seedUniversalPresetsIfEmpty();
        const limit = Number(state.capabilities?.universal_reference_limit || 14);
        const targets = [];
        if(preferredRole && state.inputs[preferredRole]) targets.push(preferredRole);
        universalEntries().forEach(([key,item]) => {
            if(!hasReferenceDisplay(item) && !targets.includes(key) && targets.length < images.length) targets.push(key);
        });
        while(targets.length < images.length && universalEntries().length < limit) {
            const entries = universalEntries();
            targets.push(createUniversalReference('prop', entries.length));
        }
        renderUniversalInputs();
        const accepted = Math.min(images.length, targets.length);
        await uploadInputPairs(images.slice(0, accepted).map((file, index) => ({file, role:targets[index]})));
        if(accepted < images.length) showToast(t('ecommerce.referenceLimitReached'), true);
    }

    function bindUniversalDockDrop(){
        const clearDragState = () => {
            el.universalDock?.classList.remove('is-file-dragover');
            el.inputSlots?.querySelectorAll('.ec-upload-slot.dragover').forEach(slot => slot.classList.remove('dragover'));
            el.inputSlots?.querySelectorAll('.ec-universal-reference.drag-target').forEach(card => card.classList.remove('drag-target'));
        };
        const showDragState = event => {
            if(!currentConfig()?.universal || !isFileDrag(event)) return;
            event.preventDefault();
            event.dataTransfer.dropEffect = 'copy';
            el.universalDock.classList.add('is-file-dragover');
        };
        el.universalDock?.addEventListener('dragenter', showDragState);
        el.universalDock?.addEventListener('dragover', showDragState);
        el.universalDock?.addEventListener('dragleave', event => {
            if(!el.universalDock.contains(event.relatedTarget)) clearDragState();
        });
        el.universalDock?.addEventListener('drop', event => {
            clearDragState();
            if(!currentConfig()?.universal || !isFileDrag(event)) return;
            event.preventDefault();
            event.stopPropagation();
            handleDroppedUniversalFiles(
                droppedFiles(event.dataTransfer),
                nearestEmptyUniversalRole(event.clientX, event.clientY),
            );
        });
        window.addEventListener('dragend', clearDragState, true);
        window.addEventListener('drop', clearDragState, true);
    }

    function inputSlotHtml(input){
        const asset = state.inputs[input.role];
        const requiredClass = input.required ? 'required' : '';
        const tryOnStack = state.operation === 'try_on' && isTryOnReferenceRole(input.role);
        const displayLabel = tryOnStack ? tryOnSlotDisplayLabel(input, asset) : t(input.labelKey);
        const candidates = tryOnStack ? tryOnReferenceCandidates(asset) : [];
        const selectedIndex = tryOnStack ? tryOnSelectedReferenceIndex(asset, candidates) : 0;
        const hasStack = candidates.length > 1;
        const switchMeta = tryOnStack ? state.tryOnSwitches[input.role] : null;
        const switchClass = switchMeta ? `is-switch-${switchMeta.direction < 0 ? 'prev' : 'next'}` : '';
        const slotClass = ['ec-upload-slot', requiredClass, hasStack ? 'has-reference-stack' : '', switchClass].filter(Boolean).join(' ');
        const actionButton = (action, label) => tryOnStack
            ? `<button type="button" data-action="${escapeHtml(action)}" title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}"><span aria-hidden="true">${escapeHtml(action === 'upload' ? '+' : action === 'assets' ? '库' : 'x')}</span></button>`
            : `<button type="button" data-action="${escapeHtml(action)}">${escapeHtml(label)}</button>`;
        const actionClass = tryOnStack ? 'ec-upload-actions ec-floating-upload-actions' : 'ec-upload-actions';
        const visibleSlotLabel = tryOnStack ? '' : `<b>${escapeHtml(displayLabel)}</b>`;
        const displayUrl = referenceDisplayUrl(asset);
        if(displayUrl) {
            const stackControls = hasStack ? `<div class="ec-tryon-stack-controls">
                <button type="button" data-tryon-stack-step="-1" aria-label="${escapeHtml(t('ecommerce.previousReference'))}">‹</button>
                <span>${selectedIndex + 1}/${candidates.length}</span>
                <button type="button" data-tryon-stack-step="1" aria-label="${escapeHtml(t('ecommerce.nextReference'))}">›</button>
            </div>` : '';
            const outgoingUrl = referenceDisplayUrl(switchMeta?.from);
            const outgoingCard = hasStack && outgoingUrl ? `<div class="ec-tryon-transition-card is-outgoing" aria-hidden="true"><img src="${escapeHtml(outgoingUrl)}" alt=""></div>` : '';
            const uploadActionLabel = tryOnStack ? t('ecommerce.addReferenceImage') : t('ecommerce.replace');
            return `<article class="${slotClass}" data-role="${escapeHtml(input.role)}" ${tryOnStack ? `tabindex="0" data-tryon-stack-role="${escapeHtml(input.role)}" data-tryon-selected-index="${selectedIndex}" data-switch-token="${escapeHtml(switchMeta?.token || '')}"` : ''}>
                <div class="ec-upload-preview ${hasStack ? 'ec-tryon-stack-preview' : ''}">
                    <div class="ec-tryon-card-stack" aria-label="${escapeHtml(displayLabel)}">
                        ${hasStack ? '<span class="ec-tryon-card-shadow one"></span><span class="ec-tryon-card-shadow two"></span>' : ''}
                        ${outgoingCard}
                        <button type="button" class="ec-upload-image-trigger ec-tryon-active-card" data-preview-reference="${escapeHtml(input.role)}" title="${escapeHtml(t('ecommerce.openReferencePreview'))}"><img src="${escapeHtml(displayUrl)}" alt="${escapeHtml(displayLabel)}"></button>
                        ${stackControls}
                    </div>
                    <div class="ec-upload-info">
                        ${visibleSlotLabel}
                        <span title="${escapeHtml(asset.name || displayUrl)}">${escapeHtml(asset.uploading ? t('ecommerce.uploading') : formatName(asset.name || displayUrl))}</span>
                        <div class="${actionClass}">
                            ${actionButton('upload', uploadActionLabel)}
                            ${actionButton('assets', t('ecommerce.fromAssets'))}
                            ${actionButton('remove', t('ecommerce.remove'))}
                        </div>
                    </div>
                </div>
            </article>`;
        }
        return `<article class="${slotClass}" data-role="${escapeHtml(input.role)}" ${tryOnStack ? `tabindex="0" data-tryon-stack-role="${escapeHtml(input.role)}"` : ''}>
            <div class="ec-upload-empty" data-action="upload" role="button" tabindex="0">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4M7 9l5-5 5 5M5 20h14"></path></svg>
                ${visibleSlotLabel}
                <small>${escapeHtml(t('ecommerce.dropOrChoose'))}</small>
                <span class="${actionClass}">${actionButton('upload', t('ecommerce.addReferenceImage'))}${actionButton('assets', t('ecommerce.fromAssets'))}</span>
            </div>
        </article>`;
    }

    function bindInputSlots(root=el.inputSlots){
        root?.querySelectorAll('.ec-upload-slot').forEach(slot => {
            const role = slot.dataset.role;
            slot.querySelectorAll('[data-action]').forEach(button => {
                button.addEventListener('click', event => {
                    event.preventDefault();
                    event.stopPropagation();
                    const action = button.dataset.action;
                    if(action === 'remove') removeInput(role);
                    if(action === 'upload') openFilePicker(role);
                    if(action === 'assets') openAssetPicker(role);
                });
            });
            slot.querySelectorAll('[data-preview-reference]').forEach(button => button.addEventListener('click', event => {
                event.preventDefault();
                event.stopPropagation();
                openReferencePreview(button.dataset.previewReference || role);
            }));
            if(state.operation === 'try_on' && isTryOnReferenceRole(role)) {
                let lastWheelSwitch = 0;
                slot.querySelectorAll('[data-tryon-stack-step]').forEach(button => {
                    button.addEventListener('click', event => {
                        event.preventDefault();
                        event.stopPropagation();
                        shiftTryOnReference(role, Number(button.dataset.tryonStackStep || 0));
                    });
                });
                slot.addEventListener('pointerenter', () => {
                    if(document.querySelector('dialog[open]') || isTextEditingElement()) return;
                    try { slot.focus({preventScroll:true}); } catch(error) { slot.focus(); }
                });
                slot.addEventListener('keydown', event => {
                    if(event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
                    event.preventDefault();
                    shiftTryOnReference(role, event.key === 'ArrowRight' ? 1 : -1);
                });
                slot.addEventListener('wheel', event => {
                    const candidates = tryOnReferenceCandidates(state.inputs[role]);
                    if(candidates.length <= 1) return;
                    const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
                    if(Math.abs(delta) < 8) return;
                    event.preventDefault();
                    const now = Date.now();
                    if(now - lastWheelSwitch < 180) return;
                    lastWheelSwitch = now;
                    shiftTryOnReference(role, delta > 0 ? 1 : -1);
                }, {passive:false});
            }
            const empty = slot.querySelector('.ec-upload-empty');
            empty?.addEventListener('keydown', event => {
                if(event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    openFilePicker(role);
                }
            });
            slot.addEventListener('dragover', event => {
                if(!isFileDrag(event)) return;
                event.preventDefault();
                slot.classList.add('dragover');
            });
            slot.addEventListener('dragleave', event => {
                if(!slot.contains(event.relatedTarget)) slot.classList.remove('dragover');
            });
            slot.addEventListener('drop', event => {
                event.preventDefault();
                slot.classList.remove('dragover');
                const files = droppedFiles(event.dataTransfer);
                if(!files.length) return;
                event.stopPropagation();
                if(currentConfig()?.universal) handleDroppedUniversalFiles(files, role);
                else if(state.operation === 'try_on' && isTryOnReferenceRole(role)) handleSelectedFiles(files, role);
                else {
                    const file = files.find(isSupportedImageFile);
                    if(file) handleSelectedFile(file, role);
                    else showFormError(t('ecommerce.invalidImage'));
                }
            });
        });
    }

    function renderOperationControls(){
        if(window.StudioFocusGuard?.shouldDeferDomUpdate?.(el.operationControls)) {
            window.StudioFocusGuard.deferDomUpdate('ecommerce-render-operation-controls', renderOperationControls);
            return;
        }
        const focusSnapshot = window.StudioFocusGuard?.capture?.();
        const editingControl = isTextEditingElement() ? document.activeElement : null;
        const options = currentOptions();
        let html = '';
        if(state.operation === 'try_on') {
            html = `<section class="ec-tryon-dialogue-card">
                <label class="ec-tryon-message-box"><span><b>${escapeHtml(t('ecommerce.tryOnDialogTitle'))}</b><small>${escapeHtml(t('ecommerce.tryOnDialogHint'))}</small></span><div class="ec-tryon-message-compose"><textarea data-option="instruction" maxlength="1000" placeholder="${escapeHtml(t('ecommerce.extraInstructionHint'))}">${escapeHtml(options.instruction || '')}</textarea><div id="tryOnMessageActionSlot" class="ec-tryon-message-action-slot"></div></div></label>
            </section>`;
        } else if(state.operation === 'pose_transfer') {
            html = `<div class="ec-field"><span>${escapeHtml(t('ecommerce.poseSource'))}</span><div class="ec-chip-grid">
                <button type="button" data-option-button="pose_source" data-value="reference" class="${options.pose_source === 'reference' ? 'active':''}">${escapeHtml(t('ecommerce.uploadPose'))}</button>
                <button type="button" data-option-button="pose_source" data-value="preset" class="${options.pose_source === 'preset' ? 'active':''}">${escapeHtml(t('ecommerce.posePreset'))}</button>
            </div></div><div class="ec-field"><span>${escapeHtml(t('ecommerce.posePreset'))}</span><div id="posePresetGrid" class="ec-chip-grid">${presetButtons('pose_presets', options.pose_preset)}</div></div>${instructionHtml(options.instruction)}`;
        } else if(state.operation === 'prop_replace') {
            html = `<label class="ec-field"><span>${escapeHtml(t('ecommerce.targetDescription'))}</span><input data-option="target_description" maxlength="240" value="${escapeHtml(options.target_description)}" placeholder="${escapeHtml(t('ecommerce.targetDescriptionHint'))}"></label>${instructionHtml(options.instruction)}`;
        } else if(state.operation === 'angle_change') {
            html = `<div class="ec-field"><span>${escapeHtml(t('ecommerce.viewPreset'))}</span><div class="ec-chip-grid">
                <button type="button" data-angle-preset="0,0">${escapeHtml(t('ecommerce.frontView'))}</button>
                <button type="button" data-angle-preset="-45,0">${escapeHtml(t('ecommerce.leftThreeQuarter'))}</button>
                <button type="button" data-angle-preset="45,0">${escapeHtml(t('ecommerce.rightThreeQuarter'))}</button>
                <button type="button" data-angle-preset="90,0">${escapeHtml(t('ecommerce.sideView'))}</button>
                <button type="button" data-angle-preset="0,20">${escapeHtml(t('ecommerce.topView'))}</button>
            </div></div><div class="ec-field"><span>${escapeHtml(t('ecommerce.azimuth'))}</span><div class="ec-range-row"><input data-option="azimuth" type="range" min="-180" max="180" step="15" value="${Number(options.azimuth)}"><span class="ec-range-value" data-value-for="azimuth">${Number(options.azimuth)}°</span></div></div>
                <div class="ec-field"><span>${escapeHtml(t('ecommerce.elevation'))}</span><div class="ec-range-row"><input data-option="elevation" type="range" min="-30" max="30" step="10" value="${Number(options.elevation)}"><span class="ec-range-value" data-value-for="elevation">${Number(options.elevation)}°</span></div></div>
                <label class="ec-field"><span>${escapeHtml(t('ecommerce.distance'))}</span><select data-option="distance">${optionHtml('close','ecommerce.close',options.distance)}${optionHtml('medium','ecommerce.medium',options.distance)}${optionHtml('wide','ecommerce.wide',options.distance)}</select></label>${instructionHtml(options.instruction)}`;
        } else if(state.operation === 'background_change') {
            html = `<div class="ec-field"><span>${escapeHtml(t('ecommerce.backgroundMode'))}</span><div class="ec-chip-grid">
                <button type="button" data-option-button="background_mode" data-value="preset" class="${options.background_mode === 'preset' ? 'active':''}">${escapeHtml(t('ecommerce.backgroundPreset'))}</button>
                <button type="button" data-option-button="background_mode" data-value="prompt" class="${options.background_mode === 'prompt' ? 'active':''}">${escapeHtml(t('ecommerce.backgroundPrompt'))}</button>
                <button type="button" data-option-button="background_mode" data-value="reference" class="${options.background_mode === 'reference' ? 'active':''}">${escapeHtml(t('ecommerce.backgroundReference'))}</button>
            </div></div><div class="ec-field"><span>${escapeHtml(t('ecommerce.backgroundPreset'))}</span><div id="backgroundPresetGrid" class="ec-chip-grid">${presetButtons('background_presets', options.background_preset)}</div></div>
            <label class="ec-field"><span>${escapeHtml(t('ecommerce.backgroundPrompt'))}</span><textarea data-option="background_prompt" maxlength="1000" placeholder="${escapeHtml(t('ecommerce.backgroundPromptHint'))}">${escapeHtml(options.background_prompt)}</textarea></label>${instructionHtml(options.instruction)}`;
        } else if(state.operation === 'universal') {
            const promptLabelKey = IS_FREE_CREATION ? 'freeCreation.prompt' : 'ecommerce.finalInstruction';
            const promptHintKey = IS_FREE_CREATION ? 'freeCreation.promptHint' : 'ecommerce.finalInstructionHint';
            html = `<label class="ec-field"><span>${escapeHtml(t(promptLabelKey))}</span><textarea class="ec-universal-instruction" data-option="instruction" maxlength="2000" placeholder="${escapeHtml(t(promptHintKey))}">${escapeHtml(options.instruction || '')}</textarea></label>`;
        }
        el.operationControls.innerHTML = html;
        syncUniversalLayout();
        bindOperationControls();
        if(focusSnapshot) window.StudioFocusGuard?.restore?.(focusSnapshot);
        if(editingControl) restoreEditingFocus(editingControl);
    }

    function optionHtml(value, labelKey, selected){
        return `<option value="${escapeHtml(value)}" ${value === selected ? 'selected':''}>${escapeHtml(t(labelKey))}</option>`;
    }
    function instructionHtml(value){
        return `<label class="ec-field"><span>${escapeHtml(t('ecommerce.extraInstruction'))}</span><textarea data-option="instruction" maxlength="1000" placeholder="${escapeHtml(t('ecommerce.extraInstructionHint'))}">${escapeHtml(value || '')}</textarea></label>`;
    }
    function presetButtons(kind, selected){
        const items = state.capabilities?.[kind] || [];
        if(!items.length) return '<span class="ec-task-empty">—</span>';
        return items.map(item => `<button type="button" data-preset-kind="${escapeHtml(kind)}" data-value="${escapeHtml(item.id)}" class="${item.id === selected ? 'active':''}">${escapeHtml(localizedLabel(item))}</button>`).join('');
    }
    function localizedLabel(item){
        const lang = window.StudioI18n?.lang?.() || 'zh';
        return item?.label?.[lang] || item?.label_zh || item?.label_en || item?.name || item?.id || '';
    }

    function studioReferenceItems(){
        const presets = Array.isArray(state.capabilities?.studio_reference_presets) ? state.capabilities.studio_reference_presets : [];
        return STUDIO_REFERENCE_TYPES.map(item => {
            const preset = presets.find(value => value?.id === item.id) || {};
            return {
                ...item,
                label:localizedLabel(preset) || t(item.labelKey),
                description:t(item.descKey),
            };
        });
    }

    function studioReferenceById(id){
        const value = String(id || '').trim();
        if(!value) return null;
        return studioReferenceItems().find(item => item.id === value) || null;
    }

    function currentStudioReference(){
        return studioReferenceById(currentOptions()?.studio_reference);
    }

    function studioSwatchesHtml(item){
        const colors = Array.isArray(item?.colors) && item.colors.length ? item.colors : ['#fff','#ddd','#aaa'];
        return colors.map(color => `<span style="--studio-color:${escapeHtml(color)}"></span>`).join('');
    }

    function studioReferenceCardHtml(context='default'){
        const selected = currentStudioReference();
        const cardClasses = [
            'ec-studio-reference-card',
            selected ? 'is-selected' : 'is-empty',
            selected ? `tone-${selected.tone}` : 'tone-none',
            context === 'try_on' ? 'ec-tryon-slot-card is-studio' : '',
            context === 'universal' ? 'is-universal-studio' : '',
        ].filter(Boolean).join(' ');
        const title = selected ? selected.label : t('ecommerce.addStudioReference');
        const desc = selected ? selected.description : t('ecommerce.studioReferenceEmpty');
        const swatches = studioSwatchesHtml(selected || {colors:['#fffef8','#e7e2d8','#9a6636']});
        const kicker = context === 'try_on'
            ? `<div class="ec-tryon-card-kicker"><b>08</b><span>${escapeHtml(t('ecommerce.studioReference'))}</span></div>`
            : '';
        const footer = context === 'try_on'
            ? `<div class="ec-studio-reference-status">${escapeHtml(selected ? t('ecommerce.studioReferenceReady') : t('ecommerce.studioReferenceOptional'))}</div>`
            : '';
        return `<article class="${cardClasses}" data-studio-reference-card>
            ${kicker}
            <button type="button" class="ec-studio-reference-button" data-open-studio-dialog>
                <span class="ec-studio-reference-visual" aria-hidden="true">${swatches}</span>
                <span class="ec-studio-reference-copy"><b>${escapeHtml(t('ecommerce.studioReference'))}</b><em>${escapeHtml(title)}</em><small>${escapeHtml(desc)}</small></span>
            </button>
            ${footer}
        </article>`;
    }

    function renderStudioDialog(){
        if(!el.studioReferenceGrid) return;
        const selectedId = String(currentOptions()?.studio_reference || '');
        el.studioReferenceGrid.innerHTML = studioReferenceItems().map(item => `<button type="button" class="ec-studio-reference-option ${item.id === selectedId ? 'active':''}" data-studio-reference="${escapeHtml(item.id)}">
            <span class="ec-studio-reference-visual tone-${escapeHtml(item.tone)}" aria-hidden="true">${studioSwatchesHtml(item)}</span>
            <b>${escapeHtml(item.label)}</b>
            <small>${escapeHtml(item.description)}</small>
        </button>`).join('');
        el.studioReferenceGrid.querySelectorAll('[data-studio-reference]').forEach(button => {
            button.addEventListener('click', () => selectStudioReference(button.dataset.studioReference || ''));
        });
    }

    function openStudioDialog(){
        renderStudioDialog();
        if(el.studioDialog && !el.studioDialog.open) el.studioDialog.showModal();
    }

    function selectStudioReference(id){
        const item = studioReferenceById(id);
        if(!item) return;
        if(currentConfig()?.universal && universalTypedEntries().some(([,reference]) => reference.reference_type === 'scene')) {
            showToast(t('ecommerce.sceneStudioConflict'), true);
            return;
        }
        currentOptions().studio_reference = item.id;
        persistSettings();
        renderInputs();
        validateForm(false);
        showToast(t('ecommerce.studioReferenceSelected', {name:item.label}));
        el.studioDialog?.close();
    }

    function clearStudioReference(){
        currentOptions().studio_reference = '';
        persistSettings();
        renderInputs();
        validateForm(false);
        showToast(t('ecommerce.studioReferenceCleared'));
        el.studioDialog?.close();
    }

    function bindStudioReferenceControls(root=el.inputSlots){
        root?.querySelectorAll('[data-open-studio-dialog]').forEach(button => {
            button.addEventListener('click', event => {
                event.preventDefault();
                event.stopPropagation();
                openStudioDialog();
            });
        });
    }

    function bindOperationControls(){
        el.operationControls.querySelectorAll('[data-option]').forEach(input => {
            const update = (deferSync=false) => {
                const key = input.dataset.option;
                currentOptions()[key] = input.type === 'checkbox' ? input.checked : (input.type === 'range' ? Number(input.value) : input.value);
                const target = el.operationControls.querySelector(`[data-value-for="${key}"]`);
                if(target) target.textContent = `${input.value}°`;
                persistSettings(deferSync ? {sync:false} : undefined);
                if(state.operation === 'universal' && key === 'instruction') syncUniversalPromptModeUi();
                validateForm(false);
            };
            if(input.tagName === 'SELECT') input.addEventListener('change', () => update(false));
            else if(input.type === 'checkbox') input.addEventListener('change', () => { update(false); syncGenerationParameterControls(); });
            else if(input.type === 'range') input.addEventListener('input', () => update(false));
            else bindComposingInput(input, () => update(true));
        });
        el.operationControls.querySelectorAll('[data-option-button]').forEach(button => {
            button.addEventListener('click', () => {
                currentOptions()[button.dataset.optionButton] = button.dataset.value;
                persistSettings();
                renderOperationControls();
                renderInputs();
                validateForm(false);
            });
        });
        el.operationControls.querySelectorAll('[data-preset-kind]').forEach(button => {
            button.addEventListener('click', () => {
                if(button.dataset.presetKind === 'pose_presets') currentOptions().pose_preset = button.dataset.value;
                if(button.dataset.presetKind === 'background_presets') currentOptions().background_preset = button.dataset.value;
                persistSettings();
                renderOperationControls();
            });
        });
        el.operationControls.querySelectorAll('[data-angle-preset]').forEach(button => {
            button.addEventListener('click', () => {
                const [azimuth,elevation] = button.dataset.anglePreset.split(',').map(Number);
                currentOptions().azimuth = azimuth;
                currentOptions().elevation = elevation;
                persistSettings();
                renderOperationControls();
            });
        });
    }

    function switchOperation(operation){
        if(IS_FREE_CREATION && operation !== DEFAULT_OPERATION) return;
        if(!OPERATION_CONFIG[operation] || operation === state.operation) return;
        captureWorkspace();
        state.operation = operation;
        const workspace = restoreWorkspace(operation);
        updateTabs();
        renderInputs();
        renderOperationControls();
        if(state.currentTask) renderTaskResult(state.currentTask);
        else {
            hideResult();
            if(workspace.taskId) loadTask(workspace.taskId, false);
        }
        updateRouteSummary();
        persistSettings();
        clearFormError();
    }

    function switchMode(mode){
        state.mode = 'standard';
        updateTabs();
        populateModelSelectors();
        updateRouteSummary();
        persistSettings();
    }

    function removeInput(role){
        const existing = state.inputs[role];
        if(removeTryOnSelectedCandidate(role)) {
            // handled below by the shared render/persist path
        } else if(currentConfig()?.universal && role.startsWith('ref_') && existing) {
            revokeInputPreviewUrls(existing);
            state.inputs[role] = {
                role:existing.role,
                reference_type:existing.reference_type,
                reference_id:existing.reference_id || role,
                label:existing.label || '',
                instruction:existing.instruction || '',
                order:Number(existing.order || 0),
                url:'',
                name:'',
                kind:'image',
                mime:'',
                width:0,
                height:0,
                original_url:'',
                original_name:'',
                original_width:0,
                original_height:0,
                crop_history:[],
            };
        } else {
            revokeInputPreviewUrls(existing);
            delete state.inputs[role];
        }
        renderInputs();
        validateForm(false);
        persistSettings();
    }

    function openFilePicker(role){
        state.activeUploadRole = role;
        byId('fileInput')?.click();
    }

    function openAssetPicker(role){
        state.activeUploadRole = role;
        window.EcommerceStudio?.openAssetPicker?.(role);
    }

    async function handleSelectedFile(file, role){
        if(!file || !role) return;
        await handleSelectedFiles([file], role);
    }

    async function handleSelectedFiles(files, role){
        if(!role) return;
        const list = Array.from(files || []);
        if(!list.length) return;
        if(state.operation === 'try_on' && isTryOnReferenceRole(role)) {
            const images = list.filter(isSupportedImageFile);
            if(!images.length) {
                showFormError(t('ecommerce.invalidImage'));
                return;
            }
            await uploadInputPairs(images.map(file => ({file,role})));
            if(images.length < list.length) showToast(t('ecommerce.invalidImage'), true);
            return;
        }
        const file = list.find(isSupportedImageFile);
        if(file) await uploadInput(file, role);
        else showFormError(t('ecommerce.invalidImage'));
    }

    async function fetchJson(url, options={}){
        const response = await fetch(url, options);
        let body = null;
        try { body = await response.json(); } catch(error) {}
        if(!response.ok) {
            const message = body?.detail || body?.message || `HTTP ${response.status}`;
            throw new Error(Array.isArray(message) ? message.map(item => item.msg || item).join('; ') : String(message));
        }
        return body || {};
    }

    async function fetchJsonWithTimeout(url, options={}, timeoutMs=6000){
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), timeoutMs);
        try {
            return await fetchJson(url, {...options, signal:controller.signal});
        } finally {
            clearTimeout(timer);
        }
    }

    function showToast(message, isError=false){
        if(!el.toast) return;
        el.toast.textContent = String(message || '');
        el.toast.classList.toggle('error', !!isError);
        el.toast.classList.add('show');
        clearTimeout(showToast.timer);
        showToast.timer = setTimeout(() => el.toast.classList.remove('show'), 2600);
    }

    function imageDimensions(url){
        return new Promise((resolve, reject) => {
            const image = new Image();
            image.onload = () => resolve({width:image.naturalWidth, height:image.naturalHeight});
            image.onerror = () => reject(new Error(t('ecommerce.invalidImage')));
            image.src = url;
        });
    }

    function uploadFileValidationError(file){
        if(!isSupportedImageFile(file)) {
            return t('ecommerce.invalidImage');
        }
        if(file.size > MAX_REFERENCE_UPLOAD_BYTES) {
            return t('ecommerce.fileTooLarge');
        }
        return '';
    }

    async function uploadReferenceFile(file){
        const formData = new FormData();
        formData.append('files', file, file.name);
        const result = await fetchJson('/api/ai/upload', {method:'POST', body:formData});
        const uploaded = (result.files || [])[0];
        if(!uploaded?.url || uploaded.kind !== 'image') throw new Error(t('ecommerce.uploadFailed'));
        return uploaded;
    }

    async function uploadReferenceFilesInParallel(pairs){
        return Promise.all(pairs.map(pair => uploadReferenceFile(pair.file)));
    }

    async function uploadedImageDimensions(uploaded){
        const width = Number(uploaded?.width || 0);
        const height = Number(uploaded?.height || 0);
        if(width > 0 && height > 0) return {width, height};
        return imageDimensions(uploaded.url);
    }

    function uploadToken(){
        return `upload_${Date.now().toString(36)}_${Math.random().toString(36).slice(2,10)}`;
    }

    function uploadBaselineForPairs(pairs){
        const baselines = new Map();
        pairs.forEach(pair => {
            if(!baselines.has(pair.role)) baselines.set(pair.role, cloneSerializableInput(state.inputs[pair.role]));
        });
        return baselines;
    }

    function restoreUploadBaselines(baselines){
        baselines.forEach((input, role) => {
            revokeInputPreviewUrls(state.inputs[role]);
            if(input) state.inputs[role] = input;
            else delete state.inputs[role];
        });
    }

    function buildPreviewInput(file, role, token, previewUrl){
        const existing = state.inputs[role] || {};
        const nextInput = {
            ...existing,
            url:'',
            preview_url:previewUrl,
            uploading:true,
            upload_token:token,
            name:file.name || existing.name || '',
            kind:'image',
            mime:file.type || existing.mime || '',
            width:0,
            height:0,
            original_url:'',
            original_name:file.name || existing.original_name || existing.name || '',
            original_width:0,
            original_height:0,
            crop_history:[],
        };
        if(state.operation === 'try_on' || currentConfig()?.universal) {
            const fallbackRole = state.operation === 'try_on' ? role : (existing.reference_type || existing.role || 'prop');
            applySlotTypeToInput(nextInput, selectedSlotTypeId(existing, fallbackRole), fallbackRole);
        }
        return nextInput;
    }

    function applyPreviewInput(pair){
        const token = uploadToken();
        const previewUrl = URL.createObjectURL(pair.file);
        const previewInput = buildPreviewInput(pair.file, pair.role, token, previewUrl);
        const activePair = {...pair, upload_token:token, preview_url:previewUrl};
        if(state.operation === 'try_on' && isTryOnReferenceRole(pair.role)) setTryOnInputCandidate(pair.role, previewInput);
        else {
            revokeInputPreviewUrls(state.inputs[pair.role]);
            state.inputs[pair.role] = previewInput;
        }
        return activePair;
    }

    async function uploadedInputFor(file, role, uploaded, existing){
        const dimensions = await uploadedImageDimensions(uploaded);
        const nextInput = stripUploadPreviewFields({
            ...existing, ...uploaded, role:existing.reference_type || role, reference_id:existing.reference_id || role, reference_type:existing.reference_type || (role === 'source' ? 'source' : role), ...dimensions,
            original_url:uploaded.url, original_name:uploaded.name || file.name, original_width:dimensions.width, original_height:dimensions.height,
            crop_history:[],
        });
        if(state.operation === 'try_on' || currentConfig()?.universal) {
            const fallbackRole = state.operation === 'try_on' ? role : (existing.reference_type || existing.role || 'prop');
            applySlotTypeToInput(nextInput, selectedSlotTypeId(existing, fallbackRole), fallbackRole);
        }
        return nextInput;
    }

    async function applyUploadedInput(pair, uploaded){
        const {file, role, upload_token:token, preview_url:previewUrl} = pair;
        if(state.operation === 'try_on' && isTryOnReferenceRole(role)) {
            const existing = state.inputs[role] || {};
            const candidates = tryOnReferenceCandidates(existing);
            const candidateIndex = candidates.findIndex(candidate => candidate.upload_token === token);
            if(candidateIndex < 0) {
                if(isLocalPreviewUrl(previewUrl)) URL.revokeObjectURL(previewUrl);
                return;
            }
            revokeReferencePreviewUrl(candidates[candidateIndex]);
            const uploadedCandidate = await uploadedInputFor(file, role, uploaded, {...existing, ...candidates[candidateIndex]});
            candidates[candidateIndex] = cleanInputCandidate(uploadedCandidate);
            const selectedIndex = existing.upload_token === token || candidates[tryOnSelectedReferenceIndex(existing, candidates)]?.upload_token === token
                ? candidateIndex
                : tryOnSelectedReferenceIndex(existing, candidates);
            state.inputs[role] = buildTryOnInput(role, existing, candidates, selectedIndex);
        } else {
            const existing = state.inputs[role] || {};
            if(existing.upload_token !== token) {
                if(isLocalPreviewUrl(previewUrl)) URL.revokeObjectURL(previewUrl);
                return;
            }
            revokeReferencePreviewUrl(existing);
            state.inputs[role] = await uploadedInputFor(file, role, uploaded, existing);
        }
        return;
    }

    async function uploadInputPairs(pairs){
        const uploadPairs = (pairs || []).filter(pair => pair?.file && pair?.role);
        if(!uploadPairs.length) return;
        const validationError = uploadPairs.map(pair => uploadFileValidationError(pair.file)).find(Boolean);
        if(validationError) {
            showFormError(validationError);
            return;
        }
        clearFormError();
        el.generateButton.disabled = true;
        const originalLabel = el.generateButton.querySelector('span')?.textContent || '';
        const label = el.generateButton.querySelector('span');
        if(label) label.textContent = t('ecommerce.uploading');
        const baselines = uploadBaselineForPairs(uploadPairs);
        const activePairs = uploadPairs.map(applyPreviewInput);
        renderInputs();
        validateForm(false);
        try {
            const uploadedFiles = await uploadReferenceFilesInParallel(activePairs);
            for(let index=0; index<activePairs.length; index += 1) {
                await applyUploadedInput(activePairs[index], uploadedFiles[index]);
            }
            renderInputs();
            validateForm(false);
            persistSettings();
        } catch(error) {
            restoreUploadBaselines(baselines);
            renderInputs();
            validateForm(false);
            showFormError(`${t('ecommerce.uploadFailed')}：${error.message}`);
        } finally {
            el.generateButton.disabled = false;
            if(label) label.textContent = originalLabel;
            updateTabs();
        }
    }

    async function uploadInput(file, role){
        await uploadInputPairs([{file, role}]);
    }

    function referenceVersions(item){
        if(!item || typeof item !== 'object') return [];
        const versions = [];
        const seen = new Set();
        const append = version => {
            const url = String(version?.url || '').trim();
            if(!url || seen.has(url)) return;
            seen.add(url);
            versions.push({...version, url});
        };
        append({
            url:item.original_url || item.url,
            name:item.original_name || item.name || '',
            width:Number(item.original_width || item.width || 0),
            height:Number(item.original_height || item.height || 0),
            ratio:'source',
            is_original:true,
        });
        cleanCropHistory(item.crop_history).forEach((version, index) => append({
            ...version,
            is_original:false,
            crop_index:index + 1,
        }));
        append({
            url:item.url,
            name:item.name || '',
            width:Number(item.width || 0),
            height:Number(item.height || 0),
            ratio:'',
            is_original:false,
            crop_index:versions.length,
        });
        return versions;
    }

    function selectedReferenceVersion(){
        return state.referencePreview.versions[state.referencePreview.selectedIndex] || null;
    }

    function renderReferenceVersions(){
        const preview = state.referencePreview;
        el.referenceVersionList.innerHTML = preview.versions.map((version, index) => {
            const label = version.is_original
                ? t('ecommerce.originalVersion')
                : t('ecommerce.cropVersion',{count:version.crop_index || index});
            return `<button type="button" class="ec-reference-version ${index === preview.selectedIndex ? 'active':''}" data-reference-version="${index}" title="${escapeHtml(version.name || label)}"><img src="${escapeHtml(version.url)}" alt="${escapeHtml(label)}"><span>${escapeHtml(label)}</span></button>`;
        }).join('');
        el.referenceVersionList.querySelectorAll('[data-reference-version]').forEach(button => {
            button.addEventListener('click', () => selectReferenceVersion(Number(button.dataset.referenceVersion)));
        });
        const item = state.inputs[preview.key];
        const selected = selectedReferenceVersion();
        if(el.useReferenceVersion) el.useReferenceVersion.disabled = !selected || selected.url === item?.url;
    }

    function selectReferenceVersion(index){
        const preview = state.referencePreview;
        if(!preview.versions.length) return;
        preview.selectedIndex = Math.max(0, Math.min(preview.versions.length - 1, Number(index) || 0));
        const selected = selectedReferenceVersion();
        if(!selected) return;
        el.referencePreviewImage.src = selected.url;
        el.referenceCropImage.onload = () => {
            if(preview.mode === 'crop') resetReferenceCropBox();
        };
        el.referenceCropImage.src = selected.url;
        renderReferenceVersions();
        resetReferenceCropBox();
    }

    function openReferencePreview(key, preferredUrl=''){
        const item = state.inputs[key];
        if(!item?.url || !el.referencePreview) return;
        const versions = referenceVersions(item);
        if(!versions.length) return;
        const preview = state.referencePreview;
        preview.key = key;
        preview.versions = versions;
        preview.selectedIndex = Math.max(0, versions.findIndex(version => version.url === (preferredUrl || item.url)));
        preview.ratio = 'free';
        preview.drag = null;
        el.referencePreviewTitle.textContent = item.label || item.name
            ? `${t('ecommerce.referencePreviewTitle')} · ${formatName(item.label || item.name)}`
            : t('ecommerce.referencePreviewTitle');
        selectReferenceVersion(preview.selectedIndex);
        setReferenceCropRatio('free');
        setReferencePreviewMode('preview');
        if(!el.referencePreview.open) el.referencePreview.showModal();
    }

    function setReferencePreviewMode(mode){
        const preview = state.referencePreview;
        preview.mode = mode === 'crop' ? 'crop' : 'preview';
        const cropping = preview.mode === 'crop';
        el.referencePreviewMode.classList.toggle('active', !cropping);
        el.referenceCropMode.classList.toggle('active', cropping);
        el.referencePreviewStage.classList.toggle('hidden', cropping);
        el.referenceCropStage.classList.toggle('hidden', !cropping);
        el.referenceCropRatios.classList.toggle('hidden', !cropping);
        el.applyReferenceCrop.classList.toggle('hidden', !cropping);
        if(cropping) resetReferenceCropBox();
    }

    function cropRatioValue(ratio=state.referencePreview.ratio){
        const image = el.referenceCropImage;
        if(ratio === 'free') return 0;
        if(ratio === 'source') return image?.naturalWidth && image?.naturalHeight ? image.naturalWidth / image.naturalHeight : 0;
        const [width,height] = String(ratio || '').split(':').map(Number);
        return width > 0 && height > 0 ? width / height : 0;
    }

    function setReferenceCropRatio(ratio){
        const supported = new Set(['free','source','1:1','2:3','3:2','3:4','4:3','4:5','9:16','16:9']);
        state.referencePreview.ratio = supported.has(ratio) ? ratio : 'free';
        el.referenceCropRatios.querySelectorAll('[data-crop-ratio]').forEach(button => {
            button.classList.toggle('active', button.dataset.cropRatio === state.referencePreview.ratio);
        });
        resetReferenceCropBox();
    }

    function resetReferenceCropBox(){
        const image = el.referenceCropImage;
        const sourceRatio = image?.naturalWidth && image?.naturalHeight ? image.naturalWidth / image.naturalHeight : 0;
        const targetRatio = cropRatioValue();
        let width = .9;
        let height = .9;
        if(sourceRatio > 0 && targetRatio > 0) {
            const normalizedRatio = targetRatio / sourceRatio;
            if(normalizedRatio >= 1) height = width / normalizedRatio;
            else width = height * normalizedRatio;
        }
        state.referencePreview.cropRect = {
            x:(1 - width) / 2,
            y:(1 - height) / 2,
            w:width,
            h:height,
        };
        renderReferenceCropBox();
    }

    function renderReferenceCropBox(){
        const rect = state.referencePreview.cropRect;
        if(!rect || !el.referenceCropBox) return;
        el.referenceCropBox.style.left = `${rect.x * 100}%`;
        el.referenceCropBox.style.top = `${rect.y * 100}%`;
        el.referenceCropBox.style.width = `${rect.w * 100}%`;
        el.referenceCropBox.style.height = `${rect.h * 100}%`;
    }

    function beginReferenceCropDrag(event){
        if(event.button !== 0) return;
        const stage = el.referenceCropStage.getBoundingClientRect();
        if(!stage.width || !stage.height) return;
        event.preventDefault();
        const handle = event.target.closest('[data-crop-handle]')?.dataset.cropHandle || 'move';
        state.referencePreview.drag = {
            pointerId:event.pointerId,
            handle,
            startX:event.clientX,
            startY:event.clientY,
            stageWidth:stage.width,
            stageHeight:stage.height,
            rect:{...state.referencePreview.cropRect},
        };
        el.referenceCropBox.setPointerCapture?.(event.pointerId);
    }

    function moveReferenceCropDrag(event){
        const drag = state.referencePreview.drag;
        if(!drag || drag.pointerId !== event.pointerId) return;
        event.preventDefault();
        const dx = (event.clientX - drag.startX) / drag.stageWidth;
        const dy = (event.clientY - drag.startY) / drag.stageHeight;
        const start = drag.rect;
        if(drag.handle === 'move') {
            state.referencePreview.cropRect = {
                ...start,
                x:Math.max(0, Math.min(1 - start.w, start.x + dx)),
                y:Math.max(0, Math.min(1 - start.h, start.y + dy)),
            };
            renderReferenceCropBox();
            return;
        }
        const west = drag.handle.includes('w');
        const north = drag.handle.includes('n');
        const anchorX = west ? start.x + start.w : start.x;
        const anchorY = north ? start.y + start.h : start.y;
        const pointerX = Math.max(0, Math.min(1, (event.clientX - el.referenceCropStage.getBoundingClientRect().left) / drag.stageWidth));
        const pointerY = Math.max(0, Math.min(1, (event.clientY - el.referenceCropStage.getBoundingClientRect().top) / drag.stageHeight));
        const maxWidth = west ? anchorX : 1 - anchorX;
        const maxHeight = north ? anchorY : 1 - anchorY;
        const minWidth = Math.min(maxWidth, 32 / drag.stageWidth);
        const minHeight = Math.min(maxHeight, 32 / drag.stageHeight);
        let width = Math.max(minWidth, Math.min(maxWidth, Math.abs(pointerX - anchorX)));
        let height = Math.max(minHeight, Math.min(maxHeight, Math.abs(pointerY - anchorY)));
        const targetRatio = cropRatioValue();
        const sourceRatio = el.referenceCropImage.naturalWidth && el.referenceCropImage.naturalHeight
            ? el.referenceCropImage.naturalWidth / el.referenceCropImage.naturalHeight
            : 0;
        if(targetRatio > 0 && sourceRatio > 0) {
            const normalizedRatio = targetRatio / sourceRatio;
            const projectedHeight = (width * normalizedRatio + height) / (normalizedRatio * normalizedRatio + 1);
            const minimumHeight = Math.max(minHeight, minWidth / normalizedRatio);
            height = Math.max(minimumHeight, Math.min(maxHeight, maxWidth / normalizedRatio, projectedHeight));
            width = height * normalizedRatio;
        }
        state.referencePreview.cropRect = {
            x:west ? anchorX - width : anchorX,
            y:north ? anchorY - height : anchorY,
            w:width,
            h:height,
        };
        renderReferenceCropBox();
    }

    function endReferenceCropDrag(event){
        const drag = state.referencePreview.drag;
        if(!drag || (event?.pointerId != null && drag.pointerId !== event.pointerId)) return;
        try { el.referenceCropBox.releasePointerCapture?.(drag.pointerId); } catch(error) {}
        state.referencePreview.drag = null;
    }

    async function applyReferenceCrop(){
        const preview = state.referencePreview;
        const item = state.inputs[preview.key];
        const selected = selectedReferenceVersion();
        const image = el.referenceCropImage;
        if(!item || !selected || !image?.naturalWidth || !image?.naturalHeight) return;
        const rect = preview.cropRect;
        const sourceX = Math.max(0, Math.round(rect.x * image.naturalWidth));
        const sourceY = Math.max(0, Math.round(rect.y * image.naturalHeight));
        const sourceWidth = Math.max(1, Math.min(image.naturalWidth - sourceX, Math.round(rect.w * image.naturalWidth)));
        const sourceHeight = Math.max(1, Math.min(image.naturalHeight - sourceY, Math.round(rect.h * image.naturalHeight)));
        const canvas = document.createElement('canvas');
        canvas.width = sourceWidth;
        canvas.height = sourceHeight;
        const context = canvas.getContext('2d');
        if(!context) return;
        el.applyReferenceCrop.disabled = true;
        try {
            context.drawImage(image, sourceX, sourceY, sourceWidth, sourceHeight, 0, 0, sourceWidth, sourceHeight);
            const blob = await new Promise((resolve, reject) => {
                canvas.toBlob(value => value ? resolve(value) : reject(new Error(t('ecommerce.cropFailed'))), 'image/png');
            });
            const baseName = String(item.original_name || item.name || 'reference').replace(/\.[^.]+$/, '');
            const fileName = `${baseName}-crop-${Date.now()}.png`;
            const formData = new FormData();
            formData.append('files', blob, fileName);
            const result = await fetchJson('/api/ai/upload', {method:'POST', body:formData});
            const uploaded = (result.files || [])[0];
            if(!uploaded?.url || uploaded.kind !== 'image') throw new Error(t('ecommerce.cropFailed'));
            const history = cleanCropHistory(item.crop_history);
            history.push({
                url:uploaded.url,
                name:uploaded.name || fileName,
                source_url:selected.url,
                width:sourceWidth,
                height:sourceHeight,
                ratio:preview.ratio,
                created_at:Date.now(),
                crop:{x:rect.x,y:rect.y,w:rect.w,h:rect.h,source_width:image.naturalWidth,source_height:image.naturalHeight},
            });
            item.url = uploaded.url;
            item.name = uploaded.name || fileName;
            item.kind = 'image';
            item.mime = uploaded.mime || 'image/png';
            item.width = sourceWidth;
            item.height = sourceHeight;
            item.original_url = item.original_url || selected.url;
            item.original_name = item.original_name || selected.name || item.name;
            item.original_width = Number(item.original_width || selected.width || image.naturalWidth);
            item.original_height = Number(item.original_height || selected.height || image.naturalHeight);
            item.crop_history = history;
            syncTryOnCurrentCandidate(preview.key);
            renderInputs();
            persistSettings();
            preview.versions = referenceVersions(item);
            preview.selectedIndex = Math.max(0, preview.versions.findIndex(version => version.url === uploaded.url));
            selectReferenceVersion(preview.selectedIndex);
            setReferencePreviewMode('preview');
            showToast(t('ecommerce.cropSucceeded'));
        } catch(error) {
            showToast(`${t('ecommerce.cropFailed')}：${error.message}`, true);
        } finally {
            el.applyReferenceCrop.disabled = false;
        }
    }

    function useReferenceVersion(){
        const preview = state.referencePreview;
        const item = state.inputs[preview.key];
        const selected = selectedReferenceVersion();
        if(!item || !selected) return;
        item.url = selected.url;
        item.name = selected.name || item.name;
        item.width = Number(selected.width || item.width || 0);
        item.height = Number(selected.height || item.height || 0);
        syncTryOnCurrentCandidate(preview.key);
        renderInputs();
        persistSettings();
        renderReferenceVersions();
        showToast(t('ecommerce.referenceVersionApplied'));
    }

    function bindReferencePreview(){
        el.referencePreviewMode?.addEventListener('click', () => setReferencePreviewMode('preview'));
        el.referenceCropMode?.addEventListener('click', () => setReferencePreviewMode('crop'));
        el.referenceCropRatios?.querySelectorAll('[data-crop-ratio]').forEach(button => {
            button.addEventListener('click', () => setReferenceCropRatio(button.dataset.cropRatio));
        });
        el.useReferenceVersion?.addEventListener('click', useReferenceVersion);
        el.applyReferenceCrop?.addEventListener('click', applyReferenceCrop);
        el.referenceCropBox?.addEventListener('pointerdown', beginReferenceCropDrag);
        el.referenceCropBox?.addEventListener('pointermove', moveReferenceCropDrag);
        el.referenceCropBox?.addEventListener('pointerup', endReferenceCropDrag);
        el.referenceCropBox?.addEventListener('pointercancel', endReferenceCropDrag);
        el.referenceCropImage?.addEventListener('dragstart', event => event.preventDefault());
        el.referencePreview?.addEventListener('cancel', () => endReferenceCropDrag());
        el.referencePreview?.addEventListener('close', () => {
            endReferenceCropDrag();
            state.referencePreview.key = '';
            state.referencePreview.versions = [];
            el.referencePreviewImage.removeAttribute('src');
            el.referenceCropImage.removeAttribute('src');
        });
        setReferenceCropRatio('free');
    }

    function assetLibraries(){
        const data = state.assetLibrary || {};
        return Array.isArray(data.libraries) && data.libraries.length ? data.libraries : [data].filter(item => item.id);
    }

    function selectedAssetLibrary(){
        const libraries = assetLibraries();
        return libraries.find(item => item.id === el.assetLibrarySelect.value) || libraries[0] || null;
    }

    function selectedAssetCategory(){
        const library = selectedAssetLibrary();
        return (library?.categories || []).find(item => item.id === el.assetCategorySelect.value) || null;
    }

    function activeAssetReferenceFallbackRole(){
        if(state.operation === 'try_on') return state.activeUploadRole || 'prop';
        const item = state.inputs[state.activeUploadRole] || {};
        return item.reference_type || item.role || 'prop';
    }

    function renderAssetReferenceTypeSelector(){
        if(!el.assetReferenceTypeSelect) return;
        const selectable = state.assetDialogMode === 'select' && (state.operation === 'try_on' || currentConfig()?.universal);
        el.assetReferenceTypeSelect.parentElement?.classList.toggle('has-reference-type', selectable);
        el.assetReferenceTypeSelect.classList.toggle('hidden', !selectable);
        if(!selectable) {
            el.assetReferenceTypeSelect.innerHTML = '';
            return;
        }
        const context = state.operation === 'try_on' ? 'try_on' : 'universal';
        const fallback = activeAssetReferenceFallbackRole();
        const selected = selectedSlotTypeId(state.inputs[state.activeUploadRole] || {}, fallback);
        el.assetReferenceTypeSelect.innerHTML = referenceTypeOptionsHtml(selected, context, fallback);
        if(Array.from(el.assetReferenceTypeSelect.options).some(option => option.value === selected)) {
            el.assetReferenceTypeSelect.value = selected;
        }
    }

    function renderAssetLibrarySelectors(){
        const libraries = assetLibraries();
        const currentLibraryId = el.assetLibrarySelect.value || state.assetLibrary?.active_library_id || libraries[0]?.id || '';
        el.assetLibrarySelect.innerHTML = libraries.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name || item.id)}</option>`).join('');
        el.assetLibrarySelect.value = libraries.some(item => item.id === currentLibraryId) ? currentLibraryId : (libraries[0]?.id || '');
        const categories = (selectedAssetLibrary()?.categories || []).filter(item => item.type === 'image');
        const currentCategoryId = el.assetCategorySelect.value;
        el.assetCategorySelect.innerHTML = categories.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name || item.id)}</option>`).join('');
        el.assetCategorySelect.value = categories.some(item => item.id === currentCategoryId) ? currentCategoryId : (categories[0]?.id || '');
        renderAssetReferenceTypeSelector();
        renderAssetGrid();
    }

    function renderAssetGrid(){
        const category = selectedAssetCategory();
        if(state.assetDialogMode === 'save') {
            el.assetGrid.innerHTML = `<div class="ec-task-empty">${escapeHtml(t('ecommerce.destinationHint',{name:category?.name || '—'}))}</div>`;
            return;
        }
        const items = (category?.items || []).filter(item => item.kind === 'image' && item.url);
        if(!items.length) {
            el.assetGrid.innerHTML = `<div class="ec-task-empty">${escapeHtml(t('ecommerce.noAssets'))}</div>`;
            return;
        }
        el.assetGrid.innerHTML = items.map((item,index) => `<button type="button" class="ec-asset-item" data-asset-index="${index}">
            <img src="${escapeHtml(item.thumbnail_url || item.preview_url || item.url)}" alt="${escapeHtml(item.name || '')}" loading="lazy">
            <span>${escapeHtml(item.name || item.url)}</span>
        </button>`).join('');
        el.assetGrid.querySelectorAll('[data-asset-index]').forEach(button => {
            button.addEventListener('click', async () => {
                const item = items[Number(button.dataset.assetIndex)];
                if(!item) return;
                try {
                    const dimensions = await imageDimensions(item.url);
                    const existing = state.inputs[state.activeUploadRole] || {};
                    const nextInput = {
                        ...existing,
                        url:item.url,
                        name:item.name || item.url.split('/').pop(),
                        kind:'image',
                        mime:item.mime || '',
                        role:existing.reference_type || state.activeUploadRole,
                        reference_id:existing.reference_id || state.activeUploadRole,
                        original_url:item.url,
                        original_name:item.name || item.url.split('/').pop(),
                        original_width:dimensions.width,
                        original_height:dimensions.height,
                        crop_history:[],
                        ...dimensions,
                    };
                    if(state.operation === 'try_on' || currentConfig()?.universal) {
                        applySlotTypeToInput(nextInput, el.assetReferenceTypeSelect?.value || selectedSlotTypeId(existing, activeAssetReferenceFallbackRole()), activeAssetReferenceFallbackRole());
                    }
                    if(state.operation === 'try_on' && isTryOnReferenceRole(state.activeUploadRole)) setTryOnInputCandidate(state.activeUploadRole, nextInput);
                    else state.inputs[state.activeUploadRole] = nextInput;
                    el.assetDialog.close();
                    renderInputs();
                    validateForm(false);
                    persistSettings();
                } catch(error) {
                    showToast(error.message, true);
                }
            });
        });
    }

    async function openAssetPickerForRole(role){
        state.activeUploadRole = role;
        state.assetDialogMode = 'select';
        el.assetDialogTitle.textContent = t('ecommerce.chooseAsset');
        el.assetSaveConfirm.classList.add('hidden');
        try {
            const response = await fetchJson('/api/asset-library');
            state.assetLibrary = response.library || {};
            renderAssetLibrarySelectors();
            el.assetDialog.showModal();
        } catch(error) {
            showToast(`${t('ecommerce.taskLoadFailed')}：${error.message}`, true);
        }
    }

    async function openAssetSaveDialog(){
        if(el.saveAsset.disabled) return;
        state.assetDialogMode = 'save';
        el.assetDialogTitle.textContent = t('ecommerce.chooseDestination');
        el.assetSaveConfirm.classList.remove('hidden');
        try {
            const response = await fetchJson('/api/asset-library');
            state.assetLibrary = response.library || {};
            renderAssetLibrarySelectors();
            el.assetDialog.showModal();
        } catch(error) {
            showToast(error.message, true);
        }
    }

    function validateForm(show=true){
        const config = currentConfig();
        if(config.universal) {
            const references = universalEntries().map(([,item]) => item).filter(item => item.url);
            if(!IS_FREE_CREATION && !references.length) {
                if(show) showFormError(t('ecommerce.universalReferenceRequired'));
                return false;
            }
            if(IS_FREE_CREATION && !String(currentOptions().instruction || '').trim()) {
                if(show) showFormError(t('freeCreation.promptRequired'));
                return false;
            }
            if(!IS_FREE_CREATION) {
                const plan = resolveUniversalReferencePlan();
                if(plan.conflicts.length) {
                    if(show) showFormError(plan.conflicts[0]);
                    return false;
                }
            }
            if(!compatibleModels().length) {
                if(show) {
                    clearFormError();
                    showResultPreviewError(t('ecommerce.noCompatibleModel'));
                }
                return false;
            }
            clearFormError();
            return true;
        }
        const missing = config.inputs.filter(item => {
            if(!item.required) return false;
            if(state.operation === 'pose_transfer' && item.role === 'pose' && currentOptions().pose_source === 'preset') return false;
            return !state.inputs[item.role]?.url;
        });
        if(state.operation === 'pose_transfer' && currentOptions().pose_source === 'reference' && !state.inputs.pose?.url) missing.push({role:'pose'});
        if(state.operation === 'background_change' && currentOptions().background_mode === 'reference' && !state.inputs.background?.url) missing.push({role:'background'});
        if(missing.length) {
            if(show) showFormError(t('ecommerce.inputRequired'));
            return false;
        }
        if(state.operation === 'try_on' && tryOnOutfitCount() <= 0) {
            if(show) showFormError(t('ecommerce.tryOnOutfitRequired'));
            return false;
        }
        if(!state.capabilities?.models?.length) {
            if(show) {
                clearFormError();
                showResultPreviewError(t('ecommerce.noCompatibleModel'));
            }
            return false;
        }
        clearFormError();
        return true;
    }

    function isCompatibleModelError(message){
        const value = String(message || '');
        const lower = value.toLowerCase();
        return value.includes('兼容的图片编辑模型')
            || lower.includes('compatible image editing model')
            || lower.includes('compatible image editor');
    }

    function hideResultPreviewError(){
        el.emptyResult?.classList.remove('has-error');
        el.emptyResultNotice?.classList.add('hidden');
        if(el.emptyResultNoticeTitle) el.emptyResultNoticeTitle.textContent = '';
        if(el.emptyResultNoticeMessage) el.emptyResultNoticeMessage.textContent = '';
        el.resultErrorOverlay?.classList.add('hidden');
        if(el.resultErrorTitle) el.resultErrorTitle.textContent = '';
        if(el.resultErrorMessage) el.resultErrorMessage.textContent = '';
        if(el.resultErrorClear) {
            el.resultErrorClear.dataset.clearTask = '';
            el.resultErrorClear.classList.add('hidden');
        }
    }

    function showResultPreviewError(message, task=null){
        const text = String(message || t('ecommerce.taskFailed')).trim();
        const taskId = task ? taskIdOf(task) : '';
        const title = task ? t('ecommerce.taskErrorTitle') : t('ecommerce.previewErrorTitle');
        setGenerationVisible(false);
        if(taskId || !el.resultWorkspace?.classList.contains('hidden')) {
            el.emptyResult?.classList.remove('has-error');
            el.emptyResultNotice?.classList.add('hidden');
            if(el.resultErrorTitle) el.resultErrorTitle.textContent = title;
            if(el.resultErrorMessage) el.resultErrorMessage.textContent = text;
            if(el.resultErrorClear) {
                el.resultErrorClear.dataset.clearTask = taskId;
                el.resultErrorClear.classList.toggle('hidden', !taskId);
            }
            el.resultErrorOverlay?.classList.remove('hidden');
            return;
        }
        el.resultWorkspace?.classList.add('hidden');
        el.resultErrorOverlay?.classList.add('hidden');
        el.emptyResult?.classList.remove('hidden');
        el.emptyResult?.classList.add('has-error');
        if(el.emptyResultNoticeTitle) el.emptyResultNoticeTitle.textContent = title;
        if(el.emptyResultNoticeMessage) el.emptyResultNoticeMessage.textContent = text;
        el.emptyResultNotice?.classList.remove('hidden');
    }

    function showTaskResultError(task){
        const status = t(`ecommerce.${task?.status || 'failed'}`);
        const message = `${status}：${task?.error || t('ecommerce.taskFailed')}`;
        showResultPreviewError(message, task);
    }

    function showFormError(message){ el.formError.textContent = message; el.formError.classList.remove('hidden'); }
    function clearFormError(){ el.formError.textContent = ''; el.formError.classList.add('hidden'); }
    function hideResult(){
        hideResultPreviewError();
        el.emptyResult.classList.remove('hidden');
        el.resultWorkspace.classList.add('hidden');
        syncTryOnLookPreview();
    }

    function taskInputsForRequest(){
        if(currentConfig().universal) {
            const userSupplement = universalHasUserSupplement();
            const entries = IS_FREE_CREATION || userSupplement ? universalEntries().filter(([,item]) => item.url) : universalTypedEntries();
            const plan = IS_FREE_CREATION ? null : resolveUniversalReferencePlan();
            return entries.map(([,item]) => ({
                url:item.url,name:item.name || '',role:item.reference_type,reference_id:item.reference_id,
                reference_type:item.reference_type,label:requestReferenceLabel(item),instruction:item.instruction || '',kind:'image',mime:item.mime || '',
                detail_target_id:!IS_FREE_CREATION && item.reference_type === 'detail' ? detailTargetIdForItem(item, plan) : '',
            }));
        }
        if(state.operation === 'try_on') {
            return tryOnInputEntriesForRequest().filter(([,item]) => item?.url).map(([slotRole,item], index) => {
                const role = tryOnRequestRoleForSlot(slotRole, item);
                return [slotRole, role, item];
            }).filter(([,role]) => role === 'source' || TRY_ON_REQUEST_ROLES.includes(role)).map(([slotRole,role,item], index) => ({
                url:item.url,
                name:item.name || '',
                role,
                reference_id:item.reference_id || `${slotRole}_${index + 1}`,
                reference_type:role === 'source' ? 'source' : role,
                label:requestReferenceLabel(item, t(tryOnInputConfig(slotRole)?.labelKey || 'ecommerce.garmentImage')),
                instruction:item.instruction || '',
                kind:'image',
                mime:item.mime || '',
            }));
        }
        return Object.values(state.inputs).filter(item => {
            if(!item?.url) return false;
            if(item.role === 'pose' && currentOptions().pose_source !== 'reference') return false;
            if(item.role === 'background' && currentOptions().background_mode !== 'reference') return false;
            return true;
        }).map(item => ({url:item.url, name:item.name || '', role:item.role, kind:'image', mime:item.mime || ''}));
    }

    function ecommerceTaskPayload(parentTaskId=''){
        const payload = {
            operation:state.operation,
            mode:'standard',
            inputs:taskInputsForRequest(),
            options:{...currentOptions()},
            provider_id:state.providerId,
            model:state.model,
            aspect_ratio:state.aspectRatio,
            resolution:state.resolution,
            quality:state.quality,
            count:state.count,
            parent_task_id:parentTaskId || '',
        };
        if(IS_FREE_CREATION) payload.options.prompt_policy = 'free';
        return payload;
    }

    function taskReferences(task){
        const inputs = task?.inputs || task?.request?.inputs || task?.result?.inputs || task?.result?.params?.reference_images || [];
        return Array.isArray(inputs) ? inputs : [];
    }

    function taskPoseReference(task){
        return taskReferences(task).find(item => item?.url && (item.reference_type === 'pose' || item.role === 'pose')) || null;
    }

    function sourceReferenceForTask(task){
        const source = taskReferences(task).find(item => item?.url && (item.role === 'source' || item.reference_type === 'subject' || item.role === 'subject'));
        if(source) return source;
        if(state.inputs.source?.url) return state.inputs.source;
        return universalEntries().find(([,item]) => item.reference_type === 'subject')?.[1] || null;
    }

    function comparisonReferenceForTask(task){
        const explicitUrl = task?.comparison_reference_url || task?.request?.comparison_reference_url || task?.result?.comparison_reference_url || task?.result?.params?.comparison_reference_url || '';
        const pose = taskPoseReference(task);
        const source = sourceReferenceForTask(task);
        if(pose) return {...pose, url:explicitUrl || pose.url, isPose:true};
        if(source) return {...source, url:explicitUrl || source.url, isPose:false};
        return null;
    }

    function sourceUrlForTask(task){
        return comparisonReferenceForTask(task)?.url || '';
    }

    function setComparisonForeground(image, url){
        if(url) image.src = url;
        else image.removeAttribute('src');
    }

    function setComparisonBackdrops(url){
        [el.beforeBackdrop, el.afterBackdrop].forEach(backdrop => {
            if(url) backdrop.src = url;
            else backdrop.removeAttribute('src');
        });
    }

    function syncComparisonReference(task){
        const reference = comparisonReferenceForTask(task);
        const isPose = Boolean(reference?.isPose);
        const label = t(isPose ? 'ecommerce.poseReference' : 'ecommerce.before');
        setComparisonForeground(el.beforeImage, reference?.url || '');
        el.beforeImage.alt = label;
        el.compareBeforeLabel.textContent = label;
        el.compareBeforeLabel.dataset.i18n = isPose ? 'ecommerce.poseReference' : 'ecommerce.before';
        el.compareHandle.setAttribute('aria-label', t(isPose ? 'ecommerce.poseCompareLabel' : 'ecommerce.compareLabel'));
        return reference;
    }

    function setCompareValue(value){
        state.compareValue = Math.max(0, Math.min(100, Number(value) || 0));
        activeWorkspace().compareValue = state.compareValue;
        if(state.compareViewer) state.compareViewer.setDivider(state.compareValue, true);
        else {
            el.afterClip.style.width = `${state.compareValue}%`;
            el.compareHandle.style.left = `${state.compareValue}%`;
            el.compareHandle.setAttribute('aria-valuenow', String(Math.round(state.compareValue)));
        }
    }

    function setZoom(value){
        state.zoom = Math.max(1, Math.min(8, Math.round(Number(value) * 100) / 100));
        activeWorkspace().zoom = state.zoom;
        if(state.compareViewer) state.compareViewer.setZoom(state.zoom, true);
        else {
            el.compareStage.style.setProperty('--ec-zoom', String(state.zoom));
            el.zoomReset.textContent = `${state.zoom.toFixed(state.zoom % 1 ? 1 : 0)}×`;
        }
    }

    function syncCompareGeometry(){
        if(!el.compareStage) return;
        el.compareStage.style.setProperty('--compare-stage-width', `${el.compareStage.clientWidth}px`);
        state.compareViewer?.refresh();
    }

    function setGenerationVisible(visible, message=''){
        el.generationOverlay.classList.toggle('hidden', !visible);
        el.generationMessage.textContent = message || '';
        clearInterval(state.generationTimer);
        state.generationTimer = null;
        if(!visible || !state.routeActive || document.hidden) return;
        const started = Number(state.currentTask?.created_at || Date.now() / 1000);
        const update = () => {
            const elapsed = Math.max(0, Math.floor(Date.now() / 1000 - started));
            const minutes = String(Math.floor(elapsed / 60)).padStart(2,'0');
            const seconds = String(elapsed % 60).padStart(2,'0');
            el.generationTimer.textContent = `${minutes}:${seconds}`;
        };
        update();
        state.generationTimer = setInterval(update, 1000);
    }

    function formatTaskElapsed(task){
        const started = Number(task?.created_at || Date.now() / 1000);
        const elapsed = Math.max(0, Math.floor(Date.now() / 1000 - started));
        const minutes = String(Math.floor(elapsed / 60)).padStart(2,'0');
        const seconds = String(elapsed % 60).padStart(2,'0');
        return `${minutes}:${seconds}`;
    }

    function updateCandidateTimers(){
        el.candidateList?.querySelectorAll('[data-task-candidate-time]').forEach(label => {
            const task = state.tasksById.get(String(label.dataset.taskCandidateTime || ''));
            if(task) label.textContent = formatTaskElapsed(task);
        });
    }

    function syncCandidateTimer(){
        clearInterval(state.candidateTimer);
        state.candidateTimer = null;
        if(!state.routeActive || document.hidden || !el.candidateList?.querySelector('[data-task-candidate-time]')) return;
        updateCandidateTimers();
        state.candidateTimer = setInterval(updateCandidateTimers, 1000);
    }

    function pauseEcommerceRouteMedia(){
        document.querySelectorAll('video,audio').forEach(media => {
            if(media.paused) return;
            media.dataset.routePausedByStudio = '1';
            media.pause?.();
        });
    }

    function resumeEcommerceRouteMedia(){
        document.querySelectorAll('video[data-route-paused-by-studio="1"],audio[data-route-paused-by-studio="1"]').forEach(media => {
            delete media.dataset.routePausedByStudio;
            const playResult = media.play?.();
            playResult?.catch?.(() => {});
        });
    }

    function setEcommerceRouteActive(active){
        state.routeActive = Boolean(active);
        document.documentElement.classList.toggle('studio-route-inactive', !state.routeActive);
        if(!state.routeActive || document.hidden){
            clearTimeout(state.taskPollTimer);
            state.taskPollTimer = null;
            clearInterval(state.generationTimer);
            state.generationTimer = null;
            clearInterval(state.candidateTimer);
            state.candidateTimer = null;
            pauseEcommerceRouteMedia();
            return;
        }
        resumeEcommerceRouteMedia();
        if(!el.generationOverlay.classList.contains('hidden')){
            setGenerationVisible(true, el.generationMessage.textContent);
        }
        syncCandidateTimer();
        scheduleTaskPolling(50);
    }

    function taskIdOf(task){
        return String(task?.id || task?.task_id || '');
    }

    function isTaskActive(task){
        return ['queued','running'].includes(String(task?.status || ''));
    }

    function taskMatchesWorkspace(task){
        const promptPolicy = String(task?.options?.prompt_policy || task?.request?.options?.prompt_policy || '');
        return IS_FREE_CREATION ? promptPolicy === 'free' : promptPolicy !== 'free';
    }

    function pruneTaskMemory(){
        if(state.tasks.length <= ECOMMERCE_TASK_MEMORY_LIMIT) return;
        const protectedIds = new Set(state.activeTaskIds);
        const currentId = taskIdOf(state.currentTask);
        if(currentId) protectedIds.add(currentId);
        const savedTaskId = String(sessionStorage.getItem(CURRENT_TASK_KEY) || '');
        if(savedTaskId) protectedIds.add(savedTaskId);
        Object.values(state.workspaces).forEach(workspace => {
            const taskId = String(workspace.taskId || taskIdOf(workspace.currentTask) || '');
            if(taskId) protectedIds.add(taskId);
        });
        const retained = [];
        for(const task of state.tasks) {
            const id = taskIdOf(task);
            if(protectedIds.has(id) || retained.length < ECOMMERCE_TASK_MEMORY_LIMIT) {
                retained.push(task);
            }
        }
        state.tasks = retained;
        const retainedIds = new Set(retained.map(taskIdOf));
        for(const id of state.tasksById.keys()) {
            if(!retainedIds.has(id)) state.tasksById.delete(id);
        }
    }

    function storeTask(task){
        const id = taskIdOf(task);
        if(!id) return null;
        const previous = state.tasksById.get(id) || {};
        const normalized = {...previous, ...task, id, task_id:id};
        state.tasksById.set(id, normalized);
        if(isTaskActive(normalized)) state.activeTaskIds.add(id);
        else state.activeTaskIds.delete(id);
        const existingIndex = state.tasks.findIndex(item => taskIdOf(item) === id);
        if(existingIndex >= 0) state.tasks[existingIndex] = normalized;
        else state.tasks.push(normalized);
        state.tasks.sort((a,b) => Number(b.created_at || 0) - Number(a.created_at || 0));
        pruneTaskMemory();
        Object.values(state.workspaces).forEach(workspace => {
            if(taskIdOf(workspace.currentTask) === id || workspace.taskId === id) {
                workspace.currentTask = normalized;
            }
        });
        return normalized;
    }

    function renderTaskResult(task){
        task = storeTask(task) || task;
        state.currentTask = task;
        const workspace = activeWorkspace();
        workspace.currentTask = task;
        workspace.taskId = taskIdOf(task);
        const comparisonReference = syncComparisonReference(task);
        const sourceUrl = comparisonReference?.url || '';
        const images = task?.result?.images || [];
        el.emptyResult.classList.add('hidden');
        el.resultWorkspace.classList.remove('hidden');
        hideResultPreviewError();
        const active = ['queued','running'].includes(task?.status);
        if(active) {
            const displayedUrl = images[0] || sourceUrl;
            setComparisonForeground(el.afterImage, displayedUrl);
            setComparisonBackdrops(displayedUrl);
            renderResultMeta(task);
            setGenerationVisible(true, t(task.status === 'queued' ? 'ecommerce.queued' : 'ecommerce.running'));
        } else {
            setGenerationVisible(false);
            if(images.length) {
                if(state.selectedOutput >= images.length) state.selectedOutput = 0;
                const displayedUrl = images[state.selectedOutput];
                setComparisonForeground(el.afterImage, displayedUrl);
                setComparisonBackdrops(displayedUrl);
                renderResultMeta(task);
            } else {
                setComparisonForeground(el.afterImage, sourceUrl);
                setComparisonBackdrops(sourceUrl);
                renderResultMeta(task);
            }
            if(['failed','interrupted'].includes(task?.status)) {
                clearFormError();
                showTaskResultError(task);
            }
        }
        setCompareValue(state.compareValue);
        setZoom(state.zoom);
        requestAnimationFrame(syncCompareGeometry);
        renderCandidateRail();
        sessionStorage.setItem(CURRENT_TASK_KEY, taskIdOf(task));
    }

    function candidateRailItems(){
        const tasks = state.tasks.filter(task => task.operation === state.operation && taskMatchesWorkspace(task)).slice(0,100);
        let completedOrder = 0;
        return tasks.flatMap(task => {
            const id = taskIdOf(task);
            const images = task?.result?.images || [];
            const placeholderCount = requestedOutputCountForTask(task);
            if(!images.length) return Array.from({length:placeholderCount}, (_,index) => ({id,index,url:'',status:task.status || 'queued',task}));
            const completed = images.map((url,index) => ({id,index,url,status:task.status,task,display_index:++completedOrder}));
            if(images.length && !isTaskActive(task)) return completed;
            const pendingCount = Math.max(0, placeholderCount - images.length);
            return [
                ...completed,
                ...Array.from({length:pendingCount}, (_,offset) => ({id,index:images.length + offset,url:'',status:task.status || 'queued',task})),
            ];
        }).slice(0,160);
    }

    function requestedOutputCountForTask(task){
        const parameters = task?.parameters || task?.request?.parameters || {};
        const count = Number(parameters.count ?? task?.count ?? task?.request?.count ?? 0);
        return [1,2,3,4].includes(count) ? count : 1;
    }

    function completedCandidateItems(){
        return candidateRailItems().filter(item => item.url);
    }

    function focusCandidateButton(taskId, index){
        requestAnimationFrame(() => {
            const selector = `[data-task-candidate="${CSS.escape(String(taskId || ''))}"][data-candidate-index="${Number(index)}"]`;
            el.candidateList?.querySelector(selector)?.focus({preventScroll:true});
        });
    }

    function selectCandidateItem(item, options={}){
        const task = state.tasksById.get(String(item?.id || ''));
        if(!task || !item?.url) return false;
        state.selectedOutput = Math.max(0, Number(item.index || 0));
        activeWorkspace().selectedOutput = state.selectedOutput;
        renderTaskResult(task);
        if(options.focus !== false) focusCandidateButton(item.id, item.index);
        if(options.persist !== false) persistSettings();
        return true;
    }

    function currentCompletedCandidateIndex(items){
        const currentId = taskIdOf(state.currentTask);
        return items.findIndex(item => item.id === currentId && item.index === state.selectedOutput);
    }

    function navigateCompletedResult(step){
        const items = completedCandidateItems();
        if(items.length <= 1) return false;
        const direction = step >= 0 ? 1 : -1;
        const currentIndex = currentCompletedCandidateIndex(items);
        const baseIndex = currentIndex >= 0 ? currentIndex : (direction > 0 ? -1 : 0);
        const nextIndex = (baseIndex + direction + items.length) % items.length;
        return selectCandidateItem(items[nextIndex], {focus:true, persist:true});
    }

    function isEditableKeyTarget(target){
        return Boolean(target?.closest?.('input, textarea, select, [contenteditable="true"]'));
    }

    function handleResultNavigationKeydown(event){
        if(event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
        const steps = {ArrowLeft:-1,ArrowUp:-1,ArrowRight:1,ArrowDown:1};
        if(!(event.key in steps)) return;
        if(document.querySelector('dialog[open]') || isEditableKeyTarget(event.target)) return;
        if(el.resultWorkspace?.classList.contains('hidden')) return;
        if(navigateCompletedResult(steps[event.key])) event.preventDefault();
    }

    function renderCandidateRail(){
        const items = candidateRailItems();
        el.candidateList.innerHTML = items.map(item => {
            const selected = item.id === taskIdOf(state.currentTask) && (item.index < 0 || item.index === state.selectedOutput);
            const status = String(item.status || 'queued');
            const clearable = ['failed','interrupted'].includes(status);
            const running = ['queued','running'].includes(status);
            const sequence = Number(item.display_index || item.index + 1);
            const content = item.url
                ? `<img src="${escapeHtml(item.url)}" alt=""><span>${sequence}</span>`
                : `<span class="ec-candidate-state"><i></i><b>${escapeHtml(t(`ecommerce.${status}`))}</b>${running ? `<em class="ec-candidate-time" data-task-candidate-time="${escapeHtml(item.id)}">${escapeHtml(formatTaskElapsed(item.task))}</em>` : ''}</span>`;
            return `<div class="ec-candidate-shell">
                <button type="button" class="ec-candidate ${selected ? 'active':''} ${item.url ? '' : `status-${escapeHtml(status)}`}" data-task-candidate="${escapeHtml(item.id)}" data-candidate-index="${item.index}" data-candidate-sequence="${sequence}" aria-label="${escapeHtml(item.url ? t('ecommerce.generatedSequence',{count:sequence}) : t(`ecommerce.${status}`))}">${content}</button>
                ${clearable ? `<button type="button" class="ec-candidate-clear" data-clear-task="${escapeHtml(item.id)}" title="${escapeHtml(t('ecommerce.clearFailedTask'))}" aria-label="${escapeHtml(t('ecommerce.clearFailedTask'))}">×</button>` : ''}
            </div>`;
        }).join('');
        syncCandidateTimer();
        el.candidateList.querySelectorAll('[data-task-candidate]').forEach(button => {
            button.addEventListener('click', () => {
                const task = state.tasksById.get(String(button.dataset.taskCandidate || ''));
                if(!task) return;
                const url = button.querySelector('img')?.getAttribute('src') || '';
                if(url) {
                    selectCandidateItem({
                        id:taskIdOf(task),
                        index:Number(button.dataset.candidateIndex || 0),
                        url,
                    });
                    return;
                }
                state.selectedOutput = Math.max(0, Number(button.dataset.candidateIndex || 0));
                activeWorkspace().selectedOutput = state.selectedOutput;
                renderTaskResult(task);
                persistSettings();
            });
        });
        el.candidateList.querySelectorAll('[data-clear-task]').forEach(button => {
            button.addEventListener('click', event => {
                event.stopPropagation();
                clearTask(button.dataset.clearTask || '');
            });
        });
    }

    function metaItem(label, value){
        return `<span>${escapeHtml(label)} <strong>${escapeHtml(value || '—')}</strong></span>`;
    }

    function renderResultMeta(task){
        const result = task.result || {};
        const requestedRoute = (task.route_candidates || task.request?.route_candidates || [])[0] || {};
        const elapsed = Number(result.generation_elapsed_seconds || 0);
        const imageItem = (result.image_items || [])[state.selectedOutput] || (result.image_items || [])[0] || {};
        const actualSize = Number(imageItem.width) > 0 && Number(imageItem.height) > 0
            ? `${Number(imageItem.width)}x${Number(imageItem.height)}`
            : (result.size || task.size);
        const garmentAnalysis = result.garment_analysis || task.garment_analysis;
        const items = [
            metaItem(t('ecommerce.platformMeta'), result.provider_name || result.provider_id || task.provider_name || task.provider_id || requestedRoute.provider_name || requestedRoute.provider_id),
            metaItem(t('ecommerce.modelMeta'), result.model || task.model || requestedRoute.model),
            metaItem(t('ecommerce.sizeMeta'), actualSize),
            metaItem(t('ecommerce.candidatesMeta'), t('ecommerce.imagesCount',{count:(result.images || []).length || Number(task.count || 0)})),
            metaItem(t('ecommerce.durationMeta'), elapsed > 0 ? t('ecommerce.seconds',{count:elapsed.toFixed(1)}) : t(`ecommerce.${task.status || 'queued'}`)),
        ];
        if(garmentAnalysis?.status === 'succeeded') {
            items.push(metaItem(t('ecommerce.detectedGarmentMeta'), garmentAnalysis.garment_type || garmentAnalysis.category));
        }
        el.resultMeta.innerHTML = items.join('');
    }

    async function createTask(parentTaskId=''){
        if(!validateForm(true)) return;
        clearFormError();
        state.submissionsInFlight += 1;
        el.generateButton.classList.add('submitting');
        try {
            const payload = JSON.parse(JSON.stringify(ecommerceTaskPayload(parentTaskId)));
            const task = await fetchJson('/api/ecommerce/tasks', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify(payload),
            });
            const stored = storeTask({
                ...task,
                count:task.count ?? payload.count,
                parameters:{
                    aspect_ratio:payload.aspect_ratio,
                    resolution:payload.resolution,
                    quality:payload.quality,
                    count:payload.count,
                    ...(task.parameters || task.request?.parameters || {}),
                },
            });
            state.selectedOutput = 0;
            renderTaskResult(stored);
            renderTaskList();
            persistSettings();
            showToast(t('ecommerce.taskSubmitted'));
            scheduleTaskPolling(100);
        } catch(error) {
            if(isCompatibleModelError(error.message)) {
                clearFormError();
                showResultPreviewError(error.message);
            } else {
                showFormError(error.message);
            }
        } finally {
            state.submissionsInFlight = Math.max(0, state.submissionsInFlight - 1);
            el.generateButton.classList.toggle('submitting', state.submissionsInFlight > 0);
        }
    }

    function scheduleTaskPolling(delay=1500){
        clearTimeout(state.taskPollTimer);
        state.taskPollTimer = null;
        if(!state.routeActive || document.hidden || !state.activeTaskIds.size) return;
        state.taskPollTimer = setTimeout(pollActiveTasks, Math.max(50, Number(delay) || 1500));
    }

    async function fetchActiveTaskStatuses(ids){
        try {
            return await fetchJson('/api/ecommerce/tasks/status', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({ids}),
            });
        } catch(batchError) {
            const tasks = await Promise.all(ids.map(async id => {
                try { return await fetchJson(`/api/ecommerce/tasks/${encodeURIComponent(id)}`); }
                catch(error) { return {id,task_id:id,status:'unknown',poll_error:error.message}; }
            }));
            return {tasks};
        }
    }

    async function pollActiveTasks(){
        if(state.taskPollInflight) return;
        const ids = [...state.activeTaskIds];
        if(!ids.length) return;
        state.taskPollInflight = true;
        try {
            const response = await fetchActiveTaskStatuses(ids);
            const updates = response.tasks || [];
            const completedIds = [];
            (response.missing || []).forEach(id => {
                storeTask({
                    id,
                    task_id:id,
                    status:'interrupted',
                    error:t('ecommerce.taskLoadFailed'),
                    updated_at:Date.now() / 1000,
                });
            });
            updates.forEach(update => {
                if(update.status === 'unknown') return;
                const previous = state.tasksById.get(taskIdOf(update));
                storeTask(update);
                if(previous && isTaskActive(previous) && !isTaskActive(update) && !update.result) completedIds.push(taskIdOf(update));
            });
            if(completedIds.length) {
                const completed = await Promise.all(completedIds.map(async id => {
                    try { return await fetchJson(`/api/ecommerce/tasks/${encodeURIComponent(id)}`); }
                    catch(error) { return state.tasksById.get(id); }
                }));
                completed.filter(Boolean).forEach(storeTask);
            }
            const currentId = taskIdOf(state.currentTask);
            const current = currentId ? state.tasksById.get(currentId) : null;
            if(current) renderTaskResult(current);
            else {
                const firstCompleted = state.tasks.find(task => task.operation === state.operation && task.status === 'succeeded' && (task.result?.images || []).length);
                if(firstCompleted) renderTaskResult(firstCompleted);
                else renderCandidateRail();
            }
            renderTaskList();
        } finally {
            state.taskPollInflight = false;
            scheduleTaskPolling();
        }
    }

    async function loadTask(taskId, closeDrawer=true){
        try {
            const task = await fetchJson(`/api/ecommerce/tasks/${encodeURIComponent(taskId)}`);
            storeTask(task);
            captureWorkspace();
            if(OPERATION_CONFIG[task.operation]) state.operation = task.operation;
            restoreWorkspace(state.operation);
            state.mode = 'standard';
            if(task.operation === 'universal') {
                state.inputs = Object.fromEntries((task.inputs || []).map((item,index) => {
                    const key=String(item.reference_id || `ref_restored_${index}`);
                    return [key,{...item,reference_id:key,reference_type:item.reference_type || item.role,order:index}];
                }));
            } else {
                state.inputs = Object.fromEntries((task.inputs || []).map(item => [item.role,{...item}]));
            }
            if(task.options && DEFAULT_OPTIONS[task.operation]) state.options[task.operation] = {...DEFAULT_OPTIONS[task.operation], ...task.options};
            const parameters = task.parameters || task.request?.parameters || {};
            state.providerId = String(task.request?.provider_id ?? task.provider_id ?? state.providerId);
            state.model = String(task.request?.model ?? task.model ?? state.model);
            state.aspectRatio = ASPECT_RATIOS.includes(parameters.aspect_ratio) ? parameters.aspect_ratio : 'source';
            state.resolution = RESOLUTIONS.includes(parameters.resolution) ? parameters.resolution : 'auto';
            state.quality = QUALITIES.includes(parameters.quality) ? parameters.quality : 'auto';
            state.count = [0,1,2,3,4].includes(Number(parameters.count)) ? Number(parameters.count) : 0;
            state.selectedOutput = Number(task.approval?.output_index ?? 0);
            updateTabs();
            renderInputs();
            renderOperationControls();
            populateModelSelectors();
            syncGenerationParameterControls();
            renderTaskResult(task);
            updateRouteSummary();
            persistSettings();
            if(closeDrawer) setHistoryOpen(false);
            if(isTaskActive(task)) scheduleTaskPolling(100);
        } catch(error) {
            showToast(`${t('ecommerce.taskLoadFailed')}：${error.message}`, true);
        }
    }

    function removeTaskLocally(taskId){
        const id = String(taskId || '');
        if(!id) return;
        state.tasksById.delete(id);
        state.activeTaskIds.delete(id);
        state.tasks = state.tasks.filter(task => taskIdOf(task) !== id);
        Object.values(state.workspaces).forEach(workspace => {
            if(taskIdOf(workspace.currentTask) === id) workspace.currentTask = null;
            if(String(workspace.taskId || '') === id) workspace.taskId = '';
        });
        if(taskIdOf(state.currentTask) === id) {
            state.currentTask = null;
            const workspace = activeWorkspace();
            workspace.currentTask = null;
            workspace.taskId = '';
            const fallback = state.tasks.find(task => task.operation === state.operation && taskMatchesWorkspace(task) && task.status === 'succeeded' && (task.result?.images || []).length);
            if(fallback) renderTaskResult(fallback);
            else {
                sessionStorage.removeItem(CURRENT_TASK_KEY);
                hideResult();
                renderCandidateRail();
            }
        } else {
            renderCandidateRail();
        }
        renderTaskList();
        persistSettings();
    }

    async function clearTask(taskId){
        const id = String(taskId || '').trim();
        if(!id) return;
        const task = state.tasksById.get(id);
        if(task && !['failed','interrupted'].includes(String(task.status || ''))) return;
        try {
            await fetchJson(`/api/ecommerce/tasks/${encodeURIComponent(id)}`, {method:'DELETE'});
            removeTaskLocally(id);
            showToast(t('ecommerce.taskCleared'));
        } catch(error) {
            showToast(error.message, true);
        }
    }

    async function loadTasks(){
        try {
            const response = await fetchJsonWithTimeout('/api/ecommerce/tasks?limit=500');
            (response.tasks || []).filter(taskMatchesWorkspace).forEach(storeTask);
            renderTaskList();
            renderCandidateRail();
            scheduleTaskPolling(100);
            return state.tasks;
        } catch(error) {
            el.taskList.innerHTML = `<div class="ec-task-empty">${escapeHtml(error.message)}</div>`;
            return [];
        }
    }

    function renderTaskList(){
        const visibleTasks = state.tasks.filter(taskMatchesWorkspace);
        if(!visibleTasks.length) {
            el.taskList.innerHTML = `<div class="ec-task-empty">${escapeHtml(t(IS_FREE_CREATION ? 'freeCreation.noTasks' : 'ecommerce.noTasks'))}</div>`;
            return;
        }
        el.taskList.innerHTML = visibleTasks.slice(0,200).map(task => {
            const image = task.result?.images?.[0] || sourceUrlForTask(task);
            const operation = OPERATION_CONFIG[task.operation];
            const canRetry = !['queued','running'].includes(task.status);
            const clearable = ['failed','interrupted'].includes(String(task.status || ''));
            return `<article class="ec-task-item" data-task-id="${escapeHtml(task.id)}" tabindex="0">
                ${image ? `<img src="${escapeHtml(image)}" alt="">` : '<div class="ec-task-placeholder"></div>'}
                <div class="ec-task-info"><b>${escapeHtml(t(IS_FREE_CREATION ? 'freeCreation.title' : (operation?.titleKey || 'ecommerce.title')))}</b>
                    <span>${escapeHtml(new Date(Number(task.created_at || 0) * 1000).toLocaleString())} · ${escapeHtml(t('ecommerce.standard'))}</span>
                    <span class="ec-task-status ${escapeHtml(task.status || '')}">${escapeHtml(t(`ecommerce.${task.status || 'queued'}`))}</span>
                    <div class="ec-task-actions"><button type="button" data-open-task="${escapeHtml(task.id)}">${escapeHtml(t('ecommerce.loadTask'))}</button>${canRetry ? `<button type="button" data-retry-task="${escapeHtml(task.id)}">${escapeHtml(t('ecommerce.retry'))}</button>` : ''}${clearable ? `<button type="button" data-clear-task="${escapeHtml(task.id)}">${escapeHtml(t('ecommerce.clearFailedTask'))}</button>` : ''}</div>
                </div>
            </article>`;
        }).join('');
        el.taskList.querySelectorAll('[data-open-task]').forEach(button => button.addEventListener('click', event => {
            event.stopPropagation();
            loadTask(button.dataset.openTask);
        }));
        el.taskList.querySelectorAll('[data-retry-task]').forEach(button => button.addEventListener('click', async event => {
            event.stopPropagation();
            await loadTask(button.dataset.retryTask);
            await createTask(button.dataset.retryTask);
        }));
        el.taskList.querySelectorAll('[data-clear-task]').forEach(button => button.addEventListener('click', event => {
            event.stopPropagation();
            clearTask(button.dataset.clearTask || '');
        }));
        el.taskList.querySelectorAll('.ec-task-item').forEach(item => {
            item.addEventListener('click', () => loadTask(item.dataset.taskId));
            item.addEventListener('keydown', event => {
                if(event.key === 'Enter') loadTask(item.dataset.taskId);
            });
        });
    }

    function setHistoryOpen(open){
        el.taskDrawer.classList.toggle('open', !!open);
        el.taskDrawer.setAttribute('aria-hidden', open ? 'false' : 'true');
        el.drawerBackdrop.classList.toggle('hidden', !open);
        if(open) loadTasks();
    }

    function downloadSelectedPreview(){
        const url = state.currentTask?.result?.images?.[state.selectedOutput];
        if(!url) return;
        const link = document.createElement('a');
        link.href = url;
        link.download = `ecommerce-work-${state.currentTask.operation || 'image'}-${state.selectedOutput + 1}`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        showToast(t('ecommerce.previewDownloaded'));
    }

    function openQualityReview(){
        const task = state.currentTask;
        if(task?.status !== 'succeeded') return;
        const checks = state.capabilities?.quality_checks?.[task.operation] || [];
        const approved = task.approval?.status === 'approved' && Number(task.approval.output_index) === state.selectedOutput;
        el.qualityChecks.innerHTML = checks.map(item => `<label class="ec-quality-check">
            <input type="checkbox" data-quality-id="${escapeHtml(item.id)}" ${approved && task.approval?.checks?.[item.id] ? 'checked':''}>
            <span>${escapeHtml(localizedLabel(item))}</span>
        </label>`).join('');
        el.qualityNote.value = approved ? (task.approval?.note || '') : '';
        el.qualityDialog.showModal();
    }

    async function approveSelectedCandidate(event){
        event.preventDefault();
        if(event.submitter?.value === 'cancel') {
            el.qualityDialog.close();
            return;
        }
        const inputs = Array.from(el.qualityChecks.querySelectorAll('[data-quality-id]'));
        if(!inputs.length || inputs.some(input => !input.checked)) {
            showToast(t('ecommerce.approveAll'), true);
            return;
        }
        const checks = Object.fromEntries(inputs.map(input => [input.dataset.qualityId, true]));
        try {
            const response = await fetchJson(`/api/ecommerce/tasks/${encodeURIComponent(state.currentTask.id)}/approve`, {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({output_index:state.selectedOutput, checks, note:el.qualityNote.value || ''}),
            });
            state.currentTask.approval = response.approval;
            const stored = state.tasks.find(item => item.id === state.currentTask.id);
            if(stored) stored.approval = response.approval;
            el.qualityDialog.close();
            renderTaskList();
            showToast(t('ecommerce.approved'));
        } catch(error) {
            showToast(error.message, true);
        }
    }

    async function ensureOfficialExport(){
        const task = state.currentTask;
        const currentApproval = task?.approval || {};
        if(currentApproval.status !== 'approved' || Number(currentApproval.output_index) !== state.selectedOutput) {
            throw new Error(t('ecommerce.exportBlocked'));
        }
        if(currentApproval.export?.url) return currentApproval.export;
        const response = await fetchJson(`/api/ecommerce/tasks/${encodeURIComponent(task.id)}/export`, {method:'POST'});
        task.approval.export = response.export;
        const stored = state.tasks.find(item => item.id === task.id);
        if(stored?.approval) stored.approval.export = response.export;
        return response.export;
    }

    async function exportSelectedCandidate(){
        try {
            const exported = await ensureOfficialExport();
            const link = document.createElement('a');
            link.href = exported.url;
            link.download = exported.name || 'ecommerce-listing-image';
            document.body.appendChild(link);
            link.click();
            link.remove();
            showToast(t('ecommerce.exported'));
        } catch(error) {
            showToast(error.message, true);
        }
    }

    async function saveApprovedAsset(){
        const library = selectedAssetLibrary();
        const category = selectedAssetCategory();
        if(!library || !category) {
            showToast(t('ecommerce.selectCategory'), true);
            return;
        }
        el.assetSaveConfirm.disabled = true;
        try {
            const exported = await ensureOfficialExport();
            const response = await fetchJson('/api/asset-library/items', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({
                    library_id:library.id,
                    category_id:category.id,
                    url:exported.url,
                    name:exported.name || `ecommerce-${state.currentTask.operation}.png`,
                }),
            });
            state.assetLibrary = response.library || state.assetLibrary;
            el.assetDialog.close();
            showToast(t('ecommerce.saved'));
        } catch(error) {
            showToast(error.message, true);
        } finally {
            el.assetSaveConfirm.disabled = false;
        }
    }

    function bindComparison(){
        state.compareViewer = new window.CompareViewer({
            root:el.compareStage,
            before:el.beforeImage,
            after:el.afterImage,
            afterClip:el.afterClip,
            handle:el.compareHandle,
            zoomLabel:el.zoomReset,
            zoomInButton:el.zoomIn,
            zoomOutButton:el.zoomOut,
            fullscreenButton:el.compareFullscreen,
            divider:state.compareValue,
            scale:state.zoom,
            onChange:next => {
                state.compareValue = next.divider;
                state.zoom = next.scale;
                const workspace = activeWorkspace();
                workspace.compareValue = next.divider;
                workspace.zoom = next.scale;
                scheduleSettingsPersistence();
            },
        });
        el.compareReset.addEventListener('click', () => {
            state.compareViewer.reset();
            state.compareValue = 50;
            state.zoom = 1;
            persistSettings();
        });
        window.addEventListener('resize', syncCompareGeometry);
    }

    function compatibleModels(){
        const models = state.capabilities?.models || [];
        let referenceCount = 0;
        if(currentConfig()?.universal) {
            referenceCount = universalEntries().filter(([,item]) => item.url).length;
        } else if(state.operation === 'try_on') {
            referenceCount = taskInputsForRequest().length;
        }
        if(referenceCount <= 1) return models;
        return models.filter(item => Number(item.max_reference_images || 0) >= referenceCount);
    }

    function populateModelSelectors(){
        const providers = state.capabilities?.providers || [];
        const models = compatibleModels();
        const previousProvider = state.providerId;
        const previousModel = state.model;
        state.providerId = providers.some(item => item.id === state.providerId) ? state.providerId : (providers[0]?.id || '');
        el.providerSelect.innerHTML = providers.length
            ? providers.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name || item.id)}</option>`).join('')
            : `<option value="">${escapeHtml(t('ecommerce.noConfiguredProvider'))}</option>`;
        el.providerSelect.value = state.providerId;
        el.providerSelect.disabled = providers.length === 0;
        const filtered = state.providerId ? models.filter(item => item.provider_id === state.providerId) : [];
        const recommended = resolveRecommendedRoute(state.providerId);
        const automaticLabel = recommended?.model
            ? t('ecommerce.autoRecommended',{model:recommended.model})
            : t('ecommerce.auto');
        el.modelSelect.innerHTML = `<option value="">${escapeHtml(automaticLabel)}</option>` + filtered.map(item => `<option value="${escapeHtml(item.model)}">${escapeHtml(item.model)}</option>`).join('');
        el.modelSelect.value = filtered.some(item => item.model === state.model) ? state.model : '';
        if(!el.modelSelect.value) state.model = '';
        el.modelSelect.disabled = filtered.length === 0;
        updateModelPanelSelection();
        if(!state.initializing && (previousProvider !== state.providerId || previousModel !== state.model)) persistSettings();
    }

    function syncGenerationParameterControls(){
        const sourceCompositionLocked = state.operation === 'background_change';
        if(el.ratioSelect) {
            el.ratioSelect.value = sourceCompositionLocked ? 'source' : (ASPECT_RATIOS.includes(state.aspectRatio) ? state.aspectRatio : 'source');
            el.ratioSelect.disabled = sourceCompositionLocked;
        }
        if(el.resolutionSelect) el.resolutionSelect.value = RESOLUTIONS.includes(state.resolution) ? state.resolution : 'auto';
        if(el.qualitySelect) el.qualitySelect.value = QUALITIES.includes(state.quality) ? state.quality : 'auto';
        if(el.countSelect) el.countSelect.value = String([0,1,2,3,4].includes(Number(state.count)) ? Number(state.count) : 0);
    }

    function resolveRecommendedRoute(providerId=''){
        const models = compatibleModels();
        const route = state.capabilities?.routes?.standard;
        const routeCompatible = route && models.some(item => item.provider_id === route.provider_id && item.model === route.model);
        if(providerId && (!routeCompatible || route?.provider_id !== providerId)) return models.find(item => item.provider_id === providerId) || null;
        return routeCompatible ? route : (models[0] || null);
    }

    function updateModelPanelSelection(){
        const provider = (state.capabilities?.providers || []).find(item => item.id === state.providerId);
        const route = state.model
            ? (state.capabilities?.models || []).find(item => item.provider_id === state.providerId && item.model === state.model)
            : resolveRecommendedRoute(state.providerId);
        if(el.modelPanelSelection) {
            const modelText = state.model || (route?.model ? t('ecommerce.autoRecommended',{model:route.model}) : t('ecommerce.noConfiguredModel'));
            el.modelPanelSelection.textContent = provider ? `${provider.name || provider.id} · ${modelText}` : t('ecommerce.noConfiguredProvider');
        }
        el.advancedSettings?.classList.toggle('collapsed', state.modelPanelCollapsed);
        el.modelPanelToggle?.setAttribute('aria-expanded', state.modelPanelCollapsed ? 'false' : 'true');
    }

    function updateRouteSummary(){
        const route = resolveDisplayedRoute();
        const strong = el.routeSummary?.querySelector('strong');
        if(strong) strong.textContent = route ? `${route.provider_name || route.provider_id} · ${route.model}` : '—';
        updateModelPanelSelection();
    }

    function resolveDisplayedRoute(){
        const models = compatibleModels();
        if(state.model) {
            return models.find(item => item.model === state.model && (!state.providerId || item.provider_id === state.providerId));
        }
        const route = state.capabilities?.routes?.standard;
        if(state.providerId && route?.provider_id !== state.providerId) {
            return models.find(item => item.provider_id === state.providerId) || route;
        }
        return route || null;
    }

    function updateCapabilityStatus(){
        if(!state.capabilities || !el.capabilityStatus) return;
        const count = state.capabilities.models?.length || 0;
        el.capabilityStatus.textContent = t(count > 0 ? 'ecommerce.enginesReady' : 'ecommerce.noEngine', {count});
        el.capabilityStatus.classList.toggle('ready', count > 0);
        el.capabilityStatus.classList.toggle('error', count <= 0);
    }

    async function loadCapabilities(){
        try {
            state.capabilities = await fetchJsonWithTimeout('/api/ecommerce/capabilities');
            state.referenceSlotTypes = Array.isArray(state.capabilities.reference_slot_types) ? state.capabilities.reference_slot_types : [];
            const reconciledSlotTypes = reconcileUniversalSlotTypes();
            updateCapabilityStatus();
            populateModelSelectors();
            renderInputs();
            renderOperationControls();
            updateRouteSummary();
            if(reconciledSlotTypes) persistSettings();
        } catch(error) {
            state.capabilities = {models:[],providers:[],routes:{},pose_presets:[],background_presets:[],studio_reference_presets:[]};
            state.referenceSlotTypes = [];
            updateCapabilityStatus();
            populateModelSelectors();
            renderInputs();
            renderOperationControls();
            updateRouteSummary();
        }
    }

    function bindBaseEvents(){
        document.addEventListener('pointerdown', () => { state.lastPointerDownAt = Date.now(); }, true);
        el.operationTabs.addEventListener('click', event => {
            const button = event.target.closest('[data-operation]');
            if(button) switchOperation(button.dataset.operation);
        });
        el.modeToggle?.addEventListener('click', event => {
            const button = event.target.closest('[data-mode]');
            if(button) switchMode(button.dataset.mode);
        });
        el.providerSelect.addEventListener('change', () => {
            state.providerId = el.providerSelect.value;
            state.model = '';
            populateModelSelectors();
            updateRouteSummary();
            persistSettings();
        });
        el.modelSelect.addEventListener('change', () => {
            state.model = el.modelSelect.value;
            updateRouteSummary();
            persistSettings();
        });
        el.ratioSelect.addEventListener('change', () => {
            state.aspectRatio = ASPECT_RATIOS.includes(el.ratioSelect.value) ? el.ratioSelect.value : 'source';
            persistSettings();
        });
        el.resolutionSelect.addEventListener('change', () => {
            state.resolution = RESOLUTIONS.includes(el.resolutionSelect.value) ? el.resolutionSelect.value : 'auto';
            persistSettings();
        });
        el.qualitySelect.addEventListener('change', () => {
            state.quality = QUALITIES.includes(el.qualitySelect.value) ? el.qualitySelect.value : 'auto';
            persistSettings();
        });
        el.countSelect.addEventListener('change', () => {
            state.count = [0,1,2,3,4].includes(Number(el.countSelect.value)) ? Number(el.countSelect.value) : 0;
            persistSettings();
        });
        el.modelPanelToggle.addEventListener('click', () => {
            state.modelPanelCollapsed = !state.modelPanelCollapsed;
            updateModelPanelSelection();
            persistSettings();
        });
        el.generateButton.addEventListener('click', () => createTask());
        document.addEventListener('keydown', handleResultNavigationKeydown);
        el.resultErrorClear?.addEventListener('click', () => clearTask(el.resultErrorClear.dataset.clearTask || ''));
        el.historyToggle.addEventListener('click', () => setHistoryOpen(true));
        el.closeHistory.addEventListener('click', () => setHistoryOpen(false));
        el.drawerBackdrop.addEventListener('click', () => setHistoryOpen(false));
        el.qualityForm.addEventListener('submit', approveSelectedCandidate);
        el.cancelQuality.addEventListener('click', () => el.qualityDialog.close());
        el.assetSaveConfirm.addEventListener('click', saveApprovedAsset);
        el.assetLibrarySelect.addEventListener('change', renderAssetLibrarySelectors);
        el.assetCategorySelect.addEventListener('change', renderAssetGrid);
        el.assetReferenceTypeSelect?.addEventListener('change', renderAssetGrid);
        el.studioClear?.addEventListener('click', clearStudioReference);
        byId('fileInput')?.addEventListener('change', event => {
            const files = Array.from(event.target.files || []);
            if(files.length) handleSelectedFiles(files, state.activeUploadRole);
            event.target.value = '';
        });
        document.addEventListener('paste', event => {
            if(document.querySelector('dialog[open]')) return;
            const file = Array.from(event.clipboardData?.files || []).find(item => item.type.startsWith('image/'));
            if(!file) return;
            const config = currentConfig();
            let role = config.inputs.find(item => !state.inputs[item.role])?.role || 'source';
            if(config.universal) {
                seedUniversalPresetsIfEmpty();
                const available = universalEntries().find(([,item]) => !item.url);
                if(available) role = available[0];
                else {
                    const limit = Number(state.capabilities?.universal_reference_limit || 14);
                    if(universalEntries().length >= limit) return;
                    role = createUniversalReference('prop', universalEntries().length);
                    renderUniversalInputs();
                }
            }
            handleSelectedFile(file, role);
        });
        window.addEventListener('message', event => {
            if(event.origin && event.origin !== location.origin) return;
            if(event.data?.type === 'studio-route-active') setEcommerceRouteActive(event.data.active);
            if(event.data?.type === 'studio-language') window.StudioI18n?.set?.(event.data.lang,{sync:false});
            if(event.data?.type === 'providers-changed') loadCapabilities();
            const incomingSettings = !IS_FREE_CREATION && event.data?.type === 'canvas.preferences' ? event.data?.values?.ecommerce_settings : '';
            if(incomingSettings && incomingSettings !== state.settingsSerialized) {
                if(shouldIgnoreIncomingSettings()) return;
                applyIncomingSettings(String(incomingSettings));
            }
        });
        window.addEventListener('studio-lang-change', () => {
            updateTabs();
            renderInputs();
            renderOperationControls();
            populateModelSelectors();
            syncGenerationParameterControls();
            updateCapabilityStatus();
            if(el.studioDialog?.open) renderStudioDialog();
        });
        window.addEventListener('resize', () => {
            const previousWidth = state.viewportWidth;
            state.viewportWidth = window.innerWidth;
            if(previousWidth > 860 && state.viewportWidth <= 860 && currentConfig()?.universal) {
                requestAnimationFrame(() => { el.inputSlots.scrollLeft = 0; });
            }
        });
        window.addEventListener('pagehide', () => {
            clearTimeout(state.taskPollTimer);
            clearInterval(state.generationTimer);
            pauseEcommerceRouteMedia();
            flushScheduledSettingsPersistence();
        });
        document.addEventListener('visibilitychange', () => setEcommerceRouteActive(state.routeActive));
    }

    function renderInitialWorkspace(){
        restoreWorkspace(state.operation);
        syncGenerationParameterControls();
        updateTabs();
        renderInputs();
        renderOperationControls();
        if(el.generateButton) el.generateButton.disabled = true;
        el.ecommercePage?.setAttribute('aria-busy', 'true');
    }

    async function init(){
        cacheElements();
        configureWorkspaceVariant();
        renderInitialWorkspace();
        await waitForPreferenceBootstrap();
        loadSettings();
        restoreWorkspace(state.operation);
        state.settingsNeedsMigration = false;
        syncGenerationParameterControls();
        updateTabs();
        renderInputs();
        renderOperationControls();
        bindBaseEvents();
        bindUniversalDockDrop();
        bindReferencePreview();
        bindComparison();
        await Promise.all([loadCapabilities(), loadTasks()]);
        const savedTaskId = activeWorkspace().taskId || sessionStorage.getItem(CURRENT_TASK_KEY);
        if(savedTaskId && state.tasks.some(item => item.id === savedTaskId)) await loadTask(savedTaskId, false);
        state.initializing = false;
        if(el.generateButton) el.generateButton.disabled = false;
        el.ecommercePage?.setAttribute('aria-busy', 'false');
    }

    window.EcommerceStudio = {
        state,
        config:OPERATION_CONFIG,
        t,
        renderInputs,
        renderOperationControls,
        validateForm,
        showFormError,
        clearFormError,
        hideResult,
        updateRouteSummary,
        openAssetPicker:openAssetPickerForRole,
        uploadInput,
        uploadInputPairs,
        createTask,
        loadTask,
        comparisonReferenceForTask,
        syncComparisonReference,
        renderTaskResult,
    };
    document.addEventListener('DOMContentLoaded', init, {once:true});
})();
