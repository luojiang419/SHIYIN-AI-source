const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const sandbox={window:{}};
vm.runInNewContext(fs.readFileSync('static/js/canvas-linkfox-video.js','utf8'),sandbox);
const api=sandbox.window.CanvasLinkfoxVideo;
const plain=value=>JSON.parse(JSON.stringify(value));

test('upstream three images are collected in order; own output and unrelated nodes excluded',()=>{
    const node=api.createNode({}, {id:'video',generatedOutputs:[{url:'/old.mp4',kind:'video'}]});
    const nodes=[node,...['a','b','c','unrelated'].map(id=>({id,url:`/${id}.png`,kind:'image'})),{id:'movie',url:'/v.mp4',kind:'video'}];
    const links=['a','b','c','movie'].map(from=>({from,to:node.id}));
    const collect=()=>api.inputRefs(node,nodes,links,n=>[n]);
    assert.deepEqual(plain(api.buildRequest(node,collect()).imageList),['/a.png','/b.png','/c.png']);
    links.splice(1,1);
    assert.deepEqual(plain(api.buildRequest(node,collect()).imageList),['/a.png','/c.png']);
    links.length=0;
    assert.throws(()=>api.buildRequest(node,collect()),/连接/);
});

test('tail connected before head still maps by port; legacy links retain order',()=>{
    const node=api.createNode({}, {mode:'first_last_frame'});
    const result=api.buildRequest(node,[{url:'/last.png',inputRole:'last-frame'},{url:'/first.png',inputRole:'reference-image'}]);
    assert.equal(result.imageUrl,'/first.png');
    assert.equal(result.lastFrameImageUrl,'/last.png');
    assert.equal(api.buildRequest(node,['/first.png','/last.png']).lastFrameImageUrl,'/last.png');
    assert.throws(()=>api.buildRequest(node,[{url:'/last.png',inputRole:'last-frame'}]),/首帧/);
    assert.throws(()=>api.buildRequest(node,['a','b','c']),/2 张/);
});

test('changing model normalizes actual request values and enforces image limit',()=>{
    const node=api.createNode({}, {model:'海螺2.3',duration:5,resolution:'720p',voice:true});
    const result=api.buildRequest(node,['/a.png']);
    assert.equal(result.videoTime,6);
    assert.equal(result.resolution,'768p');
    assert.equal(result.voice,false);
    assert.equal(result.aspectRatio,'');
    assert.throws(()=>api.buildRequest(node,['a','b']),/1 张/);
});
