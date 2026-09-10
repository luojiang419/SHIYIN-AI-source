import asyncio
import sqlite3
import subprocess
from pathlib import Path
from unittest.mock import patch

from starlette.requests import Request
from canvas_core.accounts import AccountStore, AccountIdentity


def test_resource_gate_runtime():
    result = subprocess.run(['node', 'tests/js/canvas_resource_ready.test.cjs'], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def test_session_heartbeat_does_not_block_authentication_on_write_lock(tmp_path):
    store = AccountStore(tmp_path)
    store.initialize()
    token = store.create_session(AccountIdentity('admin', 'jiang', 'admin', ''))
    with store.connect() as connection:
        connection.execute('UPDATE sessions SET last_seen_at=0')
    with store.connect() as writer:
        writer.execute('BEGIN IMMEDIATE')
        try:
            assert store.resolve_session(token).is_admin
        finally:
            writer.rollback()
    assert store.resolve_session(token).is_admin


def test_auth_read_lock_returns_retryable_503_without_authorizing_request():
    import main
    request = Request({'type': 'http', 'method': 'GET', 'path': '/api/canvases', 'headers': []})
    async def forbidden(_):
        raise AssertionError('数据库校验失败不得放行请求')
    with patch.object(main.ACCOUNT_STORE, 'resolve_session', side_effect=sqlite3.OperationalError('database is locked')):
        response = asyncio.run(main.account_authentication_middleware(request, forbidden))
    assert response.status_code == 503
    assert response.headers['retry-after'] == '1'
    assert b'account_database_busy' in response.body
