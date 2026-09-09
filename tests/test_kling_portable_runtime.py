import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from canvas_core import kling_runtime as runtime
from canvas_core import kling_cli as cli
from canvas_core.kling_login import KlingLoginManager, authorization_url


URL = "https://klingai.com/oauth/authorize?client_id=test&state=test&redirect_uri=http%3A%2F%2F127.0.0.1%3A9999%2Fcallback&code_challenge=test"


@pytest.fixture
def isolated_paths(tmp_path):
    paths = SimpleNamespace(data_root=tmp_path / "data", app_root=tmp_path / "app")
    with patch.object(runtime, "APP_PATHS", paths):
        yield paths


def create_runtime(root, region="china"):
    entry = runtime.cli_entry(root, region)
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text("// fixture", encoding="utf-8")
    node = runtime.node_entry(root)
    node.parent.mkdir(parents=True, exist_ok=True)
    node.write_bytes(b"fixture")
    return node, entry


def test_node_distributions_cover_windows_and_both_macos_architectures():
    windows = runtime.node_distribution("Windows", "AMD64")
    apple = runtime.node_distribution("Darwin", "arm64")
    intel = runtime.node_distribution("Darwin", "x86_64")
    assert windows["executable"] == "node.exe" and windows["archive"].endswith(".zip")
    assert apple["key"] == "darwin-arm64" and apple["executable"] == "bin/node"
    assert intel["key"] == "darwin-x64" and intel["archive"].endswith(".tar.gz")
    assert runtime.node_distribution("Linux", "x86_64") is None
    assert runtime.NODE_EXECUTABLE_MAX_BYTES > 112_937_728


@pytest.mark.skipif(os.name != "nt", reason="Windows x64 bundled Node")
def test_bundled_runtime_connects_without_node_npm_or_kling_on_path(isolated_paths):
    node, entry = create_runtime(runtime.bundled_root())
    def run(executable, arguments, **kwargs):
        assert executable == str(node)
        assert arguments in (["--version"], [str(entry), "--version"])
        return subprocess.CompletedProcess([], 0, b"v22.23.2" if arguments == ["--version"] else b"kling-cli 0.1.3", b"")
    with patch.object(cli.shutil, "which", return_value=None), patch.object(cli, "default_kling_process_runner", side_effect=run), patch.object(runtime, "_download") as download:
        env = cli.install_kling_cli("china")
        assert env.is_ready and env.executable == str(node)
        assert env.argument_prefix == [str(entry)] and not env.use_shell
        assert cli.resolve_kling_cli().is_ready
        download.assert_not_called()
    assert runtime.selected_region() == "china"


@pytest.mark.skipif(os.name != "nt", reason="Windows x64 bundled Node")
def test_region_switch_uses_separate_package_and_persists(isolated_paths):
    create_runtime(runtime.bundled_root(), "china")
    _, global_entry = create_runtime(runtime.bundled_root(), "global")
    with patch.object(cli, "_run_version", return_value="v22.23.2"), patch.object(cli, "_run_command_version", return_value="0.1.3"):
        cli.install_kling_cli("china")
        cli.install_kling_cli("global")
        assert cli.resolve_kling_cli().entrypoint_path == str(global_entry)
    assert runtime.selected_region() == "global"


def test_broken_runtime_is_repaired_before_activation(isolated_paths):
    ready = cli.KlingCliEnvironment(node_path="node.exe", entrypoint_path="cli.js", version="0.1.3")
    with patch.object(runtime, "ensure_runtime", return_value=("node.exe", "cli.js")) as ensure, patch.object(cli, "_managed_environment", side_effect=[cli.KlingCliEnvironment(error_message="broken"), ready]):
        assert cli.install_kling_cli("china").is_ready
        assert ensure.call_args_list[-1].kwargs == {"repair":True}


@pytest.mark.skipif(os.name != "nt", reason="Windows x64 bundled Node")
def test_repair_cache_takes_precedence_over_broken_bundle(isolated_paths):
    create_runtime(runtime.bundled_root())
    node, entry = create_runtime(runtime.runtime_root())
    assert runtime.find_runtime("china") == (str(node), str(entry))


def test_failed_preparation_preserves_selected_region(isolated_paths):
    runtime.select_region("china")
    with patch.object(runtime, "ensure_runtime", side_effect=OSError("offline")), pytest.raises(cli.KlingCliError, match="offline"):
        cli.install_kling_cli("global")
    assert runtime.selected_region() == "china"


def test_global_cli_no_longer_requires_npm(isolated_paths, tmp_path):
    wrapper = tmp_path / "kling.cmd"
    wrapper.write_text("", encoding="utf-8")
    with patch.object(cli.shutil, "which", side_effect=lambda name: {"node":"node.exe", "kling.cmd":str(wrapper), "kling":str(wrapper)}.get(name)), patch.object(cli, "_windows_program_file", return_value=""), patch.object(cli, "_find_kling_entrypoint", return_value="cli.js"), patch.object(cli, "_run_version", return_value="v22.23.2"), patch.object(cli, "_run_command_version", return_value="0.1.3"):
        assert cli.resolve_kling_cli().is_ready


def test_download_rejects_tampered_archive(tmp_path):
    with patch.object(runtime.urllib.request, "urlopen", return_value=io.BytesIO(b"tampered")), pytest.raises(RuntimeError, match="校验失败"):
        runtime._download("https://example.test/component", tmp_path / "test.tgz", "sha256", hashlib.sha256(b"expected").digest())


def tar_bytes(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, content in entries.items():
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    return output.getvalue()


def test_download_prepare_reuses_cache_and_repairs_missing_entry(tmp_path):
    content = tar_bytes({"package/package.json": json.dumps({"version":runtime.CLI_VERSION}).encode(), "package/dist/cli.js":b"// fixture"})
    integrity = base64.b64encode(hashlib.sha512(content).digest()).decode()
    with patch.dict(runtime.CLI_INTEGRITY, {"china":("cli-cn", integrity)}), patch.object(runtime.urllib.request, "urlopen", side_effect=lambda *a, **kw: io.BytesIO(content)) as download:
        runtime.prepare_runtime(tmp_path, ("china",), include_node=False)
        runtime.prepare_runtime(tmp_path, ("china",), include_node=False)
        assert download.call_count == 1
        runtime.cli_entry(tmp_path, "china").unlink()
        runtime.prepare_runtime(tmp_path, ("china",), include_node=False)
        assert download.call_count == 2
        assert runtime.cli_entry(tmp_path, "china").is_file()
    assert not list(tmp_path.glob(".prepare-*"))


@pytest.mark.parametrize("name", ["../escape", "package/../../escape", "package/C:/escape", "package\\..\\escape"])
def test_archive_cannot_escape_destination(tmp_path, name):
    archive = tmp_path / "unsafe.tgz"
    archive.write_bytes(tar_bytes({name:b"bad"}))
    with pytest.raises(RuntimeError, match="非法路径"):
        runtime._unpack_cli(archive, tmp_path / "result")


def test_failed_download_does_not_publish_partial_package(tmp_path):
    with patch.object(runtime, "_download", side_effect=OSError("network")), pytest.raises(OSError):
        runtime.prepare_runtime(tmp_path, ("china",), include_node=False)
    assert not runtime.cli_entry(tmp_path, "china").exists()
    assert not list(tmp_path.glob(".prepare-*"))


def test_auth_url_allowlist_rejects_unrelated_links():
    assert authorization_url("[kling] Opening browser for login: " + URL) == URL
    assert not authorization_url(URL.replace("klingai.com", "klingai.com.attacker.test"))
    assert not authorization_url("https://klingai.com/help")
    assert not authorization_url("javascript:alert(1)")


def test_manual_browser_open_uses_only_current_official_url():
    from canvas_core import kling_login
    manager = KlingLoginManager()
    with pytest.raises(RuntimeError, match="失效"):
        manager.open_browser()
    manager.state = {"status":"waiting", "authorization_url":URL, "error":""}
    with patch.object(kling_login.os, "name", "nt"), patch.object(kling_login.os, "startfile", create=True) as opener:
        manager.open_browser()
        opener.assert_called_once_with(URL)
        manager.state["authorization_url"] = "https://example.test/"
        with pytest.raises(RuntimeError, match="失效"):
            manager.open_browser()
        assert opener.call_count == 1


def wait_status(manager, states, seconds=5):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        state = manager.snapshot()
        if state["status"] in states:
            return state
        time.sleep(0.02)
    raise AssertionError(manager.snapshot())


def test_login_captures_url_reuses_running_process_and_reports_success():
    manager = KlingLoginManager(timeout=5)
    code = f"import time; print({URL!r}, flush=True); time.sleep(0.5)"
    first = manager.start([sys.executable, "-u", "-c", code])
    assert manager.start(["must-not-run"])["pid"] == first["pid"]
    state = wait_status(manager, {"waiting"})
    assert state["authorization_url"] == URL
    assert wait_status(manager, {"succeeded"})["authorization_url"] == ""


def test_login_failure_is_visible_without_leaking_output():
    manager = KlingLoginManager(timeout=5)
    manager.start([sys.executable, "-u", "-c", "import sys; print('fetch failed ACCESS_TOKEN=secret'); sys.exit(1)"])
    state = wait_status(manager, {"failed"})
    assert "网络" in state["error"]
    assert "secret" not in json.dumps(state)


def test_browser_failure_keeps_manual_authorization_link():
    manager = KlingLoginManager(timeout=5)
    manager.start([sys.executable, "-u", "-c", f"import time; print('Could not open browser automatically.'); print({URL!r}, flush=True); time.sleep(0.5)"])
    state = wait_status(manager, {"waiting"})
    assert state["authorization_url"] == URL and "未自动打开" in state["error"]
    wait_status(manager, {"succeeded"})


def test_login_timeout_kills_child_and_allows_retry():
    manager = KlingLoginManager(timeout=0.15)
    manager.start([sys.executable, "-c", "import time; time.sleep(10)"])
    assert "超时" in wait_status(manager, {"failed"})["error"]
    manager.process.wait(timeout=2)
    manager.start([sys.executable, "-c", "pass"])
    assert wait_status(manager, {"succeeded"})["error"] == ""


def test_service_wraps_launch_and_network_timeout():
    service = cli.KlingCliService(cli.KlingCliEnvironment(kling_path="fixture"))
    for exception in (OSError("missing"), subprocess.TimeoutExpired("fixture", 1)):
        with patch.object(service, "runner", side_effect=exception), pytest.raises(cli.KlingCliError):
            service.capabilities()


def test_login_status_api_forbids_remote_access():
    import asyncio
    import main
    from canvas_core.accounts import AccountIdentity
    from fastapi import HTTPException
    from tests.test_kling_remote_web_access import request_for
    for role, host in (("user", "192.168.1.9"), ("admin", "192.168.1.9"), ("user", "127.0.0.1")):
        request = request_for(AccountIdentity("test", "test", role, ""), host)
        with pytest.raises(HTTPException) as error:
            asyncio.run(main.kling_cli_login_status(request))
        assert error.value.status_code == 403
    assert "/api/kling-cli/login-status" in main.ADMIN_ONLY_HTTP_PATHS
    assert "/api/kling-cli/login-open" in main.ADMIN_ONLY_HTTP_PATHS


def test_capabilities_distinguish_login_required_from_network_failure():
    import asyncio
    import main
    from canvas_core.accounts import AccountIdentity
    from tests.test_kling_remote_web_access import request_for
    request = request_for(AccountIdentity("admin", "test", "admin", ""), "127.0.0.1")
    environment = cli.KlingCliEnvironment(kling_path="fixture")
    for message, expected in (("No login state found. Run: kling login", True), ("fetch failed", False)):
        with patch.object(main, "resolve_kling_cli", return_value=environment), patch.object(cli.KlingCliService, "capabilities", side_effect=cli.KlingCliError(message)):
            result = asyncio.run(main.kling_cli_capabilities(request))
        assert result["login_required"] is expected
