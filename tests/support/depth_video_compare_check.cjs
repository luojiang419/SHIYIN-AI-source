const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

(async()=>{
    const root = path.resolve(__dirname, '../..');
    const browser = await chromium.launch({headless:true, channel:'chrome'});
    try{
        const page = await browser.newPage({viewport:{width:1280,height:800}});
        const errors=[];
        page.on('pageerror', error => errors.push(error.message));
        await page.setContent('<!doctype html><html><head></head><body><main id="node"></main></body></html>');
        await page.addStyleTag({path:path.join(root,'static/css/canvas-special-nodes.css')});
        await page.addScriptTag({path:path.join(root,'static/js/canvas-special-nodes.js')});
        const result = await page.evaluate(async()=>{
            const media='data:video/mp4;base64,AAAA';
            const signature=`${media}|source.mp4|x`;
            const node={depthVideoStatus:'done',depthVideoManualInput:{url:media,name:'source.mp4'},depthVideoInputUrl:media,depthVideoInputSignature:signature,depthVideoGeneratedSignature:signature,outputUrl:media,outputName:'depth.mp4',outputKind:'video'};
            const root=document.querySelector('#node');
            root.innerHTML=window.CanvasSpecialNodes.depthVideoBodyHtml(node);
            const videos=[...root.querySelectorAll('video')];
            videos.forEach(video=>{
                Object.defineProperty(video,'duration',{configurable:true,value:20});
                Object.defineProperty(video,'paused',{configurable:true,get(){return !this.__playing;}});
                video.play=function(){this.__playing=true;this.dispatchEvent(new Event('play'));return Promise.resolve();};
                video.pause=function(){this.__playing=false;this.dispatchEvent(new Event('pause'));};
            });
            window.CanvasSpecialNodes.bindDepthVideo(root,node,{});
            videos[1].currentTime=5; videos[1].dispatchEvent(new Event('timeupdate'));
            root.querySelector('[data-special-action="open-depth-video-controls"]').click();
            const controlsDialog=document.querySelector('.depth-video-control-modal');
            for(const [key,value] of Object.entries({brightness:180,contrast:140,gamma:75,blur:2,invert:true})){
                const control=controlsDialog.querySelector(`[data-depth-video-control="${key}"]`);
                if(control.type === 'checkbox') control.checked=value;
                else control.value=String(value);
                control.dispatchEvent(new Event('input',{bubbles:true}));
            }
            controlsDialog.querySelector('[data-depth-video-done]').click();
            root.querySelector('[data-special-action="compare-depth-video"]').click();
            const dialog=document.querySelector('.depth-video-compare-modal');
            const compare=[...dialog.querySelectorAll('video')];
            compare.forEach(video=>{
                Object.defineProperty(video,'duration',{configurable:true,value:20});
                Object.defineProperty(video,'paused',{configurable:true,get(){return !this.__playing;}});
                video.play=function(){this.__playing=true;this.dispatchEvent(new Event('play'));return Promise.resolve();};
                video.pause=function(){this.__playing=false;this.dispatchEvent(new Event('pause'));};
            });
            dialog.querySelector('[data-depth-compare-play]').click();
            const seek=dialog.querySelector('[data-depth-compare-seek]');
            seek.value='720'; seek.dispatchEvent(new Event('input',{bubbles:true})); seek.dispatchEvent(new Event('change',{bubbles:true}));
            const state={
                nodeSeeks:root.querySelectorAll('[data-depth-video-seek]').length,
                nodeTime:root.querySelector('[data-depth-video-time="output"]').textContent,
                sourceClip:dialog.querySelector('[data-depth-compare-source]').style.clipPath,
                divider:dialog.querySelector('[data-depth-compare-divider]').style.left,
                compareTimes:compare.map(video=>video.currentTime),
                compareTime:dialog.querySelector('[data-depth-compare-time]').textContent,
                depthFilter:getComputedStyle(dialog.querySelector('.depth-video-compare-depth')).filter,
                sourceFilter:getComputedStyle(dialog.querySelector('[data-depth-compare-video="source"]')).filter,
                playing:compare.map(video=>!video.paused)
            };
            return state;
        });
        assert.deepEqual(result,{nodeSeeks:2,nodeTime:'0:05 / 0:20',sourceClip:'inset(0px 50% 0px 0px)',divider:'50%',compareTimes:[14.4,14.4],compareTime:'0:14 / 0:20',depthFilter:'brightness(2.4) contrast(1.4) invert(1) blur(2px)',sourceFilter:'none',playing:[true,true]});
        await page.keyboard.press('Space');
        assert.deepEqual(await page.locator('[data-depth-compare-video]').evaluateAll(videos=>videos.map(video=>video.paused)),[true,true]);
        await page.locator('[data-depth-compare-seek]').focus();
        await page.keyboard.press('Space');
        assert.deepEqual(await page.locator('[data-depth-compare-video]').evaluateAll(videos=>videos.map(video=>video.paused)),[false,false]);
        await page.locator('[data-depth-video-compare-close]').click();
        assert.equal(await page.locator('.depth-video-compare-modal').count(),0);
        assert.deepEqual(errors,[]);
        console.log(JSON.stringify(result));
    } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
