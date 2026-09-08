import asyncio
import json
import subprocess
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from canvas_core.accounts import AccountIdentity
from canvas_core.kling_cli import KlingCliEnvironment, KlingCliError, KlingCliService, parse_kling_account
from tests.test_kling_remote_web_access import request_for


def test_account_uses_official_command_and_whitelists_fields():
    payload = {"ok": True, "body": {"userId": 42, "userName": "测试用户", "availableRemainCredits": 0,
        "membershipTypeDescription": "标准会员", "access_token": "secret", "extra": {"token": "secret"}}}
    calls = []
    def runner(executable, arguments, **kwargs):
        calls.append(arguments)
        return subprocess.CompletedProcess([], 0, json.dumps(payload), "")
    account = KlingCliService(KlingCliEnvironment(kling_path="fixture"), runner=runner).account()
    assert calls == [["account", "--quiet"]]
    assert account == {"user_id": "42", "username": "测试用户", "credits": "0", "membership": "标准会员"}
    assert "secret" not in json.dumps(account)


def test_account_missing_fields_and_nested_values_are_not_invented():
    assert parse_kling_account({"body": {"user": {"user_id": 0}, "availableRemainCredits": {"token": "secret"}}}) == {
        "user_id": "0", "username": None, "credits": None, "membership": None}


@pytest.mark.parametrize("host,role", [("192.168.1.8", "admin"), ("192.168.1.8", "user"), ("127.0.0.1", "user")])
def test_account_api_restricts_account_details(host, role):
    import main
    request = request_for(AccountIdentity("test", "test", role, ""), host)
    with patch.object(main, "resolve_kling_cli") as resolve:
        with pytest.raises(HTTPException) as error:
            asyncio.run(main.kling_cli_account(request))
        assert error.value.status_code == 403
        resolve.assert_not_called()
    assert "/api/kling-cli/account" in main.ADMIN_ONLY_HTTP_PATHS


def test_account_api_and_error_do_not_leak_credentials():
    import main
    from canvas_core.kling_login import LOGIN_MANAGER
    request = request_for(AccountIdentity("admin", "test", "admin", ""), "127.0.0.1")
    with patch.object(LOGIN_MANAGER, "snapshot", return_value={"status": "idle"}), \
         patch.object(main, "resolve_kling_cli", return_value=KlingCliEnvironment(kling_path="fixture")), \
         patch.object(KlingCliService, "account", return_value={"credits": "123"}) as account:
        assert asyncio.run(main.kling_cli_account(request)) == {"account": {"credits": "123"}}
        account.side_effect = KlingCliError("ACCESS_TOKEN=secret")
        with pytest.raises(HTTPException) as error:
            asyncio.run(main.kling_cli_account(request))
        assert error.value.status_code == 502
        assert "secret" not in error.value.detail


def test_account_query_waits_for_authorization():
    import main
    from canvas_core.kling_login import LOGIN_MANAGER
    request = request_for(AccountIdentity("admin", "test", "admin", ""), "127.0.0.1")
    with patch.object(LOGIN_MANAGER, "snapshot", return_value={"status": "waiting"}), \
         patch.object(main, "resolve_kling_cli") as resolve:
        with pytest.raises(HTTPException) as error:
            asyncio.run(main.kling_cli_account(request))
        assert error.value.status_code == 409
        resolve.assert_not_called()


def test_authorized_without_models_does_not_enable_generation():
    import main
    request = request_for(AccountIdentity("admin", "test", "admin", ""), "127.0.0.1")
    with patch.object(main, "resolve_kling_cli", return_value=KlingCliEnvironment(kling_path="fixture")), \
         patch.object(KlingCliService, "capabilities", return_value={"text_to_video": [], "image_to_video": []}):
        result = asyncio.run(main.kling_cli_capabilities(request))
    assert result["authenticated"] is True
    assert result["generation_enabled"] is False
    assert "模型" in result["error"]
