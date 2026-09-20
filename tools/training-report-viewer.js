(() => {
  const box=document.getElementById('lightbox'), body=document.getElementById('lightBody');
  const title=document.getElementById('lightTitle'), native=document.getElementById('native');
  body.innerHTML='<span class="viewer-status" hidden></span>';
  const status=body.querySelector('.viewer-status');
  const fitButton=document.createElement('button');fitButton.textContent='适应窗口';native.after(fitButton);
  const zoomLabel=document.createElement('span');zoomLabel.setAttribute('aria-label','当前缩放比例');fitButton.after(zoomLabel);
  const bottom=document.createElement('div');bottom.className='viewer-bottom';bottom.innerHTML='<button aria-label="上一张图片">← 上一张</button><span class="viewer-count"></span><button aria-label="下一张图片">下一张 →</button><span class="viewer-help">滚轮缩放 · 拖拽平移 · ← → 切图 · 双击重置 · Esc 关闭</span>';box.append(bottom);
  let list=[],index=0,image=null,scale=1,x=0,y=0,request=0,origin=null,drag=null,transition=null;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  function transform(){if(image)image.style.transform=`translate(-50%,-50%) translate(${x}px,${y}px) scale(${scale})`;zoomLabel.textContent=Math.round(scale*100)+'%'}
  function fit(){if(!image)return;scale=Math.min((body.clientWidth-24)/image.naturalWidth,(body.clientHeight-24)/image.naturalHeight,1);x=y=0;transform()}
  function zoom(next,cx=0,cy=0){if(!image)return;next=Math.max(.02,Math.min(8,next));const ratio=next/scale;x=cx-(cx-x)*ratio;y=cy-(cy-y)*ratio;scale=next;transform()}
  async function show(next){
    index=(next+list.length)%list.length;const token=++request,entry=list[index];
    status.hidden=false;status.textContent='正在加载图片…';
    const incoming=new Image();incoming.alt=entry.title;incoming.draggable=false;
    incoming.src=entry.src;
    try{await incoming.decode()}catch{if(token===request){status.textContent='图片加载失败，请切换或重试';}return}
    if(token!==request||box.hidden)return;
    status.hidden=true;transition?.cancel();
    body.querySelectorAll('img').forEach(el=>{if(el!==image)el.remove()});
    const previous=image;image=incoming;image.id='lightImage';if(previous)previous.removeAttribute('id');
    image.style.width=image.naturalWidth+'px';image.style.height=image.naturalHeight+'px';body.append(image);fit();
    title.textContent=entry.title;document.getElementById('download').href=entry.src;
    bottom.querySelector('.viewer-count').textContent=`${index+1} / ${list.length}`;
    // 新图解码完成后覆盖在旧图上淡入，旧图保留到叠化结束，避免切图闪黑。
    if(previous&&!reduced.matches){transition=image.animate([{opacity:0},{opacity:1}],{duration:380,easing:'ease-in-out'});transition.onfinish=()=>previous.remove();}else previous?.remove();
  }
  function open(clicked){
    const panel=clicked.closest('.panel');origin=clicked.closest('button')||clicked;
    const candidates=clicked.closest('#resultCarousel')?[...panel.querySelectorAll('.carousel-slide img')]:[...panel.querySelectorAll('.photo img,.demo-stage img')];
    list=candidates.map(el=>({src:el.closest('[data-src]')?.dataset.src||el.getAttribute('src'),title:el.closest('[data-title]')?.dataset.title||el.alt||'图片'}));
    const selected=candidates.indexOf(clicked);if(selected<0)return;
    box.hidden=false;document.body.style.overflow='hidden';document.getElementById('closeLight').focus();show(selected);
  }
  document.addEventListener('click',e=>{const target=e.target.closest('.photo,.demo-stage img');if(!target||target.closest('#lightbox'))return;const img=target.matches('img')?target:target.querySelector('img');if(!img)return;e.preventDefault();e.stopImmediatePropagation();open(img)},true);
  function close(){++request;transition?.cancel();box.hidden=true;document.body.style.overflow='';body.querySelectorAll('img').forEach(el=>el.remove());image=null;drag=null;body.classList.remove('dragging');origin?.focus()}
  document.getElementById('closeLight').onclick=close;native.onclick=()=>{scale=1;x=y=0;transform()};fitButton.onclick=fit;
  bottom.querySelectorAll('button')[0].onclick=()=>show(index-1);bottom.querySelectorAll('button')[1].onclick=()=>show(index+1);
  body.addEventListener('wheel',e=>{e.preventDefault();const r=body.getBoundingClientRect();zoom(scale*Math.exp(-e.deltaY*(e.deltaMode===1?.04:.0015)),e.clientX-r.left-r.width/2,e.clientY-r.top-r.height/2)},{passive:false});
  body.addEventListener('pointerdown',e=>{if(e.button!==0||!image)return;drag={id:e.pointerId,x:e.clientX,y:e.clientY};body.setPointerCapture(e.pointerId);body.classList.add('dragging');e.preventDefault()});
  body.addEventListener('pointermove',e=>{if(!drag||drag.id!==e.pointerId)return;x+=e.clientX-drag.x;y+=e.clientY-drag.y;drag.x=e.clientX;drag.y=e.clientY;transform()});
  function end(){drag=null;body.classList.remove('dragging')}body.addEventListener('pointerup',end);body.addEventListener('pointercancel',end);body.addEventListener('lostpointercapture',end);body.ondblclick=fit;
  document.addEventListener('keydown',e=>{if(box.hidden)return;if(['Escape','ArrowLeft','ArrowRight','+','=','-','0','Tab'].includes(e.key)){e.preventDefault();e.stopImmediatePropagation();if(e.key==='Escape')close();else if(e.key==='ArrowLeft')show(index-1);else if(e.key==='ArrowRight')show(index+1);else if(e.key==='0')fit();else if(e.key==='Tab'){const controls=[...box.querySelectorAll('button,a[href]')];let n=controls.indexOf(document.activeElement);controls[(n+(e.shiftKey?-1:1)+controls.length)%controls.length].focus()}else zoom(scale*(e.key==='-'?.8:1.25))}},true);
  new ResizeObserver(()=>{if(!box.hidden)fit()}).observe(body);
})();
