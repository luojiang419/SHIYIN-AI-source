const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/canvas.js','utf8');
const start=source.indexOf('async function syncRemoteCanvasNow(){');
const end=source.indexOf('async function checkRemoteCanvasVersion(){',start);

function fixture(){
    let resolveRead, applied=[], reads=0;
    const context=vm.createContext({
        canvas:{id:'a',revision:2},canvasSessionSuspended:false,localCanvasDirty:false,
        saveTimer:null,savingCanvasNow:false,saveCanvasAgain:false,remoteSyncTimer:null,
        localCanvasSaveSequence:10,lastCanvasUpdatedAt:100,
        classicCanvasTextInputActive:()=>false,setTimeout:()=>1,clearTimeout:()=>{},
        setStatus:()=>{},tr:value=>value,console,
        fetch:()=>{reads++;return new Promise(resolve=>{resolveRead=resolve;});},
        applyRemoteCanvasData:remote=>applied.push(remote)
    });
    vm.runInContext(source.slice(start,end),context);
    return {context,applied,reads:()=>reads,
        run:()=>vm.runInContext('syncRemoteCanvasNow()',context),
        respond:(updated_at=110)=>resolveRead({ok:true,json:async()=>({canvas:{id:'a',updated_at,revision:3}})})};
}

(async()=>{
    const clean=fixture(), cleanRun=clean.run();clean.respond();await cleanRun;
    assert.equal(clean.applied.length,1,'没有本地修改时更新远端版本');
    for(const state of ['canvasSessionSuspended','localCanvasDirty','savingCanvasNow','saveCanvasAgain']){
        const f=fixture();f.context[state]=true;await f.run();assert.equal(f.reads(),0,state);
    }
    for(const mutate of [
        c=>{c.localCanvasSaveSequence++;c.localCanvasDirty=false;}, // 保存已完成，不能只检查 dirty。
        c=>{c.canvas={id:'a',revision:4};}, // 同 ID 的会话已被替换。
        c=>{c.canvas={id:'b',revision:1};},
        c=>{c.canvasSessionSuspended=true;},
        c=>{c.classicCanvasTextInputActive=()=>true;},
        c=>{c.lastCanvasUpdatedAt=120;}
    ]){
        const f=fixture(), pending=f.run();mutate(f.context);f.respond();await pending;
        assert.equal(f.applied.length,0,'迟到的同步响应不得覆盖最新编辑状态');
    }
    const equal=fixture(), equalRun=equal.run();equal.respond(100);await equalRun;
    assert.equal(equal.applied.length,0,'相同版本不重绘');
    console.log('canvas session sync: 12 cases passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
