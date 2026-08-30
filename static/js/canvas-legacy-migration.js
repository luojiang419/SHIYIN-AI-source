/* Compatibility migration for canvases created before the unified canvas entry. */
(function installCanvasLegacyMigration(root, factory){
    const api = factory();
    if(typeof module === 'object' && module.exports) module.exports = api;
    if(root) root.CanvasLegacySmartMigration = api;
})(typeof window !== 'undefined' ? window : globalThis, function createCanvasLegacyMigration(){
    'use strict';

    const SPECIAL_TYPES = {
        panorama:'panorama',
        dwpose:'dwpose',
        'director3d':'director3d',
        'pose-replicate':'poseReplicate',
        angle:'angle',
        'multi-view':'multiView',
        'batch-generator':'batchGenerator',
        'film-storyboard':'film-storyboard',
        'film-video':'film-video',
        'film-line-art':'film-line-art',
    };

    function mediaUrl(value){
        if(typeof value === 'string') return value.trim();
        if(!value || typeof value !== 'object') return '';
        return String(value.url || value.src || value.path || value.output_url || '').trim();
    }

    function mediaItem(value, fallbackName='image'){
        if(typeof value === 'string') return {url:mediaUrl(value), name:fallbackName, kind:'image'};
        if(!value || typeof value !== 'object') return null;
        const url = mediaUrl(value);
        if(!url) return null;
        const kind = String(value.kind || value.mediaKind || value.type || 'image').toLowerCase();
        return {
            ...value,
            url,
            name:String(value.name || value.filename || fallbackName),
            kind:kind === 'video' || kind === 'audio' ? kind : 'image',
            mediaKind:kind === 'video' || kind === 'audio' ? kind : 'image',
        };
    }

    function promptText(node){
        const direct = [node.text, node.prompt, node.promptText, node.fixedPrompt, node.variablePrompt]
            .map(value => typeof value === 'string' ? value.trim() : '')
            .find(Boolean);
        if(direct) return direct;
        const items = Array.isArray(node.promptItems) ? node.promptItems : Array.isArray(node.segments) ? node.segments : [];
        return items.map(item => typeof item === 'string' ? item : item?.text || item?.content || '')
            .map(value => String(value || '').trim()).filter(Boolean).join('\n\n');
    }

    function uniqueId(base, used){
        let id = base;
        let suffix = 2;
        while(used.has(id)) id = `${base}-${suffix++}`;
        used.add(id);
        return id;
    }

    function migrate(sourceNodes){
        const input = Array.isArray(sourceNodes) ? sourceNodes : [];
        const used = new Set(input.map(node => String(node?.id || '')).filter(Boolean));
        const output = [];
        let changed = false;
        const childrenByLegacyId = new Map();

        input.forEach(raw => {
            if(!raw || typeof raw !== 'object') return;
            const node = {...raw};
            const type = String(node.type || '').toLowerCase();
            if(!['smart-image','smart-prompt','smart-loop','smart-group'].includes(type)){
                output.push(node);
                return;
            }
            changed = true;
            if(type === 'smart-prompt'){
                node.type = 'prompt';
                node.text = promptText(node);
                delete node.promptItems;
                delete node.segments;
                output.push(node);
                return;
            }
            if(type === 'smart-loop'){
                node.type = 'loop';
                node.count = Math.max(1, Math.min(100, Number(node.count || 1) || 1));
                node.mode = node.mode || 'serial';
                node.showPrompt = Boolean(node.showPrompt);
                node.imageInput = Boolean(node.imageInput);
                node.videoInput = Boolean(node.videoInput);
                node.loopStart = Math.max(1, Number(node.loopStart || 1) || 1);
                node.imageBatchSize = Math.max(1, Number(node.imageBatchSize || 1) || 1);
                node.videoBatchSize = Math.max(1, Number(node.videoBatchSize || 1) || 1);
                node.variablePrompt = String(node.variablePrompt || '');
                node.fixedPrompt = String(node.fixedPrompt || '');
                output.push(node);
                return;
            }

            const images = (Array.isArray(node.images) ? node.images : [])
                .map((item, index) => mediaItem(item, `${node.title || 'image'}-${index + 1}`)).filter(Boolean);
            if(!images.length){
                const direct = mediaItem(node.url, node.name || 'image');
                if(direct) images.push(direct);
            }
            const specialType = SPECIAL_TYPES[String(node.specialType || '').toLowerCase()];
            if(specialType){
                node.type = specialType;
                if(images.length && !node.url) node.url = images[0].url;
                if(images.length && !node.name) node.name = images[0].name;
                output.push(node);
                return;
            }
            if(type === 'smart-group' || images.length > 1){
                node.type = 'group';
                const existingItems = Array.isArray(node.items) ? node.items.filter(Boolean) : [];
                const childIds = [];
                images.forEach((item, index) => {
                    const childId = uniqueId(`${node.id || 'legacy-smart'}-image-${index + 1}`, used);
                    childIds.push(childId);
                    output.push({
                        id:childId,
                        type:'image',
                        x:(Number(node.x) || 0) + index * 36,
                        y:(Number(node.y) || 0) + index * 36,
                        url:item.url,
                        name:item.name || `image-${index + 1}`,
                        mediaKind:item.mediaKind || item.kind || 'image',
                        kind:item.kind || item.mediaKind || 'image',
                        natural_w:Number(item.natural_w || item.width || 0) || 0,
                        natural_h:Number(item.natural_h || item.height || 0) || 0,
                    });
                });
                node.items = Array.from(new Set([...existingItems, ...childIds]));
                delete node.images;
                delete node.url;
                delete node.name;
                childrenByLegacyId.set(node.id, childIds);
                output.push(node);
                return;
            }
            node.type = 'image';
            const item = images[0];
            if(item){
                node.url = item.url;
                node.name = item.name || node.name || 'image';
                node.mediaKind = item.mediaKind || item.kind || 'image';
                node.kind = item.kind || item.mediaKind || 'image';
                node.natural_w = Number(item.natural_w || item.width || node.natural_w || 0) || 0;
                node.natural_h = Number(item.natural_h || item.height || node.natural_h || 0) || 0;
            } else {
                node.url = String(node.url || '');
                node.name = node.name || '空白图片';
            }
            delete node.images;
            output.push(node);
        });
        return {nodes:output, changed};
    }

    return Object.freeze({migrate});
});
