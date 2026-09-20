"""只读归档本轮真实页面生成记录及图片，不读取平台凭据。"""
import json, sqlite3, shutil, urllib.request
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '案例/批量复刻培训-20260920'
OUT.mkdir(exist_ok=True, parents=True)
ASSETS = OUT/'assets'
ASSETS.mkdir(exist_ok=True)
refs = [('A/目标图.jpg','a-target'),('A/A产品.jpg','a-product'),('A/A产品面料细节.jpg','a-detail'),('A/服装参考B.jpg','a-style-b'),('A/服装参考C.jpg','a-style-c'),('b/目标图.jpg','b-target'),('b/服装参考.jpg','b-product'),('b/腰头细节设计+面料细节.jpg','b-detail')]
for src, name in refs:
    shutil.copy2(Path('D:/data/图片/案例')/src, ASSETS/(name+'.jpg'))
c = sqlite3.connect('file:D:/Program Files/SHIYIN AI/data/database/canvas.db?mode=ro', uri=True)
records=[]
for row in c.execute('SELECT id,payload_json FROM generation_history ORDER BY created_at DESC LIMIT 30'):
    p=json.loads(row[1])
    style=p.get('batch_outfit',{}).get('style_name','')
    if style not in ('培训-A-上衣三款-0920','培训-B-棕裤细节-0920'): continue
    params=p.get('params',{})
    references=params.get('reference_images',[])
    garment=next((r.get('name','') for r in references if r.get('role')=='target_image'),'')
    key={'A产品.jpg':'a-product','服装参考B.jpg':'a-style-b','服装参考C.jpg':'a-style-c','服装参考.jpg':'b-product'}[garment]
    filename=key+'-result'+Path(p['images'][0]).suffix
    shutil.copy2(Path('D:/Program Files/SHIYIN AI/data/media/generated')/Path(p['images'][0]).name,ASSETS/filename)
    with Image.open(ASSETS/filename) as im: dimensions=list(im.size)
    record=dict(id=row[0],style=style,garment=garment,key=key,image='assets/'+filename,dimensions=dimensions,model=p.get('model'),provider=p.get('provider_id'),seconds=p.get('generation_elapsed_seconds'),requested_size=params.get('size'),quality=params.get('quality'),references=[{'role':r.get('role'),'name':r.get('name'),'url':r.get('url')} for r in references],enhancement=p.get('fabric_enhancement',[]),archive=p.get('batch_outfit_archive'))
    records.append(record)
(OUT/'evidence/generation-records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
sheet=Image.new('RGB',(400*max(1,len(records)),560),'#eee9e1')
d=ImageDraw.Draw(sheet)
for i,r in enumerate(records):
    im=ImageOps.contain(Image.open(OUT/r['image']),(390,520))
    sheet.paste(im,(i*400,0));d.text((i*400+8,530),r['key'],fill='black')
sheet.save(OUT/'evidence/results-contact.jpg')
print(json.dumps([{'key':r['key'],'dimensions':r['dimensions'],'seconds':r['seconds'],'enhancement':r['enhancement']} for r in records],ensure_ascii=True))
row=c.execute('SELECT payload_json FROM canvases WHERE id=?',('5cb247a0e8aa42dbbf0b71953c85c32f',)).fetchone()
if row:
    canvas=json.loads(row[0])
    outputs=[im for n in canvas.get('nodes',[]) if n.get('type')=='output' for im in n.get('images',[])]
    if outputs:
        im=outputs[-1]
        shutil.copy2(Path('D:/Program Files/SHIYIN AI/data/media/generated')/Path(im['url']).name,ASSETS/'b-node-result.png')
        audit={'canvas_id':'5cb247a0e8aa42dbbf0b71953c85c32f','image':'assets/b-node-result.png','run_ms':im.get('runMs'),'model':'gemini-3-pro-image-preview','provider':'shiying','resolution':'4k','instruction':im.get('run',{}).get('prompt',''),'prior_attempt':'补充要求触发助手增量与人物身份保留约束冲突，未进入生图；清空补充后标准模板成功。'}
        (OUT/'evidence/node-record.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
