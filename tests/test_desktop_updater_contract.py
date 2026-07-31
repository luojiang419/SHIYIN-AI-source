import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
UPDATER = ROOT / "src-tauri" / "src" / "updater.rs"
BUILD_RS = ROOT / "src-tauri" / "build.rs"
CAPABILITY = ROOT / "src-tauri" / "capabilities" / "desktop-update.json"
DESKTOP_UPDATER = ROOT / "static" / "js" / "desktop-updater.js"
INDEX = ROOT / "static" / "index.html"
APP_SETTINGS = ROOT / "static" / "app-settings.html"
INSTALLER_BUILD_SCRIPT = ROOT / "tools" / "build-installer.ps1"
INSTALLER_VERIFY_SCRIPT = ROOT / "tools" / "verify-installer-artifact.ps1"
INSTALLER_SCRIPT = ROOT / "installer" / "shiyin_ai.iss"
PUBLISH_SCRIPT = ROOT / "tools" / "publish-release.ps1"
INSTALLER_SMOKE = ROOT / "tools" / "smoke-installer-updater.ps1"
UPDATER_PAGE = ROOT / "desktop-placeholder" / "updater.html"
BROWSER_SMOKE_SERVER = ROOT / "tools" / "browser-smoke-server.ps1"
BACKEND_SPEC = ROOT / "canvas-backend.spec"
REQUIREMENTS = ROOT / "requirements.txt"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
RELEASE_VERSION_RESOLVER = ROOT / "tools" / "resolve-release-version.py"
GITIGNORE = ROOT / ".gitignore"


class DesktopUpdaterContractTests(unittest.TestCase):
    def test_release_contract_uses_fixed_public_repository_and_exact_assets(self):
        source = UPDATER.read_text(encoding="utf-8")
        self.assertIn("luojiang419/SHIYIN-AI/releases/latest", source)
        self.assertIn('INSTALLER_PREFIX: &str = "SHIYIN-AI-Setup-"', source)
        self.assertIn('installer_asset_name', source)
        self.assertIn("Release 校验文件格式或资产名不正确", source)
        self.assertIn("GitHub 资产摘要与校验文件不一致", source)
        self.assertIn("tauri::async_runtime::spawn_blocking", source)
        self.assertIn("无法连接更新服务器。请检查网络或代理设置后重试。", source)
        self.assertIn("agents.push(build_update_agent(None)?)", source)
        self.assertIn("const DOWNLOAD_ATTEMPTS: usize = 3", source)
        self.assertIn("已重试 {DOWNLOAD_ATTEMPTS} 次", source)
        self.assertIn("fs::remove_file(&part)", source)
        self.assertIn('"SHIYIN_UPDATE_INSTALLER", installer', source)
        self.assertIn("/VERYSILENT", source)
        self.assertNotIn("legacyZip", source)
        self.assertNotIn("--apply-update", source)
        self.assertNotIn("Expand-Archive", source)

    def test_updater_keeps_data_and_uses_independent_helper(self):
        source = UPDATER.read_text(encoding="utf-8")
        self.assertIn("SHIYIN-AI-updater-", source)
        self.assertIn("--run-update-session", source)
        self.assertIn("UpdateInstallSession", source)
        self.assertIn("wait_for_exit", source)
        self.assertNotIn("apply_session", source)

    def test_updater_hides_console_windows_for_installer_helpers(self):
        source = UPDATER.read_text(encoding="utf-8")
        self.assertIn("const CREATE_NO_WINDOW: u32 = 0x0800_0000;", source)
        self.assertIn("fn command_without_console", source)
        self.assertIn('command_without_console("powershell.exe")', source)
        self.assertIn('command_without_console("tasklist")', source)
        self.assertIn("let mut command = command_without_console(&helper);", source)

    def test_sidebar_replaces_api_slot_with_update_and_groups_api_under_settings(self):
        source = INDEX.read_text(encoding="utf-8")
        self.assertIn('onclick="openDesktopUpdater()"', source)
        self.assertIn('>检查更新</span>', source)
        self.assertIn('>设置</span>', source)
        self.assertRegex(source, re.compile(r'id="settings-fold-group".*?switchUI\(this, \'api-settings\'\)', re.S))

    def test_settings_exposes_both_update_dimensions(self):
        source = APP_SETTINGS.read_text(encoding="utf-8")
        self.assertIn('id="updatePolicy"', source)
        self.assertIn('id="updateNetworkMode"', source)
        self.assertIn('value="automatic"', source)
        self.assertIn('value="manualProxy"', source)

    def test_local_desktop_page_can_invoke_only_update_commands(self):
        build_source = BUILD_RS.read_text(encoding="utf-8")
        capability = json.loads(CAPABILITY.read_text(encoding="utf-8"))
        self.assertIn('AppManifest::new().commands', build_source)
        self.assertIn('"check_for_update"', build_source)
        self.assertEqual(capability["windows"], ["main", "update"])
        self.assertEqual(capability["remote"]["urls"], ["http://127.0.0.1:*"])
        self.assertIn("allow-check-for-update", capability["permissions"])

    def test_manual_update_result_uses_centered_app_modal(self):
        source = DESKTOP_UPDATER.read_text(encoding="utf-8")
        self.assertIn("function showStatusModal", source)
        self.assertIn("modal.className = 'studio-modal'", source)
        self.assertIn("showStatusModal('当前已是最新版本'", source)
        self.assertIn("showStatusModal('检查更新失败'", source)
        self.assertNotIn("if (options.manual) alert(`检查更新失败", source)
        self.assertIn("setTimeout(() => checkAndDownload().catch(() => {}), 1200)", source)

    def test_build_and_publish_scripts_share_release_asset_contract(self):
        installer_build = INSTALLER_BUILD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('SHIYIN-AI-Setup-$version.exe', installer_build)
        self.assertIn('Get-Command ISCC.exe', installer_build)
        self.assertIn('dist\\installer-stage', installer_build)
        installer_verify = INSTALLER_VERIFY_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('SHIYIN-AI-Setup-$Version.exe', installer_verify)
        self.assertIn('ProductVersion', installer_verify)
        installer = INSTALLER_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('DefaultDirName=D:\\Program Files\\SHIYIN AI', installer)
        self.assertIn('Name: "{app}\\data"; Permissions: users-modify', installer)
        self.assertIn('Name: "{app}\\app"', installer)
        publish = PUBLISH_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('SHIYIN-AI-Setup-$Version.exe', publish)
        self.assertNotIn('legacyZip', publish)
        self.assertNotIn('SHIYIN-AI-v$Version-windows-x64.zip', publish)
        self.assertIn('luojiang419/SHIYIN-AI', publish)
        self.assertIn('function Get-Sha256', publish)
        self.assertNotIn('Get-FileHash', publish)
        self.assertIn('"${uploadBase}?name=$([Uri]::EscapeDataString($assetName))"', publish)
        self.assertIn('"${uploadBase}?name=$([Uri]::EscapeDataString($checksumName))"', publish)
        self.assertIn("Local compile and verification (GitHub Actions cloud build was not used)", publish)
        self.assertIn("Get-Content -Raw -Encoding UTF8 -LiteralPath $notesPath", publish)
        self.assertIn("[Text.Encoding]::UTF8.GetBytes($json)", publish)
        self.assertIn('$parameters.ContentType = "$ContentType; charset=utf-8"', publish)
        installer_smoke = INSTALLER_SMOKE.read_text(encoding="utf-8")
        self.assertIn("$FromInstaller", installer_smoke)
        self.assertNotIn("FromZip", installer_smoke)

    def test_portable_backend_collects_websocket_runtime_modules(self):
        self.assertIn("websockets", REQUIREMENTS.read_text(encoding="utf-8").splitlines())
        self.assertIn('collect_submodules("websockets")', BACKEND_SPEC.read_text(encoding="utf-8"))

    def test_browser_smoke_server_falls_back_to_system_python(self):
        source = BROWSER_SMOKE_SERVER.read_text(encoding="utf-8")
        self.assertIn('Test-Path -LiteralPath $python -PathType Leaf', source)
        self.assertIn('(Get-Command python -ErrorAction Stop).Source', source)

    def test_version_sources_are_three_part_and_synchronized(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["version"], version)

    def test_ci_uses_storyboard_style_cross_repository_release_transaction(self):
        workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
        publish = PUBLISH_SCRIPT.read_text(encoding="utf-8")
        resolver = RELEASE_VERSION_RESOLVER.read_text(encoding="utf-8")
        self.assertIn("RELEASE_REPO: luojiang419/SHIYIN-AI", workflow)
        self.assertIn("RELEASE_REPO_TOKEN", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("draft = $true", publish)
        self.assertIn("make_latest = 'true'", publish)
        self.assertIn("source-sha:$SourceSha", publish)
        self.assertIn("SHIYIN-AI-Setup-$Version.exe", publish)
        self.assertNotIn("legacyZip", workflow)
        self.assertNotIn("windows-x64.zip", workflow)
        self.assertIn("VERSION_PATTERN", resolver)

    def test_ci_runs_the_installer_updater_regression_test(self):
        updater = UPDATER.read_text(encoding="utf-8")
        workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("./tools/smoke-installer-updater.ps1", workflow)
        self.assertNotIn("apply_session", updater)

    def test_installer_updater_session_has_visible_progress_page(self):
        page = UPDATER_PAGE.read_text(encoding="utf-8")
        smoke = INSTALLER_SMOKE.read_text(encoding="utf-8")
        self.assertIn("update-progress", page)
        self.assertIn("window.__TAURI__", page)
        self.assertIn("run_installer_session", UPDATER.read_text(encoding="utf-8"))
        self.assertIn("--run-update-session", smoke)
        self.assertIn("installer_installed", smoke)
        self.assertIn("data_preserved", smoke)
        self.assertNotIn("FromZip", smoke)
        self.assertNotIn("Expand-Archive", smoke)

    def test_updater_logs_helper_failures_for_diagnosis(self):
        source = UPDATER.read_text(encoding="utf-8")
        self.assertIn('log(&log_data, &format!("更新失败：{error}"));', source)

    def test_ci_keeps_tauri_frontend_placeholder_in_public_source(self):
        self.assertTrue((ROOT / "desktop-placeholder" / "index.html").is_file())
        self.assertNotIn("desktop-placeholder/", GITIGNORE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
