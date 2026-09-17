'use strict';
// Lucide source icons, ISC license: https://lucide.dev/license (from static/vendor/js/lucide.js).
const ICONS={"RadioTower":[["path",{"d":"M4.9 16.1C1 12.2 1 5.8 4.9 1.9"}],["path",{"d":"M7.8 4.7a6.14 6.14 0 0 0-.8 7.5"}],["circle",{"cx":"12","cy":"9","r":"2"}],["path",{"d":"M16.2 4.8c2 2 2.26 5.11.8 7.47"}],["path",{"d":"M19.1 1.9a9.96 9.96 0 0 1 0 14.1"}],["path",{"d":"M9.5 18h5"}],["path",{"d":"m8 22 4-11 4 11"}]],"LayoutDashboard":[["rect",{"width":"7","height":"9","x":"3","y":"3","rx":"1"}],["rect",{"width":"7","height":"5","x":"14","y":"3","rx":"1"}],["rect",{"width":"7","height":"9","x":"14","y":"12","rx":"1"}],["rect",{"width":"7","height":"5","x":"3","y":"16","rx":"1"}]],"PackageOpen":[["path",{"d":"M12 22v-9"}],["path",{"d":"M15.17 2.21a1.67 1.67 0 0 1 1.63 0L21 4.57a1.93 1.93 0 0 1 0 3.36L8.82 14.79a1.655 1.655 0 0 1-1.64 0L3 12.43a1.93 1.93 0 0 1 0-3.36z"}],["path",{"d":"M20 13v3.87a2.06 2.06 0 0 1-1.11 1.83l-6 3.08a1.93 1.93 0 0 1-1.78 0l-6-3.08A2.06 2.06 0 0 1 4 16.87V13"}],["path",{"d":"M21 12.43a1.93 1.93 0 0 0 0-3.36L8.83 2.2a1.64 1.64 0 0 0-1.63 0L3 4.57a1.93 1.93 0 0 0 0 3.36l12.18 6.86a1.636 1.636 0 0 0 1.63 0z"}]],"MonitorSmartphone":[["path",{"d":"M18 8V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h8"}],["path",{"d":"M10 19v-3.96 3.15"}],["path",{"d":"M7 19h5"}],["rect",{"width":"6","height":"10","x":"16","y":"12","rx":"2"}]],"ScrollText":[["path",{"d":"M15 12h-5"}],["path",{"d":"M15 8h-5"}],["path",{"d":"M19 17V5a2 2 0 0 0-2-2H4"}],["path",{"d":"M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3"}]],"SlidersHorizontal":[["path",{"d":"M10 5H3"}],["path",{"d":"M12 19H3"}],["path",{"d":"M14 3v4"}],["path",{"d":"M16 17v4"}],["path",{"d":"M21 12h-9"}],["path",{"d":"M21 19h-5"}],["path",{"d":"M21 5h-7"}],["path",{"d":"M8 10v4"}],["path",{"d":"M8 12H3"}]],"PanelBottomClose":[["rect",{"width":"18","height":"18","x":"3","y":"3","rx":"2"}],["path",{"d":"M3 15h18"}],["path",{"d":"m15 8-3 3-3-3"}]],"RefreshCw":[["path",{"d":"M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"}],["path",{"d":"M21 3v5h-5"}],["path",{"d":"M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"}],["path",{"d":"M8 16H3v5"}]],"Upload":[["path",{"d":"M12 3v12"}],["path",{"d":"m17 8-5-5-5 5"}],["path",{"d":"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"}]],"Power":[["path",{"d":"M12 2v10"}],["path",{"d":"M18.4 6.6a9 9 0 1 1-12.77.04"}]],"RotateCw":[["path",{"d":"M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"}],["path",{"d":"M21 3v5h-5"}]],"Square":[["rect",{"width":"18","height":"18","x":"3","y":"3","rx":"2"}]],"Copy":[["rect",{"width":"14","height":"14","x":"8","y":"8","rx":"2","ry":"2"}],["path",{"d":"M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"}]],"Radio":[["path",{"d":"M16.247 7.761a6 6 0 0 1 0 8.478"}],["path",{"d":"M19.075 4.933a10 10 0 0 1 0 14.134"}],["path",{"d":"M4.925 19.067a10 10 0 0 1 0-14.134"}],["path",{"d":"M7.753 16.239a6 6 0 0 1 0-8.478"}],["circle",{"cx":"12","cy":"12","r":"2"}]],"Monitor":[["rect",{"width":"20","height":"14","x":"2","y":"3","rx":"2"}],["line",{"x1":"8","x2":"16","y1":"21","y2":"21"}],["line",{"x1":"12","x2":"12","y1":"17","y2":"21"}]],"Download":[["path",{"d":"M12 15V3"}],["path",{"d":"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"}],["path",{"d":"m7 10 5 5 5-5"}]],"Boxes":[["path",{"d":"M2.97 12.92A2 2 0 0 0 2 14.63v3.24a2 2 0 0 0 .97 1.71l3 1.8a2 2 0 0 0 2.06 0L12 19v-5.5l-5-3-4.03 2.42Z"}],["path",{"d":"m7 16.5-4.74-2.85"}],["path",{"d":"m7 16.5 5-3"}],["path",{"d":"M7 16.5v5.17"}],["path",{"d":"M12 13.5V19l3.97 2.38a2 2 0 0 0 2.06 0l3-1.8a2 2 0 0 0 .97-1.71v-3.24a2 2 0 0 0-.97-1.71L17 10.5l-5 3Z"}],["path",{"d":"m17 16.5-5-3"}],["path",{"d":"m17 16.5 4.74-2.85"}],["path",{"d":"M17 16.5v5.17"}],["path",{"d":"M7.97 4.42A2 2 0 0 0 7 6.13v4.37l5 3 5-3V6.13a2 2 0 0 0-.97-1.71l-3-1.8a2 2 0 0 0-2.06 0l-3 1.8Z"}],["path",{"d":"M12 8 7.26 5.15"}],["path",{"d":"m12 8 4.74-2.85"}],["path",{"d":"M12 13.5V8"}]],"Activity":[["path",{"d":"M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"}]],"ArrowUpRight":[["path",{"d":"M7 7h10v10"}],["path",{"d":"M7 17 17 7"}]],"Palette":[["path",{"d":"M12 22a1 1 0 0 1 0-20 10 9 0 0 1 10 9 5 5 0 0 1-5 5h-2.25a1.75 1.75 0 0 0-1.4 2.8l.3.4a1.75 1.75 0 0 1-1.4 2.8z"}],["circle",{"cx":"13.5","cy":"6.5","r":".5","fill":"currentColor"}],["circle",{"cx":"17.5","cy":"10.5","r":".5","fill":"currentColor"}],["circle",{"cx":"6.5","cy":"12.5","r":".5","fill":"currentColor"}],["circle",{"cx":"8.5","cy":"7.5","r":".5","fill":"currentColor"}]],"Save":[["path",{"d":"M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"}],["path",{"d":"M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"}],["path",{"d":"M7 3v4a1 1 0 0 0 1 1h7"}]],"Network":[["rect",{"x":"16","y":"16","width":"6","height":"6","rx":"1"}],["rect",{"x":"2","y":"16","width":"6","height":"6","rx":"1"}],["rect",{"x":"9","y":"2","width":"6","height":"6","rx":"1"}],["path",{"d":"M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"}],["path",{"d":"M12 12V8"}]],"X":[["path",{"d":"M18 6 6 18"}],["path",{"d":"m6 6 12 12"}]],"FolderOpen":[["path",{"d":"m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"}]],"ShieldCheck":[["path",{"d":"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"}],["path",{"d":"m9 12 2 2 4-4"}]],"Zap":[["path",{"d":"M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"}]],"ScanFace":[["path",{"d":"M3 7V5a2 2 0 0 1 2-2h2"}],["path",{"d":"M17 3h2a2 2 0 0 1 2 2v2"}],["path",{"d":"M21 17v2a2 2 0 0 1-2 2h-2"}],["path",{"d":"M7 21H5a2 2 0 0 1-2-2v-2"}],["path",{"d":"M8 14s1.5 2 4 2 4-2 4-2"}],["path",{"d":"M9 9h.01"}],["path",{"d":"M15 9h.01"}]],"FileVideo":[["path",{"d":"M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z"}],["path",{"d":"M14 2v5a1 1 0 0 0 1 1h5"}],["path",{"d":"M15.033 13.44a.647.647 0 0 1 0 1.12l-4.065 2.352a.645.645 0 0 1-.968-.56v-4.704a.645.645 0 0 1 .967-.56z"}]],"AppWindow":[["rect",{"x":"2","y":"4","width":"20","height":"16","rx":"2"}],["path",{"d":"M10 4v4"}],["path",{"d":"M2 8h20"}],["path",{"d":"M6 4v4"}]]};
function icon(name){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');for(const [k,v] of Object.entries({viewBox:'0 0 24 24',fill:'none',stroke:'currentColor','stroke-width':2,'stroke-linecap':'round','stroke-linejoin':'round','aria-hidden':'true'}))svg.setAttribute(k,v);for(const [tag,attrs] of ICONS[name]||ICONS.Boxes){const n=document.createElementNS(svg.namespaceURI,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);svg.append(n);}return svg;}
document.querySelectorAll('[data-icon]').forEach(n=>n.replaceWith(icon(n.dataset.icon)));
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
let noticeTimer;
function message(text,error=false){clearTimeout(noticeTimer);$('#notice').hidden=false;$('#notice').textContent=text;$('#notice').classList.toggle('error',error);if(!error)noticeTimer=setTimeout(()=>$('#notice').hidden=true,4500);}
async function api(path, body){
  const response=await fetch('/api/'+path,{method:body===undefined?'GET':'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await response.json(); if(!response.ok)throw new Error(data.error || '请求失败'); return data;
}
const names={hot:'应用增量包','hot-bootstrap':'更新器引导包','hot-updater':'更新器修复包',full:'全量安装包','person-depth':'人物深度组件','video-depth':'深度视频模型','video-depth-runtime':'深度视频运行时'};
const states={published:'已发布',paused:'已暂停',archived:'历史版本'};
function element(tag,text,className){const el=document.createElement(tag);el.textContent=text;if(className)el.className=className;return el;}
function bytes(value){let n=Math.max(0,Number(value)||0),i=0;const units=['B','KB','MB','GB','TB'];while(n>=1024&&i<4){n/=1024;i++;}return n.toFixed(i?1:0)+' '+units[i];}
function clientLabel(ip,usernames){
  const known=usernames.get(ip),username=known?.size===1?[...known][0]:'';
  return username?username+' · '+ip:ip;
}
function transferRow(t,usernames){
  const row=element('div','','transfer');
  const state={downloading:'正在发送',completed:'发送完成',interrupted:'连接中断 / 未完成'}[t.state]||t.state;
  row.append(element('strong',clientLabel(t.ip,usernames)+' · '+state),element('p',t.resource,'resource'));
  const progress=element('progress');progress.max=t.total||1;progress.value=t.sent;progress.setAttribute('aria-label','当前文件/断点请求发送进度');
  row.append(progress,element('small',bytes(t.sent)+' / '+bytes(t.total)+' · 当前请求 '+(t.total?Math.min(100,t.sent/t.total*100).toFixed(1):'100')+'%'+(t.offset?' · 断点偏移 '+bytes(t.offset):'')+' · '+new Date(t.started*1000).toLocaleTimeString(),'muted'));
  return row;
}
function renderTraffic(data){
  const t=data.traffic;if(!t)return;
  const usernames=new Map();
  for(const group of bugClientGroups(data)){
    if(!group.username||!group.ip)continue;
    if(!usernames.has(group.ip))usernames.set(group.ip,new Set());
    usernames.get(group.ip).add(group.username);
  }
  $('#downloadCount').textContent=t.active_count;$('#downloadClients').textContent=t.downloading_clients+' 台客户端下载中';
  $('#downloadSpeed').textContent=bytes(t.speed_bps)+'/s';$('#todayTraffic').textContent=bytes(t.today_bytes);
  $('#peakSpeed').textContent='今日峰值 '+bytes(t.peak_bps)+'/s（1秒采样）';
  const max=Math.max(1,...t.history.map(p=>p.speed_bps));
  $('#trafficLine').setAttribute('points',t.history.map((p,i)=>(i*720/59).toFixed(1)+','+(116-p.speed_bps/max*108).toFixed(1)).join(' '));
  $('#trafficCaption').textContent=t.day+' · 曲线上限 '+bytes(max)+'/s · 每秒刷新'+(t.persistence_error?' · 流量保存暂时失败，正在重试':'');
  for(const [selector,items,empty] of [['#activeDownloads',t.active,'当前没有下载请求'],['#recentDownloads',t.recent,'暂无下载记录']]){
    $(selector).replaceChildren(...items.map(item=>transferRow(item,usernames)));if(!items.length)$(selector).append(element('p',empty,'empty'));
  }
  const clients=new Map(data.clients.map(c=>[c.ip,c]));
  for(const ip of Object.keys(t.clients))if(!clients.has(ip))clients.set(ip,{ip,seen:0,version:''});
  $('#clientList').replaceChildren(...Array.from(clients.values()).map(c=>{
    const stats=t.clients[c.ip]||{},active=t.active.filter(a=>a.ip===c.ip),row=element('article','','client');
    const head=element('div','','client-head'),name=element('div','','client-name');
    name.append(icon('Monitor'),element('strong',clientLabel(c.ip,usernames)));
    const status=active.length?'下载中':c.update_state==='outdated'?'待补齐':c.update_state==='current'?'已是最新':Date.now()/1000-c.seen<300?'近期连接':'暂无活动';
    head.append(name,element('span',status,'badge '+(active.length?'cyan':c.update_state==='outdated'?'orange':c.update_state==='current'?'green':'')));row.append(head);
    const updateState={current:'已是最新',outdated:'待补齐',unknown:'未报告'}[c.update_state]||'未报告';
    const details=element('dl');for(const [label,value] of [['应用版本',c.version||'未报告'],['更新状态',updateState],['目标序号',c.target_version||'—'],['实时速度',bytes(stats.speed_bps)+'/s'],['今日流量',bytes(stats.today_bytes)],['今日峰值',bytes(stats.peak_bps)+'/s'],['下载请求',String(active.length)],['最近连接',c.seen?new Date(c.seen*1000).toLocaleTimeString():'—']]){const cell=element('div');cell.append(element('dt',label),element('dd',value));details.append(cell);}row.append(details);
    active.forEach(a=>row.append(transferRow(a,usernames)));return row;
  }));
  if(!clients.size)$('#clientList').append(element('p','尚无客户端连接记录','muted'));
}
const resourceIcons={hot:'PackageOpen','hot-bootstrap':'RefreshCw','hot-updater':'Zap',full:'AppWindow','person-depth':'ScanFace','video-depth':'FileVideo','video-depth-runtime':'Cpu'};
const releaseGroups=[
  {id:'application',title:'应用热更新',description:'面向日常功能发布的应用增量包',kinds:['hot']},
  {id:'updater',title:'更新器与兼容组件',description:'更新器修复包及旧客户端引导包',kinds:['hot-updater','hot-bootstrap']},
  {id:'models',title:'模型与运行时',description:'独立分发的深度模型与设备适配运行时',kinds:['person-depth','video-depth','video-depth-runtime']},
  {id:'installer',title:'全量安装包',description:'仅用于完整安装或明确要求的全量升级',kinds:['full']}
];
function releaseRow(item,actions,index){
  if(!actions){const row=element('tr'),name=element('td');name.append(element('strong',names[item.kind]||item.kind),element('small',item.kind==='hot'?'单个签名包':item.kind==='hot-bootstrap'?'旧客户端兼容':item.kind==='hot-updater'?'v3客户端迁移':item.kind==='full'?'Windows x64':'模型组件'));row.append(name,element('td',item.version,'version'),element('td',new Date(item.created*1000).toLocaleDateString()));const status=element('td');status.append(element('span',states[item.state],'badge green'));row.append(status);return row;}
  const row=element('article','','resource-row'),mark=element('span','','resource-icon'),copy=element('div','','resource-main'),version=element('div','','resource-cell'),actionsBox=element('div','','row-actions');mark.append(icon(resourceIcons[item.kind]||'Boxes'));copy.append(element('strong',names[item.kind]||item.kind),element('small','发布于 '+new Date(item.created*1000).toLocaleString()));
  const notes=element('p',item.notes?.trim()||'未填写更新日志','release-notes');notes.prepend(element('span','更新日志 · '));copy.append(notes);version.append(element('small','资源版本'),element('strong',item.version));
  actionsBox.append(element('span',states[item.state],'badge '+(item.state==='published'?'green':'orange')));const button=element('button',item.state==='published'?'暂停发布':'发布此版本','button');button.onclick=()=>act('release',{id:item.id,state:item.state==='published'?'paused':'published'});actionsBox.append(button);row.append(mark,copy,version,actionsBox);return row;
}
function renderReleaseGroups(releases){
  const sorted=[...releases].sort((a,b)=>Number(b.created)-Number(a.created));
  const sections=releaseGroups.map(group=>{
    const items=sorted.filter(item=>group.kinds.includes(item.kind));
    if(!items.length)return null;
    const section=element('section','','resource-section');
    const header=element('div','','resource-section-header'),copy=element('div'),title=element('h3',group.title),description=element('p',group.description);
    copy.append(title,description);header.append(copy,element('span',items.length+' 个版本','resource-count'));section.append(header);
    const list=element('div','','resource-section-list');
    items.forEach((item,index)=>{const row=releaseRow(item,true,index+1);row.prepend(element('span',String(index+1).padStart(2,'0'),'resource-order'));list.append(row);});
    section.append(list);return {section,latest:Number(items[0].created)||0};
  }).filter(Boolean).sort((a,b)=>b.latest-a.latest).map(entry=>entry.section);
  $('#releaseList').replaceChildren(...sections);
  if(!sections.length)$('#releaseList').append(element('p','尚未发布资源，请先导入热更新或模型。','empty'));
}
function render(data){
  state=data;$('#running').textContent=data.running?'服务运行中':'服务已停止';$('#address').textContent=data.url;$('#toggleText').textContent=data.running?'停止服务':'启动服务';$('#toggle').classList.toggle('danger',data.running);$('#miniState').textContent=data.running?'分发服务运行中':'分发服务已停止';$('#miniDot').classList.toggle('stopped',!data.running);$('#servicePulse').classList.toggle('stopped',!data.running);$('#miniAddress').textContent=data.url.replace('http://','');$('#serviceDescription').textContent=data.running?'客户端可发现并下载已发布资源':'客户端暂时无法检查与下载资源';
  applyTheme(data.settings.theme || 'system');
  $('#online').textContent=data.clients.filter(c=>Date.now()/1000-c.seen<300).length;$('#published').textContent=data.releases.filter(r=>r.state==='published').length;$('#uptime').textContent=Math.floor(data.uptime/60)+' 分钟';
  $('#summary').replaceChildren(...data.releases.filter(r=>r.state==='published').map(r=>releaseRow(r,false)));if(!$('#summary').children.length){const tr=element('tr'),td=element('td','尚未发布资源，请先导入热更新或模型。','empty');td.colSpan=4;tr.append(td);$('#summary').append(tr);}
  renderReleaseGroups(data.releases);
  $('#logList').replaceChildren(...data.logs.map(l=>{const row=element('div','','log-line');row.append(element('time',new Date(l.created*1000).toLocaleTimeString()),element('span',l.message));return row;}));
  $('#activityList').replaceChildren(...data.logs.slice(0,4).map(l=>{const row=element('div','','activity'),copy=element('div');copy.append(element('strong',l.message));row.append(element('i'),copy,element('time',new Date(l.created*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})));return row;}));
  if(!data.logs.length)$('#activityList').append(element('p','暂无活动记录','empty'));
  $('#dataRoot').textContent=data.data;$('#publicKey').textContent=data.public_key;
  renderBugs(data);
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
async function refresh(){if(refreshing||busy)return;refreshing=true;try{render(await api('status'));if(!state.job.running&&!state.job.error&&$('#notice').classList.contains('error')){$('#notice').hidden=true;$('#notice').classList.remove('error');}}catch(e){message('监控连接失败，当前显示为上次数据：'+e.message,true);}finally{refreshing=false;}}
async function act(name,body={}){if(busy)return;busy=true;try{render(await api(name,body));message(name==='import'?'导入已开始，可在日志中查看结果':'操作完成');}catch(e){message(e.message,true);}finally{busy=false;}}
let selectedBugClient='', selectedBugReport='';
function renderHardware(detail){
  const root=$('#bugHardware'), machine=detail.machine||{};
  const labels={system:'操作系统',os:'Windows 系统',cpu:'处理器',memory:'内存',disks:'磁盘',displayAdapters:'显示适配器',nvidiaGpus:'NVIDIA 显卡',name:'名称',Name:'型号',release:'系统版本',version:'版本号',architecture:'架构',caption:'系统名称',build:'内部版本',NumberOfCores:'核心数',NumberOfLogicalProcessors:'逻辑处理器',totalBytes:'总容量',Model:'型号',Size:'容量',InterfaceType:'接口类型',DriverVersion:'驱动版本',driverVersion:'驱动版本',AdapterRAM:'显存（系统报告）',memoryMiB:'显存',computeCapability:'计算能力',windowsDiagnostics:'Windows 诊断'};
  function valueText(key,value){
    if(value===null||value===undefined||value==='')return '未提供';
    if(['totalBytes','Size','AdapterRAM','memoryMiB'].includes(key)&&Number.isFinite(Number(value))&&Number(value)>=0){
      const bytes=Number(value)*(key==='memoryMiB'?1048576:1);
      return bytes>=1073741824?(bytes/1073741824).toLocaleString('zh-CN',{maximumFractionDigits:2})+' GB':(bytes/1048576).toLocaleString('zh-CN',{maximumFractionDigits:1})+' MB';
    }
    return typeof value==='boolean'?(value?'是':'否'):String(value);
  }
  function fields(value){
    const list=element('dl','','hardware-fields');
    for(const [key,item] of Object.entries(value)){
      const row=element('div','','hardware-row');
      row.append(element('dt',labels[key]||key));
      const cell=element('dd');
      if(item&&typeof item==='object')cell.append(fields(item));else cell.textContent=valueText(key,item);
      row.append(cell);list.append(row);
    }
    if(!list.children.length)list.append(element('p','未提供','hardware-empty'));
    return list;
  }
  const stamp=Number(detail.updatedAt);
  root.replaceChildren(element('div',stamp>0?'更新于 '+new Date(stamp*1000).toLocaleString():'更新时间未知','hardware-updated'));
  for(const [key,value] of Object.entries(machine)){
    const section=element('section','','hardware-group'),items=Array.isArray(value)?value:[value];
    const header=element('div','','hardware-heading');header.append(element('h4',labels[key]||key));
    if(Array.isArray(value))header.append(element('span',items.length+' 项','badge'));
    section.append(header);
    items.forEach((item,index)=>{
      const block=element('div','','hardware-device');
      if(items.length>1)block.append(element('div',String(index+1).padStart(2,'0'),'hardware-index'));
      block.append(item&&typeof item==='object'?fields(item):element('p',valueText(key,item)));section.append(block);
    });
    if(!items.length)section.append(element('p','未检测到或未上报','hardware-empty'));
    root.append(section);
  }
  if(!Object.keys(machine).length)root.append(element('p','尚无设备快照','hardware-empty'));
}
function bugClientGroups(data){
  const records=new Map();
  const memberKey=(user,client)=>JSON.stringify([user||'admin',client]);
  for(const d of data.bug_devices||[]){
    records.set(memberKey(d.user_id,d.client_id),{user:d.user_id||'admin',client:d.client_id,ip:d.ip,seen:Number(d.updated)||0,username:d.computer_user||'',hostname:d.computer_name||''});
  }
  for(const r of data.bug_reports||[]){
    const key=memberKey(r.user_id,r.client_id),previous=records.get(key);
    if(!previous)records.set(key,{user:r.user_id||'admin',client:r.client_id,ip:r.ip,seen:Number(r.created)||0,username:'',hostname:''});
    else if(Number(r.created)>previous.seen){previous.seen=Number(r.created);previous.ip=r.ip;}
  }
  const identity=r=>JSON.stringify([r.hostname.toLowerCase()||r.ip,r.username.toLowerCase()]);
  const knownByIp=new Map();
  for(const r of records.values())if(r.username){if(!knownByIp.has(r.ip))knownByIp.set(r.ip,new Set());knownByIp.get(r.ip).add(identity(r));}
  const groups=new Map();
  for(const [member,r] of records){
    const matches=knownByIp.get(r.ip);
    const key=r.username?identity(r):matches?.size===1?[...matches][0]:JSON.stringify(['legacy',r.ip]);
    let group=groups.get(key);
    if(!group){group={key,members:[],seen:-1,username:'',hostname:''};groups.set(key,group);}
    group.members.push(member);
    if(r.username){group.username=r.username;group.hostname=r.hostname;}
    if(r.seen>group.seen)Object.assign(group,{user:r.user,client:r.client,ip:r.ip,seen:r.seen});
  }
  return [...groups.values()].sort((a,b)=>b.seen-a.seen);
}
function renderBugs(data){
  $('#bugRoot').textContent=data.bug_log_root||'';
  const reports=data.bug_reports||[],clients=bugClientGroups(data);
  const selected=clients.find(c=>c.key===selectedBugClient||c.members.includes(selectedBugClient));
  if(selected)selectedBugClient=selected.key;
  $('#bugClients').replaceChildren(...clients.map(c=>{
    const b=element('button','','bug-item');
    const top=element('div','','bug-client-heading'),online=Date.now()/1000-c.seen<300;
    top.append(element('strong',c.username||'未上报用户名'),element('span',online?'在线':'离线','badge '+(online?'green':'')));
    b.append(top,element('span',c.ip+(c.hostname?' · '+c.hostname:'')),element('small','最近活跃 '+new Date(c.seen*1000).toLocaleString()));
    b.classList.toggle('active',selectedBugClient===c.key);b.onclick=async()=>{
      selectedBugClient=selectedBugClient===c.key?'':c.key;renderBugs(state);
      if(!selectedBugClient){$('#bugHardware').textContent='选择客户端查看设备信息';return;}
      const requestedClient=selectedBugClient;
      $('#bugHardware').textContent='正在加载设备信息…';
      try{const detail=await api('bug-devices/'+encodeURIComponent(c.user)+'/'+encodeURIComponent(c.client));
        if(selectedBugClient===requestedClient)renderHardware(detail);
      }catch(e){if(selectedBugClient===requestedClient)$('#bugHardware').textContent='设备信息加载失败：'+e.message;}
    };return b;
  }));
  if(!clients.length)$('#bugClients').append(element('p','暂无客户端记录','empty'));
  const members=new Set(selected?.members||[]);
  const shown=reports.filter(r=>!selectedBugClient||members.has(JSON.stringify([r.user_id||'admin',r.client_id])));
  $('#bugReports').replaceChildren(...shown.map(r=>{
    const b=element('button','','bug-item');
    b.append(element('strong',r.kind==='error'?'错误':r.kind==='heartbeat'?'运行状态':'运行日志'),element('span',r.summary||r.client_id),element('small',new Date(r.created*1000).toLocaleString()));
    b.classList.toggle('active',selectedBugReport===r.id);
    b.onclick=async()=>{selectedBugReport=r.id;renderBugs(state);try{$('#bugDetail').textContent=JSON.stringify(await api('bug-reports/'+encodeURIComponent(r.id)),null,2);}catch(e){message(e.message,true);}};return b;
  }));
  if(!shown.length)$('#bugReports').append(element('p','暂无报告','empty'));
}
function navigate(view){document.querySelectorAll('.view').forEach(s=>s.hidden=s.id!==view);document.querySelectorAll('nav button').forEach(n=>n.classList.toggle('active',n.dataset.view===view));$('#title').textContent={overview:'服务总览',releases:'资源与发布',clients:'客户端',bugs:'BUG反馈',logs:'服务日志',settings:'服务设置'}[view];window.scrollTo(0,0);}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>navigate(b.dataset.view));
document.querySelectorAll('[data-go]').forEach(b=>b.onclick=()=>navigate(b.dataset.go));
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
