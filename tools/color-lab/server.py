"""本机面料验证台，独立于安装版；python tools/color-lab/server.py。"""
import sys, json, base64, io, os, uuid
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from canvas_core.color_fidelity import crop_rgb, smart_color_match_preview, apply_lab_controls, inspect_color_fidelity
DATA=Path(os.environ.get('LOCALAPPDATA', str(Path.home())))/'SHIYIN-AI'/'color-lab'
DATA.mkdir(parents=True,exist_ok=True)
class Handler(BaseHTTPRequestHandler):
    def send(self,obj,status=200):
        body=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.end_headers();self.wfile.write(body)
    def do_GET(self):
        if self.path=='/profiles':
            self.send(json.loads((DATA/'profiles.json').read_text('utf-8')) if (DATA/'profiles.json').exists() else []);return
        if self.path!='/': self.send({},404);return
        self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(Path(__file__).with_name('index.html').read_bytes())
    def do_POST(self):
        try:
            n=int(self.headers.get('Content-Length',0))
            if n>80_000_000: raise ValueError('图片请求过大')
            p=json.loads(self.rfile.read(n))
            if self.path=='/profiles':
                name=str(p['name']).strip()
                if not name: raise ValueError('请填写面料名称')
                path=DATA/'profiles.json'; records=json.loads(path.read_text('utf-8')) if path.exists() else []
                p['status']='参数草稿，需跨图验证';records.append(p)
                tmp=DATA/'profiles.tmp';tmp.write_text(json.dumps(records,ensure_ascii=False,indent=2),'utf-8');tmp.replace(path);self.send(records);return
            if self.path!='/fit': self.send({},404);return
            def load(key):
                return np.array(Image.open(io.BytesIO(base64.b64decode(p[key].split(',')[1]))).convert('RGB'))
            ref,src=load('reference'),load('source'); original=src.copy(); c=p['controls']
            refcrop=crop_rgb(ref,p['reference_roi']); srccrop=crop_rgb(src,p['source_roi'])
            # 原型由用户画出的应用矩形限制范围；不宣称自动分割已经可靠。
            x,y,w,h=p['apply_roi']; target=crop_rgb(src,(x,y,w,h))
            fitted=target if c['model']=='manual' else smart_color_match_preview(refcrop,srccrop,c['strength'],c['model'],target)
            fitted=apply_lab_controls(fitted,c['lightness'],c['contrast'],c['chroma'],c['a_shift'],c['b_shift'])
            src[y:y+h,x:x+w]=fitted
            out=DATA/('preview_'+uuid.uuid4().hex+'.png');Image.fromarray(src).save(out)
            buf=io.BytesIO();Image.fromarray(src).save(buf,format='PNG')
            self.send({'image':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode(),'path':str(out),'before':inspect_color_fidelity(refcrop,srccrop).as_dict(),'after':inspect_color_fidelity(refcrop,crop_rgb(src,p['source_roi'])).as_dict()})
        except Exception as exc:self.send({'error':str(exc)},400)
if __name__=='__main__':
    print('面料验证台 http://127.0.0.1:13229',flush=True)
    HTTPServer(('127.0.0.1',13229),Handler).serve_forever()
