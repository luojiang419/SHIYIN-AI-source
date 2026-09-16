// 真实 Service Worker 中注入磁盘缓存永久挂起；不访问正式用户数据。
const {chromium} = require('playwright');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const worker = fs.readFileSync(process.argv[2] || path.join(__dirname, '../../static/media-cache-sw.js'), 'utf8');
const inject = `
let fault='';
const realOpen=caches.open.bind(caches);
caches.open=async function(name){
  if(fault==='open')return new Promise(()=>{});
  if(fault==='unavailable')throw Error('storage unavailable');
  const cache=await realOpen(name);
  if(fault==='match')cache.match=()=>new Promise(()=>{});
  if(fault==='put')cache.put=()=>new Promise(()=>{});
  if(fault==='quota')cache.put=async()=>{throw Error('quota')};
  return cache;
};
self.addEventListener('message', e=>{if(e.data.fault){fault=e.data.fault;e.ports[0].postMessage('ready')}});
`;
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64');
const server = http.createServer((req,res) => {
    if(req.url.startsWith('/media-cache-sw.js')) {
        res.writeHead(200, {'Content-Type':'application/javascript','Service-Worker-Allowed':'/'});
        return res.end(inject + worker);
    }
    if(req.url.startsWith('/api/auth/status')) {
        res.writeHead(200, {'X-Media-Account':'fixture'});return res.end('{}');
    }
    if(req.url.startsWith('/api/media-preview')) {
        res.writeHead(200, {'Content-Type':'image/png','Content-Length':png.length,'X-Media-Account':'fixture'});return res.end(png);
    }
    if(req.url.startsWith('/static/probe.js')) {
        res.writeHead(200, {'Content-Type':'application/javascript'});return res.end('window.probeLoaded=true;');
    }
    res.writeHead(200, {'Content-Type':'text/html'});res.end('<!doctype html><body>cache startup fixture</body>');
});
(async()=>{
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    const base=`http://127.0.0.1:${server.address().port}`;
    const browser=await chromium.launch({channel:'msedge',headless:true});
    try {
        for(const fault of ['open','match','put','quota','unavailable']) {
            const context=await browser.newContext();
            try {
                const page=await context.newPage();
                await page.goto(base);
                await page.evaluate(async()=>{await navigator.serviceWorker.register('/media-cache-sw.js');await navigator.serviceWorker.ready;});
                await page.reload();
                await page.evaluate(fault=>new Promise(resolve=>{const channel=new MessageChannel();channel.port1.onmessage=resolve;navigator.serviceWorker.controller.postMessage({fault},[channel.port2]);}),fault);
                const started=Date.now();
                await page.evaluate(()=>{const script=document.createElement('script');script.src='/static/probe.js?v=1';document.body.append(script);const img=new Image();img.id='preview';img.src='/api/media-preview?rev=1';document.body.append(img);});
                await page.waitForFunction(()=>window.probeLoaded && document.getElementById('preview').naturalWidth>0, null, {timeout:2500});
                const elapsed=Date.now()-started;
                assert.ok(elapsed<2000);
                console.log(JSON.stringify({fault,scriptAndImageReadyMs:elapsed}));
            } finally {await context.close();}
        }
    } finally {await browser.close();server.close();}
})().catch(error=>{console.error(error);server.close();process.exitCode=1;});
