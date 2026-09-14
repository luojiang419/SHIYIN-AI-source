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
function bytes(value){let n=Math.max(0,Number(value)||0),i=0;const units=['B','KB','MB','GB','TB'];while(n>=1024&&i<4){n/=1024;i++;}return n.toFixed(i?1:0)+' '+units[i];}
function transferRow(t){
  const row=element('div','','transfer');
  const state={downloading:'正在发送',completed:'发送完成',interrupted:'连接中断 / 未完成'}[t.state]||t.state;
  row.append(element('strong',t.ip+' · '+state),element('p',t.resource,'resource'));
  const progress=element('progress');progress.max=t.total||1;progress.value=t.sent;progress.setAttribute('aria-label','当前文件/断点请求发送进度');
  row.append(progress,element('small',bytes(t.sent)+' / '+bytes(t.total)+' · 当前请求 '+(t.total?Math.min(100,t.sent/t.total*100).toFixed(1):'100')+'%'+(t.offset?' · 断点偏移 '+bytes(t.offset):'')+' · '+new Date(t.started*1000).toLocaleTimeString(),'muted'));
  return row;
}
function renderTraffic(data){
  const t=data.traffic;if(!t)return;
  $('#downloadCount').textContent=t.active_count;$('#downloadClients').textContent=t.downloading_clients+' 台客户端下载中';
  $('#downloadSpeed').textContent=bytes(t.speed_bps)+'/s';$('#todayTraffic').textContent=bytes(t.today_bytes);
  $('#peakSpeed').textContent='今日峰值 '+bytes(t.peak_bps)+'/s（1秒采样）';
  const max=Math.max(1,...t.history.map(p=>p.speed_bps));
  $('#trafficLine').setAttribute('points',t.history.map((p,i)=>(i*720/59).toFixed(1)+','+(116-p.speed_bps/max*108).toFixed(1)).join(' '));
  $('#trafficCaption').textContent=t.day+' · 曲线上限 '+bytes(max)+'/s · 每秒刷新'+(t.persistence_error?' · 流量保存暂时失败，正在重试':'');
  for(const [selector,items,empty] of [['#activeDownloads',t.active,'当前没有下载请求'],['#recentDownloads',t.recent,'暂无下载记录']]){
    $(selector).replaceChildren(...items.map(transferRow));if(!items.length)$(selector).append(element('p',empty,'muted'));
  }
  const clients=new Map(data.clients.map(c=>[c.ip,c]));
  for(const ip of Object.keys(t.clients))if(!clients.has(ip))clients.set(ip,{ip,seen:0,version:''});
  $('#clientList').replaceChildren(...Array.from(clients.values()).map(c=>{
    const stats=t.clients[c.ip]||{},active=t.active.filter(a=>a.ip===c.ip),row=element('article');
    row.append(element('strong',c.ip),element('span',active.length?'下载中 · '+active.length+' 个请求':Date.now()/1000-c.seen<300?'近期连接':'暂无近期活动','badge'));
    row.append(element('p','应用版本：'+(c.version||'未报告')+' · 最近连接：'+(c.seen?new Date(c.seen*1000).toLocaleString():'—')),
      element('p','实时速度 '+bytes(stats.speed_bps)+'/s · 今日流量 '+bytes(stats.today_bytes)+' · 今日峰值 '+bytes(stats.peak_bps)+'/s'));
    active.forEach(a=>row.append(transferRow(a)));return row;
  }));
  if(!clients.size)$('#clientList').append(element('p','尚无客户端连接记录','muted'));
}
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
  renderTraffic(data);
  if(!$('#settings').contains(document.activeElement)){
    $('#ip').value=data.settings.address;$('#port').value=data.settings.port;$('#autostart').checked=data.settings.auto_start;
    $('#theme').value=data.settings.theme || 'system';$('#closeToTray').checked=data.settings.background_on_close!==false;
    $('#launchAtLogin').checked=!!data.settings.launch_at_login;$('#startHidden').checked=data.settings.start_hidden!==false;
    $('#startHidden').disabled=!$('#launchAtLogin').checked;
  }
  if(data.job.running)message(data.job.message);else if(data.job.error)message(data.job.error,true);
}
let refreshing=false;
async function refresh(){if(refreshing||busy)return;refreshing=true;try{render(await api('status'));if(!state.job.running&&!state.job.error)message('已连接本机管理服务 · '+state.url);}catch(e){message('监控连接失败，当前显示为上次数据：'+e.message,true);}finally{refreshing=false;}}
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
refresh();setInterval(refresh,1000);
