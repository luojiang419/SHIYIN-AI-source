const $=id=>document.getElementById(id);
const spec=[['strength','拟合强度',0,1,.01,1],['lightness','亮度 L*',-25,25,.5,0],['contrast','对比度',.5,1.5,.01,1],['chroma','饱和度',.3,1.8,.01,1],['a_shift','红绿 a*',-30,30,.5,0],['b_shift','黄蓝 b*',-30,30,.5,0]];
let reference,source,last,records=[],timer,revision=0,running=false,pending=false,exporting=false;
const assets={};
$('controls').innerHTML=spec.map(([k,n,a,b,s,v])=>`<div class="control" data-key="${k}"><label for="${k}" class="control-top">${n}<output id="${k}v">${v}</output></label><input id="${k}" type="range" aria-label="${n}" min="${a}" max="${b}" step="${s}" value="${v}"></div>`).join('');
const values=()=>Object.fromEntries([['model',$('model').value],...spec.map(([k])=>[k,Number($(k).value)])]);
function dirty(){revision++;last=null;$('save').disabled=true;$('download').hidden=true;clearTimeout(timer);if(!reference||!source)return;$('status').textContent='正在更新预览…';$('preview-badge').textContent='UPDATING';timer=setTimeout(()=>render(false),180)}
spec.forEach(([k])=>$(k).oninput=()=>{$(k+'v').value=$(k).value;dirty()});$('model').onchange=dirty;['rr','sr','ar'].forEach(k=>$(k).oninput=dirty);
function decode(url){return new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('无法解码图片'));im.src=url})}
const tokens={};
for(const [key,img] of [['ref','ri'],['src','si']]) $(key).onchange=async()=>{
 const file=$(key).files[0];if(!file)return;const token=Symbol();tokens[key]=token;
 try{const url=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(file)});const im=await decode(url);if(tokens[key]!==token)return;
 const scale=Math.min(1,1000/Math.max(im.width,im.height));const cv=document.createElement('canvas');cv.width=Math.round(im.width*scale);cv.height=Math.round(im.height*scale);cv.getContext('2d').drawImage(im,0,0,cv.width,cv.height);
 assets[key]={url,preview:cv.toDataURL('image/png'),sx:cv.width/im.width,sy:cv.height/im.height};$(img).src=url;
 if(key==='ref'){reference=url;$('rr').value=`0,0,${im.width},${im.height}`}else{source=url;$('sr').value=$('ar').value=`0,0,${im.width},${im.height}`;$('split-before').src=url}
 $(key+'-name').textContent=file.name;dirty();
 }catch(e){$('status').textContent=e.message}
};
function roi(key,small){const box=$(key).value.split(',').map(Number);if(box.length!==4||box.some(x=>!Number.isInteger(x)||x<0)||box[2]<8||box[3]<8)throw Error('区域需填写 x,y,宽,高，宽高至少 8 像素');if(!small)return box;const a=assets[key==='rr'?'ref':'src'];return box.map((n,i)=>Math.round(n*(i%2?a.sy:a.sx)))}
async function request(url,body){const r=await fetch(url,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});const x=await r.json();if(!r.ok)throw Error(x.error||r.status);return x}
function metrics(r){$('metrics').textContent=JSON.stringify({前:r.before,后:r.after},null,2);const fields=[['平均色差 ΔE00','delta_e00_mean'],['亮度偏移 ΔL*','lightness_offset'],['色板覆盖度','palette_overlap'],['高分位色差 P90','delta_e00_p90']];$('metric-cards').replaceChildren(...fields.map(([label,key])=>{const el=document.createElement('div');el.append(document.createTextNode(label));const strong=document.createElement('strong');strong.textContent=key==='palette_overlap'?(r.after[key]*100).toFixed(1)+'%':r.after[key].toFixed(2);el.append(strong);const note=document.createElement('small');note.textContent='原图 '+r.before[key]+' → 当前 '+r.after[key];el.append(note);return el}))}
async function render(full=false){
 if(!reference||!source){$('status').textContent='请先上传两张图片';return}
 if(running){pending=true;if(full)exporting=true;return}running=true;pending=false;const version=revision,c=values(),started=performance.now();$('run').disabled=true;
 try{const r=await request('/fit',{reference:full?reference:assets.ref.preview,source:full?source:assets.src.preview,reference_roi:roi('rr',!full),source_roi:roi('sr',!full),apply_roi:roi('ar',!full),controls:c,preview:!full});
 if(version!==revision)return;
 last={controls:c,metrics:r.after,resolution:full?'original':'preview'};$('oi').src=$('split-after').src=r.image;metrics(r);$('save').disabled=false;$('preview-badge').textContent=(full?'FULL RES':'LIVE')+' · '+Math.round(performance.now()-started)+' ms';$('status').textContent=full?'原尺寸结果已生成，可下载。':'实时预览已更新 · 指标基于最长边 1000px 预览';if(full){$('download').href=r.image;$('download').hidden=false}
 }catch(e){if(version===revision){$('status').textContent=e.message;$('preview-badge').textContent='检查区域'}}finally{running=false;$('run').disabled=false;if(pending||version!==revision){const fullNext=exporting;exporting=false;clearTimeout(timer);timer=setTimeout(()=>render(fullNext),0)}}
}
$('run').onclick=()=>{clearTimeout(timer);render(true)};
async function refresh(){records=await request('/profiles');$('profiles').replaceChildren(new Option('加载面料档案',''),...records.map((p,i)=>new Option(p.name,i)))}
$('refresh').onclick=()=>refresh().catch(e=>$('status').textContent=e.message);
$('save').disabled=true;$('save').onclick=async()=>{try{if(!last)throw Error('等待当前预览完成后再保存');const name=$('name').value.trim();if(!name)throw Error('填写面料名称');await request('/profiles',{name,...last,created_at:new Date().toISOString()});await refresh();$('status').textContent='面料参数已保存为草稿。'}catch(e){$('status').textContent=e.message}};
$('profiles').onchange=()=>{if($('profiles').value==='')return;const p=records[$('profiles').value];if(!p)return;$('name').value=p.name;$('model').value=p.controls.model;spec.forEach(([k])=>{$(k).value=p.controls[k];$(k+'v').value=$(k).value});dirty()};
$('reset').onclick=()=>{spec.forEach(([k,n,a,b,s,v])=>{$(k).value=v;$(k+'v').value=v});dirty()};
$('export').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify({name:$('name').value,controls:values(),metrics:last?.metrics},null,2)],{type:'application/json'}));a.download='fabric-profile.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};
$('wipe').oninput=()=>{$('split-after').style.clipPath=`inset(0 0 0 ${$('wipe').value}%)`;document.querySelector('.split-line').style.left=$('wipe').value+'%'};
for(const type of ['grid','split'])$('view-'+type).onclick=()=>{$('grid').hidden=type!=='grid';$('split').hidden=type!=='split';$('view-grid').classList.toggle('active',type==='grid');$('view-split').classList.toggle('active',type==='split')};
refresh().catch(e=>$('status').textContent=e.message);
