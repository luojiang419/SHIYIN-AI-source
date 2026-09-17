
import io
from PIL import Image
import numpy as np
from fastapi.testclient import TestClient
from canvas_core import cutout_api as api

def test_preview_and_export_share_edge_controls(monkeypatch):
    image=Image.new('RGB',(80,80),'orange')
    buffer=io.BytesIO();image.save(buffer,'PNG')
    mask=np.zeros((80,80),dtype=np.float32);mask[20:60,20:60]=1
    monkeypatch.setattr(api.engine,'segment',lambda session,points:mask)
    client=TestClient(api.app)
    upload=client.post('/api/images',files={'image':('test.png',buffer.getvalue())}).json()
    request={'session_id':upload['session_id'],'points':[{'x':40,'y':40,'label':1}],'edge_shift':3,'feather':0}
    response=client.post('/api/export/cutout',json=request)
    result=Image.open(io.BytesIO(response.content))
    assert result.size==(80,80)
    assert result.getpixel((18,40))[3]==255
    assert result.getpixel((0,0))[3]==0
    assert client.delete('/api/images/'+upload['session_id']).status_code==200
    assert client.post('/api/segment',json=request).status_code==404


def test_session_is_account_scoped():
    from canvas_core.account_storage import account_scope
    client=TestClient(api.app)
    buffer=io.BytesIO();Image.new('RGB',(8,8)).save(buffer,'PNG')
    with account_scope('cutout-a'):
        upload=client.post('/api/images',files={'image':('test.png',buffer.getvalue())}).json()
    with account_scope('cutout-b'):
        assert client.delete('/api/images/'+upload['session_id']).status_code==404
    with account_scope('cutout-a'):
        assert client.delete('/api/images/'+upload['session_id']).status_code==200
