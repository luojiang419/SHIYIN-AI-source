(() => {
  const root=document.documentElement;
  const toggle=document.getElementById('tutorialSidebarToggle');
  const scrim=document.getElementById('tutorialSidebarScrim');
  if(!toggle)return;
  let saved;
  try{saved=localStorage.getItem('shiyin-tutorial-sidebar')}catch{}
  const narrow=()=>matchMedia('(max-width:800px)').matches;
  function apply(state,persist=true){
    root.dataset.tutorialSidebar=state;
    const expanded=state==='expanded';
    toggle.setAttribute('aria-expanded',String(expanded));
    toggle.title=expanded?'折叠教程导航':'展开教程导航';
    const label=toggle.querySelector('.sr-only');if(label)label.textContent=toggle.title;
    if(persist){try{localStorage.setItem('shiyin-tutorial-sidebar',state)}catch{}}
  }
  apply(saved|| (narrow()?'collapsed':'expanded'),false);
  toggle.onclick=()=>apply(root.dataset.tutorialSidebar==='expanded'?'collapsed':'expanded');
  scrim.onclick=()=>apply('collapsed');
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&narrow())apply('collapsed')});
})();
