import concurrent.futures
import socket
import struct
import time

import pytest

from distribution.service import Center
from distribution.traffic import Traffic
from tests.test_distribution_service import get, server, snapshot


def settled(center):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        state = center.traffic.snapshot()
        if state['active_count'] == 0:
            return state
        time.sleep(.02)
    raise AssertionError('下载请求未清理')


def test_concurrent_ranges_count_only_response_bytes_and_preserve_version(server, tmp_path):
    center, url = server
    content = b'x' * 8192
    center.import_release(snapshot(tmp_path/'release', content), 'hot')
    with get(url+'/v1/catalog', {'X-Shiyin-Version': '1.0.446'}) as response:
        response.read()
    import hashlib
    sha = hashlib.sha256(content).hexdigest()
    def download(_):
        with get(url+'/v1/blobs/'+sha, {'Range': 'bytes=100-1099'}) as response:
            assert response.read() == content[100:1100]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(download, range(16)))
    state = settled(center)
    assert state['today_bytes'] == 16000
    assert state['clients']['127.0.0.1']['today_bytes'] == 16000
    assert len(state['recent']) == 16
    assert all(t['state'] == 'completed' and t['offset'] == 100 for t in state['recent'])
    assert 'app/web/index.html' in state['recent'][0]['resource']
    assert center.status()['clients'][0]['version'] == '1.0.446'
    restored = Center(center.data)
    assert restored.traffic.snapshot()['today_bytes'] == 16000
    assert restored.traffic.snapshot()['active_count'] == 0


def test_speed_idle_daily_rollover_and_restart(tmp_path):
    center = Center(tmp_path/'data')
    stamp = [time.mktime((2026, 9, 14, 23, 59, 58, 0, 0, -1))]
    traffic = Traffic(center.db, clock=lambda: stamp[0])
    one = traffic.begin('a', 'model', 1200)
    two = traffic.begin('b', 'update', 600)
    traffic.advance(one, 900)
    traffic.advance(two, 600)
    stamp[0] += 1
    state = traffic.snapshot()
    assert state['speed_bps'] == 500
    assert state['peak_bps'] == 1500
    assert state['active_count'] == 2 and state['downloading_clients'] == 2
    stamp[0] += 1
    traffic.advance(one, 300)
    traffic.finish(one, True)
    traffic.finish(two, True)
    state = traffic.snapshot()
    assert state['day'] == '2026-09-15' and state['today_bytes'] == 300
    stamp[0] += 5
    assert traffic.snapshot()['speed_bps'] == 0
    restored = Traffic(center.db, clock=lambda: stamp[0])
    assert restored.snapshot()['today_bytes'] == 300
    with center.db() as db:
        assert db.execute("SELECT bytes FROM traffic_daily WHERE day='2026-09-14' AND ip='*'").fetchone()[0] == 1500


def test_socket_disconnect_cleans_active_and_does_not_count_whole_file(server):
    center, url = server
    path = center.data/'bootstrap'/'SHIYIN-Hot-Update.exe'
    path.parent.mkdir()
    with path.open('wb') as handle:
        handle.truncate(64 * 1024 * 1024)
    port = int(url.rsplit(':', 1)[1])
    sock = socket.create_connection(('127.0.0.1', port))
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    sock.sendall(b'GET /SHIYIN-Hot-Update.exe HTTP/1.1\r\nHost: localhost\r\n\r\n')
    assert sock.recv(1024)
    deadline = time.monotonic()+3
    while not center.traffic.snapshot()['active_count'] and time.monotonic()<deadline:
        time.sleep(.01)
    assert center.traffic.snapshot()['active_count'] == 1
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('hh', 1, 0) if __import__('os').name == 'nt' else struct.pack('ii', 1, 0))
    sock.close()
    state = settled(center)
    assert state['recent'][0]['state'] == 'interrupted'
    assert state['today_bytes'] == state['recent'][0]['sent'] < path.stat().st_size


def test_invalid_range_does_not_count_and_monitor_is_admin_only(server):
    center, url = server
    path = center.data/'bootstrap'/'SHIYIN-Hot-Update.exe'
    path.parent.mkdir();path.write_bytes(b'abc')
    import urllib.error
    with pytest.raises(urllib.error.HTTPError):
        get(url+'/SHIYIN-Hot-Update.exe', {'Range': 'bytes=99-'})
    with pytest.raises(urllib.error.HTTPError):
        get(url+'/api/status')
    assert center.traffic.snapshot()['today_bytes'] == 0


def test_storage_retry_keeps_download_counts(tmp_path):
    center = Center(tmp_path/'data')
    traffic = center.traffic
    original = traffic.db
    import sqlite3
    def failed():
        raise sqlite3.OperationalError('locked')
    key = traffic.begin('ip', 'file', 3)
    traffic.db = failed
    traffic.advance(key, 3)
    traffic.finish(key, True)
    assert traffic.persistence_error
    traffic.db = original
    assert traffic.snapshot()['today_bytes'] == 3
    assert traffic.snapshot()['today_bytes'] == 3
