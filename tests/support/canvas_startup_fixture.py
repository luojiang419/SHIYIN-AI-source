"""隔离画布浏览器回归服务。仅服务仓库 static 和内存 fixture，不访问用户数据或外部 API。"""
import argparse
import base64
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote
import mimetypes
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from canvas_core.pose_replicate_prompts import pose_replicate_template_catalog, POSE_REPLICATE_TEMPLATE_ID
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jEOsAAAAASUVORK5CYII=')
STATE = {'requests': [], 'saves': [], 'projects': {}}
CONFIG = {'image_models':['private-image'], 'video_models':['private-video'], 'chat_models':['private-chat'],
    'api_providers':[
        {'id':'custom','name':'Fixture Custom','enabled':True,'image_models':['private-image'],'video_models':['private-video'],'chat_models':['private-chat']},
        {'id':'runninghub','name':'RunningHub','enabled':True,'rh_workflows':[{'workflowId':'fixture-workflow','title':'Fixture workflow'}]},
        {'id':'minimax-h3','name':'MiniMax H3','enabled':True,'video_models':['MiniMax H3']}
    ]}

def project(canvas_id):
    return {'id':canvas_id,'title':'启动架构隔离回归','kind':'classic','project':'default', 'updated_at':1,
        'viewport':{'x':40,'y':40,'scale':0.5},'connections':[], 'nodes':[
            {'id':'prompt','type':'prompt','x':0,'y':0,'text':'保留原始提示词','w':350,'h':240},
            {'id':'generator','type':'generator','x':440,'y':0,'apiProvider':'custom','model':'private-image','ratio':'wide','resolution':'2k','count':1},
            {'id':'video','type':'video','x':960,'y':0,'apiProvider':'custom','model':'private-video','count':1},
            {'id':'image','type':'image','x':0,'y':700,'url':'/fixture.png','name':'fixture.png','width':1,'height':1},
            {'id':'depth','type':'depthMap','x':440,'y':700},
            {'id':'pose','type':'poseReplicate','x':960,'y':700},
            {'id':'rh','type':'rh','x':1480,'y':0,'workflowId':'fixture-workflow','rhKind':'workflow'},
            {'id':'h3','type':'video','x':1480,'y':700,'apiProvider':'minimax-h3','model':'MiniMax H3'},
        ]}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def send(self, value, status=200, mime='application/json'):
        body=value if isinstance(value, bytes) else json.dumps(value,ensure_ascii=False).encode()
        try:
            self.send_response(status); self.send_header('Content-Type',mime); self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError): pass
    def do_GET(self):
        path=unquote(urlsplit(self.path).path)
        STATE['requests'].append({'path':path,'at':time.monotonic()})
        if path.startswith('/static/'):
            file=(ROOT/path.lstrip('/')).resolve()
            if not file.is_relative_to(ROOT/'static') or not file.is_file(): return self.send({},404)
            body=file.read_bytes()
            if file.name=='canvas.js':
                body=body.replace(b'function render(){', b'function render(){ console.log("[fixture-render]", nodes.length, new Error().stack);')
            return self.send(body,mime=mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
        if path=='/fixture.png': return self.send(PNG,mime='image/png')
        if path=='/fixture-state': return self.send(STATE)
        if path=='/api/runtime/config':
            time.sleep(self.server.config_delay)
            if self.server.fail_config_once:
                self.server.fail_config_once=False
                return self.send({'detail':'fixture transient failure'},503)
            return self.send(CONFIG)
        if path=='/api/canvas/pose-replicate-templates':
            return self.send({'template_id':POSE_REPLICATE_TEMPLATE_ID,'items':pose_replicate_template_catalog()})
        if path.startswith('/api/canvases/'):
            canvas_id=path.split('/')[3]
            if path.endswith('/meta'): return self.send({'id':canvas_id,'updated_at':1})
            return self.send({'canvas':STATE['projects'].get(canvas_id) or project(canvas_id)})
        if path.startswith('/api/runninghub/workflows/'):
            time.sleep(self.server.capability_delay)
            return self.send({'workflow':{'workflowId':'fixture-workflow','title':'Fixture workflow','fields':[]}})
        if path=='/api/minimax-h3/status':
            time.sleep(self.server.capability_delay)
            return self.send({'generation_enabled':True,'resolutions':[],'defaults':{}})
        if path=='/api/canvas-assets/check': return self.send({'missing':[]})
        if path.startswith('/api/'): return self.send({'tasks':[],'items':[],'canvases':[],'bindings':{},'libraries':[]})
        return self.send({},404)
    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length',0)))
        if self.path.endswith('/touch'): return self.send({'canvas':{'id':self.path.split('/')[3],'updated_at':1}})
        if self.path.endswith('/check'): return self.send({'missing':[]})
        return self.send({'detail':'Fixture server: generation is disabled'},503)
    def do_PUT(self):
        payload=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
        STATE['saves'].append(payload)
        canvas_id = self.path.split('/')[3]
        saved = {**project(canvas_id), **payload, 'id':canvas_id, 'updated_at':1, 'revision':1}
        STATE['projects'][canvas_id] = saved
        return self.send({'canvas':saved})

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=3011)
    parser.add_argument('--config-delay',type=float,default=2)
    parser.add_argument('--capability-delay',type=float,default=4)
    parser.add_argument('--fail-config-once',action='store_true')
    args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    server.config_delay=args.config_delay
    server.capability_delay=args.capability_delay
    server.fail_config_once=args.fail_config_once
    print(f'canvas fixture on http://127.0.0.1:{args.port}',flush=True)
    server.serve_forever()
