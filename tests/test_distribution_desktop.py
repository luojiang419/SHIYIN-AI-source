import json
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

import pytest
from distribution.service import Center
from distribution import desktop_settings


def test_theme_selection_obeys_system_without_changing_it(monkeypatch):
    monkeypatch.setattr(desktop_settings, 'system_dark', lambda: True)
    assert desktop_settings.resolve_dark('system')
    assert not desktop_settings.resolve_dark('light')
    monkeypatch.setattr(desktop_settings, 'system_dark', lambda: False)
    assert not desktop_settings.resolve_dark('system')
    assert desktop_settings.resolve_dark('dark')


def test_preferences_persist_and_startup_is_optional(tmp_path, monkeypatch):
    changes = []
    monkeypatch.setattr('distribution.service.set_startup', lambda enabled: changes.append(enabled))
    center = Center(tmp_path)
    server = ThreadingHTTPServer(('127.0.0.1', 0), center.handler(True))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def post(path, value):
        req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/api/{path}',
            data=json.dumps(value).encode(), headers={'Authorization': 'Bearer ' + center.token, 'Content-Type': 'application/json'})
        with opener.open(req) as response:
            return json.load(response)

    try:
        before = dict(center.config)
        dark = post('settings', {'theme': 'dark'})
        assert dark['settings']['theme'] == 'dark' and not changes
        assert dark['settings']['auto_start'] == before['auto_start']
        off = post('settings', {'launch_at_login': False, 'background_on_close': False, 'start_hidden': False})
        assert changes == [False]
        assert off['settings']['background_on_close'] is False
        restored = Center(tmp_path)
        assert restored.config['theme'] == 'dark'
        assert restored.config['launch_at_login'] is False
        assert restored.config['start_hidden'] is False
        post('settings', {'launch_at_login': True})
        assert changes == [False, True]
        with pytest.raises(urllib.error.HTTPError): post('settings', {'theme': 'invalid'})
        with pytest.raises(urllib.error.HTTPError): post('settings', {'launch_at_login': 'false'})
        first = post('desktop-action', {'action': 'background'})['desktop_action']
        second = post('desktop-action', {'action': 'show'})['desktop_action']
        assert second['sequence'] > first['sequence']
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
