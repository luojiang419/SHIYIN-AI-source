"""真实后端的首次注册、权限隔离和桌面会话恢复。"""
import os
import subprocess
import sys
from pathlib import Path


def test_account_setup_and_desktop_restore(tmp_path):
    code = r'''
from fastapi.testclient import TestClient
import main
from canvas_core.accounts import AccountStore

local = TestClient(main.app, client=('127.0.0.1', 50100))
remote = TestClient(main.app, client=('192.168.1.22', 50101))
assert local.get('/api/account/setup').json()['needs_setup']
assert remote.post('/api/account/register', json={'account':'远端','password':'pw'}).status_code == 403
assert local.post('/api/account/login', json={'account':'jiang','password':'jiang'}).status_code == 401
response = local.post('/api/account/register', json={'account':'我的管理员','password':'自选密码'})
assert response.status_code == 201, response.text
assert response.json()['account']['is_admin']
assert 'Max-Age=34560000' in response.headers['set-cookie']
assert not local.get('/api/account/setup').json()['needs_setup']
assert local.get('/api/providers').status_code == 200
assert local.get('/api/onboarding/save-mode').status_code == 200
assistant = local.get('/api/onboarding/ai-assistant').json()
assert assistant['status'] in ('not_found', 'detected'), assistant
assert not any(provider.get('has_key') for provider in local.get('/api/providers').json()['providers'])
saved_account = local.get('/api/account/me').json()

# 实例重新创建模拟后端重启，Cookie 丢失仍可从本机加密凭据恢复。
main.ACCOUNT_STORE = AccountStore(main.ACCOUNT_STORE.data_root)
main.ACCOUNT_STORE.initialize()
local.cookies.clear()
response = local.get('/api/auth/bootstrap', follow_redirects=False)
assert response.headers['location'] == '/', response.text
assert local.get('/api/account/me').json() == saved_account
assert remote.get('/api/auth/bootstrap', follow_redirects=False).status_code == 403
assert remote.get('/api/account/me').status_code == 401

response = remote.post('/api/account/register', json={'account':'普通用户','password':'普通密码'})
assert response.status_code == 201, response.text
assert not response.json()['account']['is_admin']
for path in ['/api/providers','/api/config','/api/admin/accounts','/api/onboarding/save-mode']:
    assert remote.get(path).status_code == 403, path
assert remote.put('/api/providers', json=[]).status_code == 403
assert remote.get('/api/account/me').json() != saved_account
assert local.post('/api/account/logout').status_code == 200
local.cookies.clear()
assert local.get('/api/auth/bootstrap', follow_redirects=False).headers['location'] == '/login'

# 普通用户也可在桌面持久登录，但恢复后仍没有管理员权限。
assert local.post('/api/account/login', json={'account':'普通用户','password':'普通密码'}).status_code == 200
local.cookies.clear()
assert local.get('/api/auth/bootstrap', follow_redirects=False).headers['location'] == '/'
assert local.get('/api/providers').status_code == 403
user_id = local.get('/api/account/me').json()['account']['account_id']
main.ACCOUNT_STORE.update_account(user_id, password='修改密码')
local.cookies.clear()
assert local.get('/api/auth/bootstrap', follow_redirects=False).headers['location'] == '/login'
assert local.post('/api/account/login', json={'account':'普通用户','password':'修改密码'}).status_code == 200
main.ACCOUNT_STORE.update_account(user_id, disabled=True)
local.cookies.clear()
assert local.get('/api/auth/bootstrap', follow_redirects=False).headers['location'] == '/login'
'''
    clean_environment = {key: value for key, value in os.environ.items()
                         if not key.startswith('API_PROVIDER_') and not key.endswith(('_KEY', '_TOKEN', '_SECRET'))}
    environment = dict(clean_environment, CANVAS_DATA_DIR=str(tmp_path / 'data'), CANVAS_PORTABLE_ROOT=str(tmp_path),
                       CANVAS_RUNTIME_MODE='desktop', CANVAS_PORT='3000')
    result = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).resolve().parents[1], env=environment,
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
