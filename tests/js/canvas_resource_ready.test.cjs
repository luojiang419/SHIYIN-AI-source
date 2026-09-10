const assert=require('node:assert/strict');
const ready=require('../../static/js/canvas-resource-ready.js')({setTimeout});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function img(src){return {tagName:'IMG',dataset:{},complete:false,naturalWidth:0,getAttribute:()=>src,decode:async()=>{}};}
function root(items){return {items,querySelectorAll(selector){return selector==='.missing-asset'?[]:this.items;}};}
(async()=>{
 const old=img('/old'),next=img('/new');const r=root([old]);let done=false;
 const wait=ready.wait({root:r,isCurrent:()=>true,drain:()=>{},progress:()=>{}}).then(x=>{done=true;return x;});
 await sleep(100);r.items=[next];await sleep(400);assert(!done,'移除旧 DOM 不代表新资源已就绪');
 let decode;next.decode=()=>new Promise(resolve=>decode=resolve);next.complete=true;next.naturalWidth=100;
 await sleep(150);assert(!done,'load 后必须等待解码');decode();await wait;
 const video={tagName:'VIDEO',dataset:{},readyState:1,getAttribute:()=>'/video',load(){}};
 const v=root([video]);done=false;
 const playback=ready.wait({root:v,isCurrent:()=>true,drain:()=>{},progress:()=>{}}).then(()=>done=true);
 await sleep(400);assert(!done,'仅元数据不能当作可播放');video.readyState=3;await playback;
 const broken=img('/broken');broken.complete=true;
 const failed=await ready.wait({root:root([broken]),isCurrent:()=>true,drain:()=>{},progress:()=>{}});
 assert.equal(failed.failed[0],broken);
 const cancelled=await ready.wait({root:r,isCurrent:()=>false,drain:()=>{},progress:()=>{}});assert(cancelled.cancelled);
 console.log('resource readiness: DOM replacement, decode, video canplay, failures, cancellation passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
