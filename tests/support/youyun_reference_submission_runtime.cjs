const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const classic=fs.readFileSync('static/js/canvas.js','utf8'),smart=fs.readFileSync('static/js/smart-canvas.js','utf8');
function fn(source,name){let start=source.indexOf('function '+name+'(');assert(start>=0);if(source.slice(start-6,start)==='async ')start-=6;return source.slice(start,source.indexOf('\n}',start)+2);}
const context=vm.createContext({window:{},console,Number,Boolean,JSON});
vm.runInContext(fs.readFileSync('static/js/canvas-film-nodes.js','utf8'),context);
vm.runInContext(`
const settings={};
${smart.match(/const SMART_REFERENCE_IMAGE_MAX = [^;]+;/)[0]}
const node={id:'video-test',type:'film-video',apiProvider:'youyun-h3',model:'MiniMax-H3',prompt:'参考图1、视频1和音频1',multimodal:true,muteAudio:true,watermark:true};
const make=(kind,n)=>Array.from({length:n},(_,i)=>({url:'/assets/input/'+kind+i+({image:'.png',video:'.mp4',audio:'.mp3'})[kind],kind,name:kind+i,asset_uris:{'youyun-h3':'asset://wrong-platform'}}));
const inputImages=make('image',6),inputVideos=make('video',3),inputAudios=make('audio',3);
const assets=[...inputImages.map(ref=>({role:'storyboard',ref})),...inputVideos.map(ref=>({role:'reference-video',ref})),...inputAudios.map(ref=>({role:'reference-audio',ref}))];
const built=window.CanvasFilmNodes.buildPrompt(node,assets);
const refs=inputImages,videoRefs=inputVideos,audioRefs=inputAudios,prompt=node.prompt,isH3=true,isKling=false,canvas={id:'canvas-test'},providerId='youyun-h3',steps=12;
const resolveVideoProviderId=id=>id;
${fn(classic,'isYouyunH3VideoNode')}
const mediaKindForItem=ref=>ref.kind;
${['imageRefsOnly','looksLikeImageMediaUrl','videoRefsOnly','audioRefsOnly'].map(n=>fn(smart,n)).join('\n')}
`,context);
const pos=classic.indexOf('        const requestPayload = {',classic.indexOf('async function runVideoNode('));const end=classic.indexOf('\n        };',pos)+11;
vm.runInContext(classic.slice(pos,end)+';globalThis.classicPayload=requestPayload;',context);
const fp=classic.indexOf('            const payload={prompt:built.prompt,provider_id:providerId',classic.indexOf('async function runFilmNode('));const fe=classic.indexOf('\n',fp);
vm.runInContext(classic.slice(fp,fe)+';globalThis.filmPayload=payload;',context);
assert.equal(context.classicPayload.videos.length,3);assert.equal(context.classicPayload.audios.length,3);
assert.equal(context.filmPayload.videos.length,3);assert.equal(context.filmPayload.audios.length,3);
vm.runInContext(`
${['imageRefsOnly','looksLikeImageMediaUrl','videoRefsOnly','audioRefsOnly','isYouyunH3SmartSettings','isMiniMaxH3SmartSettings'].map(n=>fn(smart,n)).join('\n')}
const isKlingSmartSettings=()=>false,applyUploadedUrlsToSmartRefs=refs=>refs.map(ref=>({...ref,url:'https://expired.example/'+ref.kind}));
const loadSmartYouyunH3Status=async()=>{},smartYouyunH3State={generationEnabled:true};
const manualSmartVideoLink=()=>null,videoProviderPlatform=()=> 'youyun-h3';
const resultMediaUrls=result=>result.videos,tr=value=>value;
let transientSmartCloudLinks=[];
globalThis.captured=[];
const fetch=async(url,options)=>{captured.push(JSON.parse(options.body));return {ok:true,json:async()=>({videos:['/assets/output/mock.mp4']})};};
${fn(smart,'runApiVideoGeneration')}
globalThis.run=async()=>{
 const runSettings={videoProvider:'youyun-h3',videoModel:'MiniMax-H3',videoMultimodal:true,videoTrustedAsset:true,videoTrustedSource:'library'};
 await runApiVideoGeneration(node.prompt,[...inputImages,...inputVideos,...inputAudios],runSettings);
 await runApiVideoGeneration(built.prompt,built.refs,runSettings,node);
 // 超限素材应保留到后端校验，不能静默丢弃。
 await runApiVideoGeneration(node.prompt,[...inputImages,...make('video',4),...make('audio',4)],runSettings);
 globalThis.filmOverflow=window.CanvasFilmNodes.buildPrompt(node,make('image',10).map(ref=>({role:'storyboard',ref}))).refs.length;
};
`,context);
(async()=>{
 await context.run();
 for(const payload of context.captured.slice(0,2)){
  assert.equal(payload.images.length,6);assert.equal(payload.videos.length,3);assert.equal(payload.audios.length,3);
  assert.equal(payload.trusted_asset,false);
  assert(payload.audios.every(url=>url.startsWith('/assets/input/audio')));
  assert(payload.images.every(ref=>ref.url.startsWith('/assets/input/image')));
 }
 assert.equal(context.captured[2].videos.length,4);assert.equal(context.captured[2].audios.length,4);assert.equal(context.filmOverflow,10);
 console.log(JSON.stringify({classic:context.classicPayload,film:context.filmPayload,smart:context.captured[0],smartFilm:context.captured[1]}));
})().catch(error=>{console.error(error);process.exitCode=1;});
