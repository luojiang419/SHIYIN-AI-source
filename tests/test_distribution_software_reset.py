import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

spec = importlib.util.spec_from_file_location('software_reset', Path(__file__).parents[1]/'tools/reset-distribution-software.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_reset_preserves_models_shared_blobs_and_client_records(tmp_path):
    data = tmp_path/'data';data.mkdir();(data/'blobs').mkdir();(data/'bootstrap').mkdir()
    old, shared, model = 'a'*64, 'b'*64, 'c'*64
    for name in (old, shared, model): (data/'blobs'/name).write_bytes(name.encode())
    (data/'bootstrap/SHIYIN-Hot-Update.exe').write_bytes(b'legacy')
    (data/'fixed-models.json').write_bytes(b'{"fixed":true}')
    with sqlite3.connect(data/'index.db') as db:
        db.execute('CREATE TABLE releases(id TEXT,kind TEXT,manifest TEXT)')
        db.execute('CREATE TABLE clients(id TEXT)');db.execute("INSERT INTO clients VALUES('user')")
        for rid, kind, refs in [('old','hot',[old,shared]), ('fixed','person-depth',[shared,model])]:
            envelope=json.dumps({'payload':json.dumps({'files':[{'sha256':sha} for sha in refs]})})
            db.execute('INSERT INTO releases VALUES(?,?,?)',(rid,kind,envelope))
    backup=tmp_path/'before.db'
    preview=module.reset(data,backup)
    assert preview['delete_files']==2 and not backup.exists()
    assert (data/'blobs'/old).exists()
    report=module.reset(data,backup,True)
    assert report['shared_blobs_preserved']==1
    assert not (data/'blobs'/old).exists() and not (data/'bootstrap/SHIYIN-Hot-Update.exe').exists()
    assert (data/'blobs'/shared).exists() and (data/'blobs'/model).exists()
    assert (data/'fixed-models.json').read_bytes()==b'{"fixed":true}'
    with sqlite3.connect(data/'index.db') as db:
        assert db.execute('SELECT id FROM releases').fetchall()==[('fixed',)]
        assert db.execute('SELECT id FROM clients').fetchall()==[('user',)]
    with sqlite3.connect(backup) as db:
        assert db.execute('SELECT count(*) FROM releases').fetchone()[0]==2
    with pytest.raises(ValueError,match='备份文件已存在'):module.reset(data,backup,True)
