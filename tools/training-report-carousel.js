(() => {
  const root=document.documentElement, theme=document.getElementById('themeToggle');
  let saved;try{saved=localStorage.getItem('shiyin-training-theme')}catch{}
  function setTheme(value){root.dataset.theme=value;theme.textContent=value==='dark'?'浅色模式':'暗色模式';theme.setAttribute('aria-label',value==='dark'?'切换为浅色模式':'切换为暗色模式')}
  setTheme(saved|| (matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'));
  theme.onclick=()=>{const next=root.dataset.theme==='dark'?'light':'dark';setTheme(next);try{localStorage.setItem('shiyin-training-theme',next)}catch{}};
  const items=[
    ['denim-software-node-3.jpg','牛仔上衣 · 已选候选 1','一键复刻 · 现阶段效果演示，材质仍有差异'],
    ['a-product-result.jpg','黑白豹纹上衣','批量换款 · A1'],
    ['a-style-b-result.jpg','棕色豹纹上衣','批量换款 · A2'],
    ['b-product-fixed.png','棕色宽腿裤','批量换款 · B1 · 颜色与质感未通过'],
    ['b-node-fixed.png','棕色宽腿裤','一键复刻 · 边界修复，材质仍需复核']
  ];
  const el=document.getElementById('resultCarousel');
  el.innerHTML='<div class="carousel-top"><span class="carousel-live">实际生成作品</span><span id="carouselCount"></span></div><div class="carousel-stage">'+items.map(([src,title],i)=>`<figure class="carousel-slide ${i===0?'active':''}" aria-hidden="${i!==0}"><button class="photo" tabindex="${i===0?0:-1}" aria-label="查看原图：${title}"><img src="assets/${src}" alt="${title}" decoding="async"></button></figure>`).join('')+'</div><div class="carousel-meta"><div><strong id="carouselTitle"></strong><p id="carouselCaption"></p></div><div class="carousel-controls"><button id="carouselPrev" aria-label="上一张作品">←</button><button id="carouselPause">暂停</button><button id="carouselNext" aria-label="下一张作品">→</button></div></div><div class="carousel-thumbs">'+items.map(([src,title],i)=>`<button aria-label="切换到第 ${i+1} 张：${title}" aria-current="${i===0}"><img src="assets/${src}" alt=""></button>`).join('')+'</div><div class="carousel-track"><span></span></div>';
  let current=0,elapsed=0,last=performance.now(),playing=!matchMedia('(prefers-reduced-motion: reduce)').matches;
  const slides=[...el.querySelectorAll('.carousel-slide')], thumbs=[...el.querySelectorAll('.carousel-thumbs button')], pauseButton=document.getElementById('carouselPause');
  function show(index){current=(index+items.length)%items.length;elapsed=0;slides.forEach((s,i)=>{s.classList.toggle('active',i===current);s.setAttribute('aria-hidden',String(i!==current));s.querySelector('button').tabIndex=i===current?0:-1;thumbs[i].setAttribute('aria-current',String(i===current))});document.getElementById('carouselCount').textContent=`0${current+1} / 0${items.length}`;document.getElementById('carouselTitle').textContent=items[current][1];document.getElementById('carouselCaption').textContent=items[current][2]}
  function label(){pauseButton.textContent=playing?'暂停':'播放';pauseButton.setAttribute('aria-label',playing?'暂停作品轮播':'播放作品轮播')}
  thumbs.forEach((b,i)=>b.onclick=()=>show(i));document.getElementById('carouselPrev').onclick=()=>show(current-1);document.getElementById('carouselNext').onclick=()=>show(current+1);pauseButton.onclick=()=>{playing=!playing;label()};
  slides.forEach((slide,i)=>slide.querySelector('button').onclick=()=>{returnFocus=slide.querySelector('button');document.getElementById('lightbox').hidden=false;document.getElementById('lightImage').src='assets/'+items[i][0];document.getElementById('lightTitle').textContent=items[i][1];document.getElementById('download').href='assets/'+items[i][0];document.getElementById('lightBody').classList.remove('native');document.getElementById('native').textContent='原图大小';document.getElementById('closeLight').focus();document.body.style.overflow='hidden'});
  // 离开总览、后台标签页或查看大图时停止计时，避免回到页面后突然跳图。
  setInterval(()=>{const now=performance.now(),delta=Math.min(now-last,200);last=now;if(playing&&!document.hidden&&!document.getElementById('overview').hidden&&document.getElementById('lightbox').hidden){elapsed+=delta;if(elapsed>=5000)show(current+1)}el.querySelector('.carousel-track span').style.width=(elapsed/5000*100)+'%'},100);
  show(0);label();
})();
