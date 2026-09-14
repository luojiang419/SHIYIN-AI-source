'use strict';
const $ = s => document.querySelector(s);
let token = location.hash.slice(1) || sessionStorage.getItem('distribution-token') || '';
if(token){sessionStorage.setItem('distribution-token', token); history.replaceState(null,'',location.pathname);}
let state, busy = false;
const systemTheme = matchMedia('(prefers-color-scheme: dark)');
function applyTheme(theme='system') {
  document.documentElement.dataset.theme = theme==='system' ? (systemTheme.matches?'dark':'light') : theme;
}
systemTheme.addEventListener('change',()=>applyTheme(state?.settings?.theme));
applyTheme();
function message(text, error=false){$('#notice').textContent=text;$('#notice').classList.toggle('error',error);}
async function api(path, body){
  const response=await fetch('/api/'+path,{method:body===undefined?'GET':'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await response.json(); if(!response.ok)throw new Error(data.error || '请求失败'); return data;
}
const names={hot:'应用热更新',full:'全量安装包','person-depth':'人物深度组件','video-depth':'深度视频模型'};
const states={published:'已发布',paused:'已暂停',archived:'历史版本'};
function element(tag,text,className){const el=document.createElement(tag);el.textContent=text;if(className)el.className=className;return el;}
function releaseRow(item,actions){
  const row=element('div','','row'),copy=element('div','','copy');copy.append(element('strong',names[item.kind]+' · '+item.version),element('small',new Date(item.created*1000).toLocaleString()));row.append(copy,element('span',states[item.state],'badge'));
  if(actions){const button=element('button',item.state==='published'?'暂停发布':'发布此版本');button.onclick=()=>act('release',{id:item.id,state:item.state==='published'?'paused':'published'});row.append(button);}return row;
}
function render(data){
  state=data;$('#running').textContent=data.running?'服务运行中':'服务已停止';$('#address').textContent=data.url;$('#toggle').textContent=data.running?'停止服务':'启动服务';
  applyTheme(data.settings.theme || 'system');
  $('#online').textContent=data.clients.filter(c=>Date.now()/1000-c.seen<300).length;$('#published').textContent=data.releases.filter(r=>r.state==='published').length;$('#uptime').textContent=Math.floor(data.uptime/60)+' 分钟';
  $('#summary').replaceChildren(...data.releases.filter(r=>r.state==='published').map(r=>releaseRow(r,false)));if(!$('#summary').children.length)$('#summary').textContent='尚未发布资源，请先导入热更新或模型。';
  $('#releaseList').replaceChildren(...data.releases.map(r=>releaseRow(r,true)));
  $('#clientList').replaceChildren(...data.clients.map(c=>{const row=element('article');row.append(element('strong',c.ip),element('p','版本：'+(c.version||'未报告')),element('small','最近连接：'+new Date(c.seen*1000).toLocaleString()));return row;}));
  $('#logList').replaceChildren(...data.logs.map(l=>{const row=element('div','','log');row.append(element('time',new Date(l.created*1000).toLocaleTimeString()),element('span',l.message));return row;}));
  $('#dataRoot').textContent=data.data;$('#publicKey').textContent=data.public_key;
  if(!$('#settings').contains(document.activeElement)){
    $('#ip').value=data.settings.address;$('#port').value=data.settings.port;$('#autostart').checked=data.settings.auto_start;
    $('#theme').value=data.settings.theme || 'system';$('#closeToTray').checked=data.settings.background_on_close!==false;
    $('#launchAtLogin').checked=!!data.settings.launch_at_login;$('#startHidden').checked=data.settings.start_hidden!==false;
    $('#startHidden').disabled=!$('#launchAtLogin').checked;
  }
  if(data.job.running)message(data.job.message);else if(data.job.error)message(data.job.error,true);
}
async function refresh(){try{render(await api('status'));if(!state.job.running&&!state.job.error)message('已连接本机管理服务 · '+state.url);}catch(e){message(e.message,true);}}
async function act(name,body={}){if(busy)return;busy=true;try{render(await api(name,body));message(name==='import'?'导入已开始，可在日志中查看结果':'操作完成');}catch(e){message(e.message,true);}finally{busy=false;}}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.view').forEach(s=>s.hidden=s.id!==b.dataset.view);document.querySelectorAll('nav button').forEach(n=>n.classList.toggle('active',n===b));$('#title').textContent=b.textContent;});
$('#toggle').onclick=()=>act(state?.running?'stop':'start');$('#restart').onclick=()=>act('restart');$('#refresh').onclick=refresh;
$('#copy').onclick=async()=>{try{await navigator.clipboard.writeText(state.url);message('下载地址已复制');}catch{message(state.url);}};
$('#save').onclick=()=>act('settings',{address:$('#ip').value.trim(),port:Number($('#port').value),auto_start:$('#autostart').checked});
$('#theme').onchange=()=>act('settings',{theme:$('#theme').value});
$('#launchAtLogin').onchange=()=>{$('#startHidden').disabled=!$('#launchAtLogin').checked;};
$('#saveDesktop').onclick=()=>act('settings',{theme:$('#theme').value,background_on_close:$('#closeToTray').checked,launch_at_login:$('#launchAtLogin').checked,start_hidden:$('#startHidden').checked});
$('#backgroundPanel').onclick=()=>act('desktop-action',{action:'background'});
$('#importOpen').onclick=()=>$('#importDialog').showModal();$('#cancelImport').onclick=()=>$('#importDialog').close();
$('#browse').onclick=async()=>{if(window.pywebview?.api){const path=await window.pywebview.api.choose_source($('#kind').value);if(path)$('#source').value=path;}else{message('浏览器模式请填写服务器本机路径；桌面控制面板支持选择文件。');}};
$('#importForm').onsubmit=e=>{e.preventDefault();const source=$('#source').value.trim();if(!source)return;$('#importDialog').close();act('import',{source,kind:$('#kind').value,notes:$('#notes').value});};
refresh();setInterval(refresh,3000);
