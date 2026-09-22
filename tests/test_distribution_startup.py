import json
import urllib.error
import urllib.request
import threading
from unittest.mock import Mock

import pytest

from distribution import launcher, startup
from distribution.service import Center, ExclusiveHTTPServer


def test_startup_detects_exited_child_without_waiting():
    request = Mock(side_effect=ConnectionRefusedError('refused'))
    process = Mock()
    process.poll.return_value = 7
    with pytest.raises(RuntimeError, match='代码 7.*service-startup.log'):
        launcher.wait_for_service(request, process)


def test_frozen_service_gets_fresh_bootloader_environment(monkeypatch):
    monkeypatch.setattr(launcher.sys, 'frozen', True, raising=False)
    spawn = Mock()
    monkeypatch.setattr(launcher.subprocess, 'Popen', spawn)
    launcher.launch_service()
    assert spawn.call_args.kwargs['env']['PYINSTALLER_RESET_ENVIRONMENT'] == '1'
    assert spawn.call_args.args[0] == [launcher.sys.executable, '--service']


def test_startup_accepts_legacy_status():
    request = Mock(side_effect=[urllib.error.HTTPError('url', 404, '', {}, None), {}])
    launcher.wait_for_service(request, Mock())
    assert [call.args[0] for call in request.call_args_list] == ['health', 'status']


def test_startup_does_not_treat_auth_failure_as_ready():
    process = Mock()
    process.poll.return_value = 1
    with pytest.raises(RuntimeError):
        launcher.wait_for_service(Mock(side_effect=urllib.error.HTTPError('url', 403, '', {}, None)), process)


def test_startup_failure_is_saved_before_reraising(tmp_path, monkeypatch):
    monkeypatch.setenv('SHIYIN_DISTRIBUTION_DATA', str(tmp_path))
    monkeypatch.setattr('distribution.service.main', Mock(side_effect=OSError('startup sentinel')))
    with pytest.raises(OSError, match='startup sentinel'):
        startup.run_service()
    assert 'OSError: startup sentinel' in (tmp_path / 'service-startup.log').read_text('utf-8')


def test_health_is_lightweight_authenticated_and_icon_is_served(tmp_path):
    center = Center(tmp_path)
    center.status = Mock(side_effect=AssertionError('health must not enumerate releases'))
    server = ExclusiveHTTPServer(('127.0.0.1', 0), center.handler(True))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url = f'http://127.0.0.1:{server.server_port}'
    try:
        with pytest.raises(OSError):
            other = ExclusiveHTTPServer(server.server_address, center.handler(True))
            other.server_close()
        with pytest.raises(urllib.error.HTTPError) as error:
            opener.open(url + '/api/health')
        assert error.value.code == 403
        req = urllib.request.Request(url + '/api/health', headers={'Authorization': 'Bearer ' + center.token})
        with opener.open(req) as response:
            assert json.load(response) == {'ok': True}
        with opener.open(url + '/distribution.png') as response:
            assert response.read(8) == b'\x89PNG\r\n\x1a\n'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
