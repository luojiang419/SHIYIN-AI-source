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
VERSION_SYNC_SCRIPT = ROOT / "tools" / "assert-version-sync.ps1"
WEB_CACHE_STAMP_SCRIPT = ROOT / "tools" / "stamp-web-cache-version.mjs"
INSTALLER_VERIFY_SCRIPT = ROOT / "tools" / "verify-installer-artifact.ps1"
INSTALLER_SCRIPT = ROOT / "installer" / "shiyin_ai.iss"
PUBLISH_SCRIPT = ROOT / "tools" / "publish-release.ps1"
INSTALLER_SMOKE = ROOT / "tools" / "smoke-installer-updater.ps1"
INSTALLER_PROGRESS_SMOKE = ROOT / "tools" / "smoke-installer-progress.ps1"
CACHE_CLEAN_SCRIPT = ROOT / "tools" / "clean-development-cache.ps1"
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

    def test_updater_repairs_start_menu_shortcuts_after_install(self):
        source = UPDATER.read_text(encoding="utf-8")
        self.assertIn("fn repair_start_menu_shortcuts", source)
        self.assertIn("CommonPrograms", source)
        self.assertIn("SHIYIN AI.lnk", source)
        self.assertIn("'SHIYIN-AI'", source)
        self.assertIn("SHIYIN_UPDATE_ROOT", source)
        self.assertLess(
            source.index("repair_start_menu_shortcuts(root, data);"),
            source.index("Command::new(&app_exe)"),
        )

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
        self.assertIn("core:event:allow-listen", capability["permissions"])
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
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertIn('SHIYIN-AI-Setup-$version.exe', installer_build)
        self.assertIn('Get-Command ISCC.exe', installer_build)
        self.assertIn('dist\\installer-stage', installer_build)
        self.assertIn("smoke-desktop.ps1", installer_build)
        self.assertIn("smoke-dwpose-packaged.py", installer_build)
        self.assertIn("DwposeSmokeInput", installer_build)
        self.assertIn("Packaged DWPose cached-model smoke test failed", installer_build)
        self.assertIn("Packaged DWPose fresh-install smoke test failed", installer_build)
        self.assertIn("Packaged desktop runtime smoke test failed", installer_build)
        self.assertIn("$runtimeSmokeSucceeded = $?", installer_build)
        self.assertIn("stamp-web-cache-version.mjs", installer_build)
        self.assertIn("Web cache-version stamping failed", installer_build)
        cache_stamp = WEB_CACHE_STAMP_SCRIPT.read_text(encoding="utf-8")
        self.assertIn(r"\/static\/", cache_stamp)
        self.assertIn("Cache-version rewrite unexpectedly emptied web asset", cache_stamp)
        self.assertIn("function Assert-StagedWebAssets", installer_build)
        self.assertIn("Staged canvas is missing the Topaz create-menu entry", installer_build)
        self.assertIn("Staged canvas navigation cache version is not", installer_build)
        self.assertGreaterEqual(installer_build.count("Assert-StagedWebAssets $stageRoot $version"), 2)
        self.assertEqual(package["scripts"]["desktop:build"], "npm run installer:build")
        self.assertIn("tauri build --no-bundle", package["scripts"]["desktop:host-build"])
        self.assertIn("npm run desktop:host-build", installer_build)
        installer_verify = INSTALLER_VERIFY_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('SHIYIN-AI-Setup-$Version.exe', installer_verify)
        self.assertIn('ProductVersion', installer_verify)
        installer = INSTALLER_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('DefaultDirName={code:ResolveDefaultInstallDir}', installer)
        self.assertIn('UsePreviousAppDir=no', installer)
        self.assertIn('DirExistsWarning=no', installer)
        self.assertIn("DefaultInstallDir = 'D:\\Program Files\\SHIYIN AI'", installer)
        self.assertIn('function IsInstallerTestPath', installer)
        self.assertIn("Pos('\\.build\\installer-updater-e2e', Normalized) > 0", installer)
        self.assertIn("Pos('\\.build\\installer-progress-smoke-', Normalized) > 0", installer)
        self.assertIn('function IsExistingInstallDir', installer)
        self.assertIn("data\\database\\canvas.db", installer)
        self.assertIn('Name: "{app}\\data"; Permissions: users-modify', installer)
        self.assertIn('Name: "{app}\\app"', installer)
        self.assertNotIn('Type: filesandordirs; Name: "{app}\\data"', installer)
        self.assertIn('Name: "{commonprograms}\\{#MyAppName}"', installer)
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
        self.assertIn("requires a clean machine", installer_smoke)
        self.assertIn("Remove-Item -LiteralPath $uninstallKey -Recurse -Force", installer_smoke)
        self.assertIn('Filter "installer-updater-e2e*"', CACHE_CLEAN_SCRIPT.read_text(encoding="utf-8"))
        progress_smoke = INSTALLER_PROGRESS_SMOKE.read_text(encoding="utf-8")
        self.assertIn("smoke-desktop.ps1", progress_smoke)
        self.assertIn("runtime_health", progress_smoke)
        self.assertIn("Installed desktop runtime did not satisfy the startup contract", progress_smoke)
        self.assertIn("$runtimeSmokeSucceeded = $?", progress_smoke)
        self.assertIn("refuses to overwrite an existing SHIYIN AI registration", progress_smoke)
        self.assertIn("Remove-Item -LiteralPath $uninstallKey", progress_smoke)

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
        package_lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))
        tauri = json.loads((ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
        update_notes = json.loads((ROOT / "static" / "update-notes.json").read_text(encoding="utf-8"))
        cargo_toml = (ROOT / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8")
        cargo_lock = (ROOT / "src-tauri" / "Cargo.lock").read_text(encoding="utf-8")
        backend = (ROOT / "main.py").read_text(encoding="utf-8")
        release_notes = (ROOT / "release-notes" / "current.md").read_text(encoding="utf-8")
        self.assertEqual(package_lock["version"], version)
        self.assertEqual(package_lock["packages"][""]["version"], version)
        self.assertEqual(tauri["version"], version)
        self.assertEqual(update_notes["version"], version)
        self.assertEqual(re.search(r'^version\s*=\s*"([^"]+)"', cargo_toml, re.M).group(1), version)
        self.assertEqual(
            re.search(r'\[\[package\]\]\s*name\s*=\s*"canvas-desktop"\s*version\s*=\s*"([^"]+)"', cargo_lock).group(1),
            version,
        )
        self.assertEqual(re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', backend, re.M).group(1), version)
        self.assertEqual(re.search(r'^# SHIYIN AI v(\d+\.\d+\.\d+)$', release_notes, re.M).group(1), version)

    def test_installer_fails_before_build_when_any_version_source_is_stale(self):
        installer_build = INSTALLER_BUILD_SCRIPT.read_text(encoding="utf-8")
        sync_script = VERSION_SYNC_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("assert-version-sync.ps1", installer_build)
        self.assertIn("Version synchronization check failed", installer_build)
        self.assertIn("if (-not $?)", installer_build)
        for source in (
            "package.json",
            "package-lock.json",
            "src-tauri/Cargo.toml",
            "src-tauri/Cargo.lock",
            "src-tauri/tauri.conf.json",
            "main.py",
            "static/update-notes.json",
            "release-notes/current.md",
        ):
            self.assertIn(source, sync_script)

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
        self.assertIn("$releases = Invoke-RestMethod", workflow)
        self.assertNotIn("$releases = @(Invoke-RestMethod", workflow)
        self.assertIn("$sourceVersion = (Get-Content -LiteralPath 'VERSION' -Raw).Trim()", workflow)
        self.assertIn("$sourceTag = \"v$sourceVersion\"", workflow)
        self.assertIn("Source VERSION $sourceVersion already has a published release", workflow)
        self.assertNotIn("$next = python tools/resolve-release-version.py --latest", workflow)
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
        progress_smoke = (ROOT / "tools" / "smoke-installer-progress.ps1").read_text(encoding="utf-8")
        installer_script = (ROOT / "installer" / "shiyin_ai.iss").read_text(encoding="utf-8")
        self.assertIn("update-progress", page)
        self.assertIn("progress-spinner", page)
        self.assertIn("@keyframes update-spin", page)
        self.assertIn("progress-fill", page)
        self.assertIn("progressPercent", page)
        self.assertIn("持续显示处理进度", page)
        self.assertIn("安装阶段按安装器实时回调推进", page)
        self.assertIn("async function prepareProgressListener()", page)
        self.assertIn("Promise.race([listenerTask, delay(800)])", page)
        self.assertIn("进度监听仍在准备，更新会话将继续执行", page)
        self.assertIn("更新会话已启动", page)
        self.assertIn("receivedBackendProgress", page)
        self.assertIn("if (!receivedBackendProgress)", page)
        self.assertNotIn("progressPercent.textContent", page)
        self.assertNotIn("textContent = `${value}%`", page)
        self.assertIn("await invoke('run_update_session')", page)
        self.assertIn("进度监听未就绪，更新会话将继续执行", page)
        self.assertLess(
            page.index("listen('update-progress', render)"),
            page.index("await invoke('run_update_session')"),
        )
        self.assertNotIn("阶段估算", page)
        self.assertNotIn("setInstallPhasePulse", page)
        self.assertNotIn("Math.round(index / 4 * 100)", page)
        self.assertIn("window.__TAURI__", page)
        self.assertIn("run_installer_session", UPDATER.read_text(encoding="utf-8"))
        self.assertIn("progress_percent: u8", UPDATER.read_text(encoding="utf-8"))
        self.assertIn("PROGRESS_PREPARE_START: u8 = 2", UPDATER.read_text(encoding="utf-8"))
        self.assertIn("PROGRESS_INSTALLER_STARTING: u8 = 30", UPDATER.read_text(encoding="utf-8"))
        self.assertIn("installer_overall_percent", UPDATER.read_text(encoding="utf-8"))
        self.assertIn("installer-progress.txt", UPDATER.read_text(encoding="utf-8"))
        self.assertIn("emit_installer_progress", UPDATER.read_text(encoding="utf-8"))
        self.assertNotIn("&format!(\"正在安装新版本… {overall_percent}%\")", UPDATER.read_text(encoding="utf-8"))
        self.assertNotIn("安装阶段 {percent}%", UPDATER.read_text(encoding="utf-8"))
        self.assertIn("CurInstallProgressChanged", installer_script)
        self.assertIn("UPDATEPROGRESS", installer_script)
        self.assertIn("realtime_progress", progress_smoke)
        self.assertIn("installer-progress.txt", progress_smoke)
        self.assertIn("$process.WaitForExit()", progress_smoke)
        self.assertIn("CommonPrograms", progress_smoke)
        self.assertIn("Remove-Item -LiteralPath $shortcutPath", progress_smoke)
        self.assertIn("start_menu_shortcut", progress_smoke)
        self.assertIn("installer-progress.txt", UPDATER.read_text(encoding="utf-8"))
        self.assertIn("--run-update-session", smoke)
        self.assertIn("installer_installed", smoke)
        self.assertIn("data_preserved", smoke)
        self.assertIn("start_menu_shortcut", smoke)
        self.assertIn("CommonPrograms", smoke)
        self.assertNotIn("FromZip", smoke)
        self.assertNotIn("Expand-Archive", smoke)

    def test_updater_logs_helper_failures_for_diagnosis(self):
        source = UPDATER.read_text(encoding="utf-8")
        self.assertIn("页面已请求启动更新会话，安装任务即将进入后台。", source)
        self.assertIn('log(&log_data, &format!("更新失败：{error}"));', source)

    def test_ci_keeps_tauri_frontend_placeholder_in_public_source(self):
        self.assertTrue((ROOT / "desktop-placeholder" / "index.html").is_file())
        self.assertNotIn("desktop-placeholder/", GITIGNORE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
