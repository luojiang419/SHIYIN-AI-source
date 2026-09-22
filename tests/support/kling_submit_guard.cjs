const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('tools/chrome-kling-bridge/adapter.js','utf8');
function fixture(mode='success'){
  let clicks=0,now=0,created=false;
  const storage=new Map();
  const editor={innerText:'一次生成',getClientRects:()=>[{}],closest:()=>({querySelector:()=>({querySelectorAll:()=>[]})})};
  const button={innerText:'生成',getClientRects:()=>[{}],getAttribute:()=>null,classList:{contains:()=>false},click(){clicks++;if(mode==='throw')throw Error('断线');created=mode==='success';}};
  const row={id:'new-task',querySelector:selector=>selector==='.prompt-display'?{innerText:'一次生成'}:{}};
  const document={querySelector:()=>null,querySelectorAll:selector=>selector.includes('contenteditable')?[editor]:selector.includes('button.button-pay')?[button]:selector==='.virtual-item[id]'&&created?[row]:[]};
  const context=vm.createContext({window:{},document,Map,Set,Date:{now:()=>now+=10000},setTimeout:fn=>fn(),sessionStorage:{getItem:key=>storage.get(key),setItem:(k,v)=>storage.set(k,v)}});
  vm.runInContext(source.replace('window.ShiyinKlingAdapter =','window.seed=value=>completed={...value,settingsSignature:settingsSignature()}; window.ShiyinKlingAdapter ='),context);
  context.window.seed({id:'one',text:'一次生成',pool:'',settings:{}});
  return {api:context.window.ShiyinKlingAdapter,editor,clicks:()=>clicks};
}
(async()=>{
  const ok=fixture();
  assert.equal((await ok.api.submit('one')).status,'submitted');
  await assert.rejects(()=>ok.api.submit('one'),/禁止重复点击/);
  assert.equal(ok.clicks(),1);
  const unknown=fixture('timeout');
  assert.equal((await unknown.api.submit('one')).status,'unknown');
  await assert.rejects(()=>unknown.api.submit('one'),/禁止重复点击/);
  assert.equal(unknown.clicks(),1);
  const lost=fixture('throw');
  await assert.rejects(()=>lost.api.submit('one'),/断线/);
  await assert.rejects(()=>lost.api.submit('one'),/禁止重复点击/);
  assert.equal(lost.clicks(),1);
  const changed=fixture();changed.editor.innerText='人工修改';
  await assert.rejects(()=>changed.api.submit('one'),/已被修改/);
  assert.equal(changed.clicks(),0);
  console.log('4 submit guard cases passed: receipt, timeout, click exception, manual edit');
})().catch(e=>{console.error(e);process.exitCode=1;});
