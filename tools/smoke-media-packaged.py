"""验证冻结后端媒体链路，使用独立数据目录和端口，不连接生成 API。"""
import argparse
import io
import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import requests
from PIL import Image
from PyInstaller.archive.readers import CArchiveReader


def run(stage, port, output):
    stage = Path(stage).resolve()
    backend = stage/'app/backend/canvas-backend/canvas-backend.exe'
    archive = CArchiveReader(str(backend)).open_embedded_archive('PYZ.pyz')
    required = ['canvas_core.media_integrity','canvas_core.works_snapshot','canvas_core.database']
    assert all(module in archive.toc for module in required), '冻结媒体模块缺失'
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',port))
    output = Path(output).resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='media-packaged-smoke-',dir=output.parent))
    environment = dict(os.environ)
    environment['CANVAS_DWPOSE_AUTO_DOWNLOAD'] = '0'
    base = f'http://127.0.0.1:{port}'
    started = time.monotonic()
    with (root/'stdout.log').open('wb') as stdout, (root/'stderr.log').open('wb') as stderr:
        process = subprocess.Popen([str(backend),'--host','127.0.0.1','--port',str(port),
            '--data-dir',str(root/'data'),'--app-root',str(stage/'app'),
            '--portable-root',str(stage),'--runtime-mode','desktop'],
            cwd=stage,env=environment,stdout=stdout,stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:
            for _ in range(200):
                assert process.poll() is None, '冻结后端提前退出'
                try:
                    health=requests.get(base+'/api/health',timeout=1)
                    if health.ok and health.json().get('status')=='ok': break
                except requests.RequestException: pass
                time.sleep(.1)
            else: raise RuntimeError('冻结后端启动超时')
            startup_ms=round((time.monotonic()-started)*1000)
            scopes=[]
            urls=[]
            for index,color in enumerate(['red','blue']):
                session=requests.Session()
                response=session.post(base+'/api/account/register',json={'account':f'Smoke{index}','password':'fixture'},timeout=10)
                response.raise_for_status()
                buffer=io.BytesIO()
                Image.new('RGB',(128,80),color).save(buffer,format='PNG')
                response=session.post(base+'/api/ai/upload',files={'files':('sample.png',buffer.getvalue(),'image/png')},timeout=10)
                response.raise_for_status()
                url=response.json()['files'][0]['url']
                canvas=session.post(base+'/api/canvases',json={'title':'媒体安装验证'},timeout=10).json()['canvas']
                response=session.put(base+f'/api/canvases/{canvas["id"]}',json={'title':'媒体安装验证','nodes':[
                    {'id':'image','type':'image','url':url,'x':0,'y':0},
                    {'id':'research','type':'lookbook','research':[{'url':'https://example.test/campaign.html'}]}],
                    'connections':[]},timeout=10)
                response.raise_for_status()
                works=session.get(base+'/api/works',timeout=10).json()
                assert works['total']==1 and works['works'][0]['name'].endswith('.png'), works
                preview=session.get(base+works['works'][0]['preview_url'],timeout=10)
                preview.raise_for_status()
                assert preview.headers['content-type'].startswith('image/')
                pixel=Image.open(io.BytesIO(preview.content)).convert('RGB').getpixel((0,0))
                assert pixel[index*2]>200
                scopes.append(preview.headers['x-media-account'])
                conditional=session.get(base+works['works'][0]['preview_url'],headers={'If-None-Match':preview.headers['etag']},timeout=10)
                assert conditional.status_code==304
                if urls:
                    assert session.get(base+urls[0],timeout=10).status_code==404, '账号越界读取'
                urls.append(url)
                rejected=session.post(base+'/api/ai/upload',files={'files':('bad.png',b'<html>not an image</html>','image/png')},timeout=10)
                assert rejected.status_code==400
                session.close()
            assert scopes[0]!=scopes[1]
            result={'health':'ok','startup_ms':startup_ms,'frozen_modules':required,
                'accounts':2,'upload_canvas_works_preview':True,'html_not_indexed':True,
                'invalid_image_rejected':True,'account_isolation':True,'conditional_304':True,
                'data_root':str(root/'data')}
        finally:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    result['backend_stopped']=process.poll() is not None
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--stage',required=True)
    parser.add_argument('--port',type=int,default=3128)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    run(args.stage,args.port,args.output)
