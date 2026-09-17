(() => {
  const $ = (id) => document.getElementById(id);
  const state = {sessionId:null,width:0,height:0,image:null,mask:null,points:[],view:'cutout',busy:false,request:0};
  const imageCanvas=$('imageCanvas'), maskCanvas=$('maskCanvas'), imageCtx=imageCanvas.getContext('2d'), maskCtx=maskCanvas.getContext('2d');
  const controls=['exportButton','undoButton','clearButton','maskExportButton','cutoutExportButton'];
  function toast(message){const node=$('toast');node.textContent=message;node.hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>node.hidden=true,3200)}
  function setBusy(value){state.busy=value;$('busy').hidden=!value;$('modelStatus').textContent=value?'模型运行中':'模型就绪';$('liveStatus').classList.toggle('working',value)}
  function updateControls(){const ready=!!state.sessionId, selected=state.points.length>0;$('undoButton').disabled=!selected;$('clearButton').disabled=!selected;['exportButton','maskExportButton','cutoutExportButton'].forEach(id=>$(id).disabled=!selected||state.busy)}
  const viewport={zoom:1,x:0,y:0,space:false,drag:null};
  function positionCanvas(){
    const r=$('canvasWrap').getBoundingClientRect();
    for(const c of [imageCanvas,maskCanvas]){
      c.style.left=((r.width-c.width*viewport.zoom)/2+viewport.x)+'px';
      c.style.top=((r.height-c.height*viewport.zoom)/2+viewport.y)+'px';
      c.style.transformOrigin='0 0';c.style.transform='scale('+viewport.zoom+')';
    }
    $('zoomValue').textContent=Math.round(viewport.zoom*100)+'%';
  }
  function resetView(){viewport.zoom=1;viewport.x=viewport.y=0;positionCanvas()}
  function fit(){
    if(!state.image)return;
    const r=$('canvasWrap').getBoundingClientRect(),scale=Math.min(r.width/state.width,r.height/state.height);
    for(const c of [imageCanvas,maskCanvas]){
      c.width=Math.max(1,Math.round(state.width*scale));c.height=Math.max(1,Math.round(state.height*scale));
      c.style.width=c.width+'px';c.style.height=c.height+'px';
    }
    positionCanvas();draw();
  }
  const stage=$('stage');
  stage.addEventListener('wheel',e=>{
    if(!state.image)return;e.preventDefault();
    const rect=maskCanvas.getBoundingClientRect(),wrap=$('canvasWrap').getBoundingClientRect();
    const unit=e.deltaMode===1?16:e.deltaMode===2?wrap.height:1;
    const next=Math.max(.1,Math.min(12,viewport.zoom*Math.exp(-e.deltaY*unit*.0015)));
    const u=(e.clientX-rect.left)/rect.width,v=(e.clientY-rect.top)/rect.height;
    viewport.x=e.clientX-wrap.left-u*maskCanvas.width*next-(wrap.width-maskCanvas.width*next)/2;
    viewport.y=e.clientY-wrap.top-v*maskCanvas.height*next-(wrap.height-maskCanvas.height*next)/2;
    viewport.zoom=next;positionCanvas();
  },{passive:false});
  function cursor(){maskCanvas.style.cursor=viewport.drag?'grabbing':viewport.space?'grab':'crosshair'}
  stage.addEventListener('pointerdown',e=>{
    if(!state.image||!(e.button===1||(e.button===0&&viewport.space)))return;
    e.preventDefault();viewport.drag={id:e.pointerId,x:e.clientX,y:e.clientY};
    stage.setPointerCapture(e.pointerId);cursor();
  });
  stage.addEventListener('pointermove',e=>{
    const d=viewport.drag;if(!d||d.id!==e.pointerId)return;
    viewport.x+=e.clientX-d.x;viewport.y+=e.clientY-d.y;d.x=e.clientX;d.y=e.clientY;positionCanvas();
  });
  function stopPan(){viewport.drag=null;cursor()}
  stage.addEventListener('pointerup',e=>{if(viewport.drag){if(stage.hasPointerCapture(e.pointerId))stage.releasePointerCapture(e.pointerId);stopPan()}});
  stage.addEventListener('pointercancel',stopPan);
  stage.addEventListener('lostpointercapture',stopPan);
  window.addEventListener('keydown',e=>{
    if(e.code==='Space'&&!e.target.closest('input,textarea,select,button,[contenteditable]')){
      e.preventDefault();viewport.space=true;cursor();
    }
  });
  window.addEventListener('keyup',e=>{if(e.code==='Space'){viewport.space=false;cursor()}});
  window.addEventListener('blur',()=>{viewport.space=false;stopPan()});
  $('fitButton').onclick=resetView;
  function draw(){if(!state.image)return;const w=imageCanvas.width,h=imageCanvas.height;imageCtx.clearRect(0,0,w,h);imageCtx.globalAlpha=1;imageCtx.drawImage(state.image,0,0,w,h);
if(state.view==='cutout'&&state.mask){imageCtx.fillStyle='rgba(0,0,0,0.65)';imageCtx.fillRect(0,0,w,h);}maskCtx.clearRect(0,0,w,h);if(state.mask&&state.view!=='original'){const temp=document.createElement('canvas');temp.width=w;temp.height=h;const ctx=temp.getContext('2d');ctx.drawImage(state.mask,0,0,w,h);
const pixels=ctx.getImageData(0,0,w,h);
for(let i=0;i<pixels.data.length;i+=4){
  pixels.data[i+3]=pixels.data[i];
  pixels.data[i]=255;pixels.data[i+1]=255;pixels.data[i+2]=255;
}
ctx.putImageData(pixels,0,0);
if(state.view==='overlay'){ctx.globalCompositeOperation='source-in';ctx.fillStyle='rgba(66,215,223,.62)';ctx.fillRect(0,0,w,h)}else{ctx.globalCompositeOperation='source-in';ctx.drawImage(state.image,0,0,w,h)}maskCtx.drawImage(temp,0,0)}state.points.forEach(p=>{const x=p.x/state.width*w,y=p.y/state.height*h;maskCtx.beginPath();maskCtx.arc(x,y,6,0,Math.PI*2);maskCtx.fillStyle=p.label?'#42d7df':'#ff5d68';maskCtx.fill();maskCtx.lineWidth=2;maskCtx.strokeStyle='#fff';maskCtx.stroke();maskCtx.beginPath();maskCtx.moveTo(x-3,y);maskCtx.lineTo(x+3,y);if(!p.label){maskCtx.moveTo(x,y-3);maskCtx.lineTo(x,y+3)}maskCtx.strokeStyle='#102023';maskCtx.lineWidth=1.5;maskCtx.stroke()})}
  async function upload(file){if(!file)return;setBusy(true);try{const body=new FormData();body.append('image',file);const response=await fetch('/api/images',{method:'POST',body});const data=await response.json();if(!response.ok)throw new Error(data.detail||'导入失败');state.sessionId=data.session_id;state.width=data.width;state.height=data.height;state.points=[];state.mask=null;const img=new Image();img.onload=()=>{state.image=img;viewport.zoom=1;viewport.x=viewport.y=0;$('stage').classList.remove('empty');$('emptyState').hidden=true;$('canvasWrap').hidden=false;$('imageMeta').textContent=`${data.width} × ${data.height}`;$('outputSize').textContent=`${data.width} × ${data.height} px`;fit()};img.src=data.preview}catch(error){toast(error.message)}finally{setBusy(false);updateControls()}}
  function requestBody(){return {session_id:state.sessionId,points:state.points,threshold:Number($('threshold').value)/100,feather:Number($('feather').value),edge_shift:Number($('edgeShift').value)}}
  async function segment(){if(!state.points.length){state.mask=null;draw();updateControls();return}const token=++state.request;setBusy(true);updateControls();try{const response=await fetch('/api/segment',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(requestBody())});const data=await response.json();if(!response.ok)throw new Error(data.detail||'分割失败');if(token!==state.request)return;const mask=new Image();mask.src=data.mask;await mask.decode();if(token!==state.request)return;state.mask=mask;state.view='cutout';document.querySelectorAll('.view-tab').forEach(tab=>tab.classList.toggle('active',tab.dataset.view==='cutout'));draw()}catch(error){toast(error.message)}finally{if(token===state.request){setBusy(false);updateControls()}}}
  function addPoint(event){if(!state.sessionId||state.busy||viewport.space||viewport.drag||event.button!==0)return;const rect=maskCanvas.getBoundingClientRect();const x=(event.clientX-rect.left)/rect.width*state.width,y=(event.clientY-rect.top)/rect.height*state.height;if(!event.ctrlKey&&!event.altKey)state.points=[];state.points.push({x:Math.round(x),y:Math.round(y),label:event.altKey?0:1});draw();segment()}
  async function exportImage(kind){if(!state.points.length)return;setBusy(true);updateControls();try{const response=await fetch('/api/export/'+kind,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(requestBody())});if(!response.ok){const data=await response.json();throw new Error(data.detail||'导出失败')}const blob=await response.blob(),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=kind==='cutout'?'shiyin-cutout.png':'shiyin-mask.png';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(error){toast(error.message)}finally{setBusy(false);updateControls()}}
  $('openButton').onclick=$('emptyOpenButton').onclick=()=>$('fileInput').click();$('fileInput').onchange=e=>upload(e.target.files[0]);maskCanvas.addEventListener('click',addPoint);$('undoButton').onclick=()=>{state.points.pop();segment()};$('clearButton').onclick=()=>{state.points=[];state.mask=null;state.request++;draw();setBusy(false);updateControls()};$('exportButton').onclick=$('cutoutExportButton').onclick=()=>exportImage('cutout');$('maskExportButton').onclick=()=>exportImage('mask');
  document.querySelectorAll('.view-tab').forEach(button=>button.onclick=()=>{document.querySelector('.view-tab.active').classList.remove('active');button.classList.add('active');state.view=button.dataset.view;draw()});
  $('threshold').oninput=()=>{$('thresholdValue').textContent=$('threshold').value+'%';clearTimeout(segment.timer);segment.timer=setTimeout(segment,180)};$('feather').oninput=()=>{$('featherValue').textContent=Number($('feather').value).toFixed(1)+' px';clearTimeout(segment.timer);segment.timer=setTimeout(segment,180)};
  $('edgeShift').oninput=()=>{$('edgeShiftValue').textContent=Number($('edgeShift').value)+' px';clearTimeout(segment.timer);segment.timer=setTimeout(segment,120)};
  window.addEventListener('resize',fit);window.addEventListener('keydown',e=>{if(e.ctrlKey&&e.key.toLowerCase()==='z'&&state.points.length){e.preventDefault();state.points.pop();segment()}});document.addEventListener('dragover',e=>e.preventDefault());document.addEventListener('drop',e=>{e.preventDefault();upload(e.dataTransfer.files[0])});updateControls();
})();
