"""隔离真实 FastAPI 性能服务；只写指定测试目录，不接触安装数据或收费 API。"""
import argparse
import io
import os
import sys
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--source', required=True)
parser.add_argument('--data', required=True)
parser.add_argument('--port', type=int, required=True)
args = parser.parse_args()
source, data = Path(args.source).resolve(), Path(args.data).resolve()
if data.exists() and not (data/'fixture-marker').exists():
    raise SystemExit('拒绝使用已有非 fixture 数据目录')
data.mkdir(parents=True,exist_ok=True)
(data/'fixture-marker').touch()
os.environ['CANVAS_APP_ROOT'] = str(source)
os.environ['CANVAS_DATA_DIR'] = str(data)
sys.path.insert(0,str(source))
import main
from PIL import Image
import uvicorn
main.MEDIA_PREVIEW_DIR = str(data/'cache'/f'benchmark-previews-{time.time_ns()}')
with main.DATABASE.transaction(immediate=True) as connection:
    connection.execute('UPDATE work_items SET created_at=1700000000.25')

if not main.DATABASE.get_canvas('media-benchmark'):
    buffer = io.BytesIO()
    Image.effect_noise((2048,2048),40).convert('RGB').save(buffer,format='JPEG',quality=92)
    raw = buffer.getvalue()
    for i in range(1250):
        target = Path(os.fspath(main.OUTPUT_OUTPUT_DIR))/f'fixture-{i}.jpg'
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(raw)
    main.DATABASE.prepend_history({'id':'fixture-history','type':'online','timestamp':1700000000.25,
        'images':[f'/assets/output/fixture-{i}.jpg' for i in range(1250)]})
    for c in range(13):
        nodes = [{'id':f'image-{i}','type':'image','x':(i%25)*300,'y':(i//25)*230,
            'w':260,'h':180,'url':f'/assets/output/fixture-{(i+c*31)%1250}.jpg','natural_w':2048,'natural_h':2048}
            for i in range(450 if c==0 else 90)]
        main.DATABASE.save_canvas({'id':'media-benchmark' if c==0 else f'fixture-{c}',
            'title':'媒体架构测试','kind':'classic','project':'default','nodes':nodes,
            'viewport':{'x':30,'y':30,'scale':.6},'connections':[]})
print('fixture ready',flush=True)
uvicorn.run(main.app, host='127.0.0.1',port=args.port,lifespan='off',log_level='warning')
