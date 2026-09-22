const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('static/js/personal-preferences.js','utf8');
function load(account,stored,server){
 const requests=[];
 const context={window:{StudioPageState:{accountId:account,ready:async()=>{}},dispatchEvent(){}},localStorage:{getItem:key=>stored[key]||null,setItem:(key,value)=>stored[key]=value},CustomEvent:class{},AbortSignal,structuredClone,console:{warn(){}},fetch:async(url,options={})=>{
  requests.push({url,...options});
  if(options.method==='PUT'){server.value={...server.value,...JSON.parse(options.body)};return {ok:true,json:async()=>server.value};}
  return {ok:server.status===200,status:server.status,json:async()=>server.value};
 }};
 vm.runInNewContext(source,context);
 return {api:context.window.PersonalPreferences,requests};
}
test('仅迁移当前账号生成偏好，不迁移旧机器目录',async()=>{
 const stored={'studio_personal_preferences_v1:account:alice':JSON.stringify({video:{h3:{duration:9}},quickSave:{mode:'silent',directory:'Z:/missing'}}),'studio_personal_preferences_v1:account:bob':JSON.stringify({video:{h3:{duration:15}}})};
 const {api,requests}=load('alice',stored,{status:200,value:{}});await api.ready;
 assert.equal(api.values.video.h3.duration,9);assert.equal(api.values.quickSave,undefined);
 assert.equal(requests.filter(r=>r.method==='PUT').length,1);
 assert(stored['studio_personal_preferences_v1:account:alice']);
});
test('服务端已有偏好时不被旧本机值覆盖',async()=>{
 const {api,requests}=load('alice',{'studio_personal_preferences_v1:account:alice':'{"video":{"h3":{"duration":9}}}'},{status:200,value:{video:{h3:{duration:12}}}});await api.ready;
 assert.equal(api.values.video.h3.duration,12);assert.equal(requests.length,1);
});
test('旧后端 404 按账号本机恢复；403 不降级',async()=>{
 const stored={'studio_personal_preferences_v1:account:alice':'{"video":{"h3":{"duration":9}}}'};
 const old=load('alice',stored,{status:404});await old.api.ready;assert.equal(old.api.values.video.h3.duration,9);
 const denied=load('alice',stored,{status:403});await denied.api.ready;assert.equal(denied.api.legacyBackend,false);assert.equal(denied.api.values.video,undefined);
});
