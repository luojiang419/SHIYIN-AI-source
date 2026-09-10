const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const requests=[],applied=[],values=new Map();
const host={addEventListener:()=>{},dispatchEvent:()=>{},StudioTheme:{apply:value=>applied.push(value)}};
host.top=host;
const context=vm.createContext({window:host,location:{host:'fixture',protocol:'http:'},
    localStorage:{getItem:key=>values.get(key),setItem:(key,value)=>values.set(key,value)},
    document:{querySelectorAll:()=>[]},crypto:{randomUUID:()=> 'fixture'},
    CustomEvent:class{},WebSocket:class{},setTimeout,clearTimeout,console,
    fetch:(url,options={})=>new Promise(resolve=>requests.push({url,options,respond(data,status=200){resolve({ok:status<400,status,json:async()=>data});}}))});
vm.runInContext(fs.readFileSync('static/js/runtime-sync.js','utf8'),context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
    const runtime=host.RuntimeSync;
    const first=runtime.setPreference('theme','dark');
    requests[0].respond({revision:1,allowed_keys:['theme'],values:{theme:'light'}});
    await tick();
    assert.deepEqual(applied,[],'启动 GET 不得覆盖已经发起的本地编辑');
    assert.equal(requests[1].options.method,'PUT');
    const second=runtime.setPreference('theme','pure-white');
    const reconnect=runtime.readPreferences();
    requests[2].respond({revision:1,allowed_keys:['theme'],values:{theme:'light'}});
    await reconnect;
    assert.deepEqual(applied,[],'写入期间的重连读取不能覆盖本地值');
    requests[1].respond({revision:2,values:{theme:'dark'}});
    await first;await tick();
    assert.deepEqual(applied,[],'先前 PUT 的迟到响应不应用到界面');
    assert.equal(JSON.parse(requests[3].options.body).values.theme,'pure-white');
    assert.equal(JSON.parse(requests[3].options.body).base_revision,2);
    requests[3].respond({revision:3,values:{theme:'pure-white'}});
    await second;
    assert.deepEqual(applied,['pure-white']);
    assert.equal(values.get('studio_theme'),'pure-white');
    console.log('runtime preference ordering and stale response guards passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
