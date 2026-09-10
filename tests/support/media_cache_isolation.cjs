const vm=require('node:vm');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const stores=new Map();
let scope='account-a', mediaRequests=0, authRequests=0, unauthorized=false;
const tasks=[];
const context={URL, Request, Response, Headers, Map, Date, console,
  self:{location:{origin:'http://fixture'},addEventListener(){}},
  caches:{async open(name){
    if(!stores.has(name))stores.set(name,new Map());const store=stores.get(name);
    return {async match(key){return store.get(key.url)?.clone()},async put(key,value){store.set(key.url,value.clone())},
      async keys(){return [...store.keys()].map(url=>new Request(url))},async delete(key){return store.delete(key.url)}};
  }},
  async fetch(request){
    const url=typeof request==='string'?request:request.url;
    await new Promise(resolve=>setTimeout(resolve,3));
    if(url.includes('/api/auth/status')){authRequests++;return new Response('{}',{status:unauthorized?401:200,headers:{'X-Media-Account':scope}})}
    mediaRequests++;
    return new Response(unauthorized?'denied':scope,{status:unauthorized?401:200,headers:{'X-Media-Account':scope,'content-type':'image/png','content-length':'9'}});
  }
};
vm.createContext(context);
vm.runInContext(fs.readFileSync('static/media-cache-sw.js','utf8'),context);
const event={waitUntil(task){tasks.push(task)}};
async function get(){const r=await context.handleImageRequest(new Request('http://fixture/api/media-preview?url=a.png&rev=1'),event);await Promise.all(tasks.splice(0));return r;}
(async()=>{
  let result=await get();assert.equal(await result.text(),'account-a');assert.equal(mediaRequests,1);
  result=await get();assert.equal(await result.text(),'account-a');assert.equal(mediaRequests,1);
  scope='account-b';result=await get();assert.equal(await result.text(),'account-b');assert.equal(mediaRequests,2);
  scope='account-a';result=await get();assert.equal(await result.text(),'account-a');assert.equal(mediaRequests,2);
  unauthorized=true;result=await get();assert.equal(result.status,401);assert.equal(await result.text(),'denied');
  unauthorized=false;scope='account-c';
  const pair=await Promise.all([get(),get()]);
  assert.deepEqual(await Promise.all(pair.map(r=>r.text())),['account-c','account-c']);
  assert.equal(mediaRequests,4); // A + B + denied + one shared C request
  assert.equal(authRequests,6); // every completed wave re-authenticates, concurrent wave shares one
  console.log('media cache: account switch, logout, cache hit and shared response isolation passed');
})().catch(error=>{console.error(error);process.exitCode=1});
