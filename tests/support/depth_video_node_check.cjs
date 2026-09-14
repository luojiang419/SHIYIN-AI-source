const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async()=>{
    const base = process.argv[2] || 'http://127.0.0.1:3012';
    const artifactDir = process.argv[3] || '.codex-artifacts/depth-video-node';
    fs.mkdirSync(artifactDir,{recursive:true});
    const browser = await chromium.launch({headless:true,channel:'chrome'});
    const results = {};
    try {
        for(const mode of ['canvas']){
            const page = await browser.newPage({viewport:{width:1440,height:900}});
            const errors=[];
            page.on('pageerror',error=>errors.push(error.message));
            await page.addInitScript(()=>{
                Object.defineProperty(HTMLMediaElement.prototype,'paused',{configurable:true,get(){return !this.__playing;}});
                HTMLMediaElement.prototype.play=function(){this.__playing=true;this.dispatchEvent(new Event('play'));return Promise.resolve();};
                HTMLMediaElement.prototype.pause=function(){this.__playing=false;this.dispatchEvent(new Event('pause'));};
            });
            await page.goto(`${base}/static/${mode}.html?id=depth-video-${mode}-${Date.now()}`);
            await page.waitForSelector('#world');
            await page.waitForSelector('.image-node,.node',{state:'attached'});
            await page.evaluate(mode=>{
                const media='data:video/mp4;base64,AAAA';
                nodes.push({id:'depth-video-check',type:'depthVideo',x:100,y:100,w:620,h:390,depthVideoStatus:'done',depthVideoManualInput:{url:media,name:'portrait.mp4',kind:'video'},depthVideoInputUrl:media,depthVideoInputName:'portrait.mp4',depthVideoInputSignature:media+'|portrait.mp4|x',depthVideoGeneratedSignature:media+'|portrait.mp4|x',outputUrl:media,outputName:'depth-preview.mp4',outputKind:'video'});
                viewport.x=80;viewport.y=80;viewport.scale=1;render();
            },mode);
            const node=page.locator(mode==='canvas'?'.depthVideo-node[data-id="depth-video-check"]':'.smart-depth-video-node[data-id="depth-video-check"]');
            await node.waitFor({state:'attached'});
            const state=await node.evaluate(el=>({
                cards:[...el.querySelectorAll('.depth-video-preview-card')].map(card=>{const r=card.getBoundingClientRect();return {width:r.width,height:r.height,ratio:r.width/r.height};}),
                objectFits:[...el.querySelectorAll('video')].map(video=>getComputedStyle(video).objectFit),
                playButtons:el.querySelectorAll('[data-depth-video-play]').length,
                overflow:(()=>{const body=el.querySelector('.node-body');return body.scrollWidth<=body.clientWidth+1;})()
            }));
            console.log(mode,JSON.stringify(state));
            assert.equal(state.cards.length,2);
            assert.ok(state.cards.every(card=>Math.abs(card.ratio-16/9)<0.02));
            assert.deepEqual(state.objectFits,['contain','contain']);
            assert.equal(state.playButtons,2);
            assert.equal(state.overflow,true);
            await node.locator('[data-depth-video-play="input"]').click();
            assert.equal(await node.locator('[data-depth-video-play="input"]').getAttribute('title'),'播放输入视频');
            assert.equal(await node.locator('[data-depth-video-play="input"]').evaluate(button=>button.classList.contains('is-playing')),true);
            assert.deepEqual(errors,[]);
            await page.screenshot({path:path.join(artifactDir,`${mode}.png`),fullPage:true});
            results[mode]=state;
            await page.close();
        }
        fs.writeFileSync(path.join(artifactDir,'results.json'),JSON.stringify(results,null,2));
        console.log(JSON.stringify(results));
    } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
