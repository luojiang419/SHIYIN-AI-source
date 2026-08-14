import unittest
from pathlib import Path


class BlenderInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent.parent
        cls.iss = (root / "installer" / "shiyin_ai.iss").read_text(encoding="utf-8")
        cls.install_script_path = (
            root / "tools" / "blender-addon" / "windows" / "Install-SHIYINBlenderAddon.ps1"
        )
        cls.install_script = cls.install_script_path.read_text(encoding="utf-8-sig")
        cls.script_test = (
            root / "tests" / "windows" / "Test-SHIYINBlenderAddonInstaller.ps1"
        ).read_text(encoding="utf-8-sig")
        cls.build_script = (root / "tools" / "build-installer.ps1").read_text(encoding="utf-8")
        cls.smoke = (root / "tools" / "smoke-installer-progress.ps1").read_text(encoding="utf-8")

    def test_installer_has_optional_blender_plugin_page(self):
        self.assertIn("BlenderPluginPage := CreateInputOptionPage(", self.iss)
        self.assertIn("Blender 联动插件", self.iss)
        self.assertIn("安装到检测到的 Blender（推荐）", self.iss)
        self.assertIn("暂不安装，仅保留插件包", self.iss)
        self.assertIn("安装后无需配对码", self.iss)
        self.assertIn("-DiscoverOnly", self.iss)

    def test_installer_runs_user_scoped_plugin_step_as_original_user(self):
        self.assertIn("ExecAsOriginalUser", self.iss)
        self.assertIn("-CheckProcessOnly", self.iss)
        self.assertIn("Blender 正在运行", self.install_script)
        self.assertIn("bpy.ops.wm.save_userpref()", self.install_script)
        self.assertIn('bpy.utils.user_resource("SCRIPTS", path="addons", create=True)', self.install_script)

    def test_plugin_deployment_is_atomic_and_rejects_reparse_point_target(self):
        self.assertIn('stage = addons_root / (".%s.install-%s"', self.install_script)
        self.assertIn('backup = addons_root / (".%s.backup-%s"', self.install_script)
        self.assertIn('FILE_ATTRIBUTE_REPARSE_POINT', self.install_script)
        self.assertIn('target.lstat().st_file_attributes', self.install_script)
        self.assertIn('Refusing to replace a linked Blender add-on', self.install_script)
        self.assertIn("backup.rename(target)", self.install_script)

    def test_silent_smoke_explicitly_skips_external_plugin_mutation(self):
        self.assertIn("{param:NOBLENDERPLUGIN|0}", self.iss)
        self.assertIn("else if WizardSilent then", self.iss)
        self.assertIn("'/NOBLENDERPLUGIN=1'", self.smoke)

    def test_windows_powershell_scripts_require_utf8_bom_and_ps51_test(self):
        self.assertTrue(self.install_script_path.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertIn("WindowsPowerShell\\v1.0\\powershell.exe", self.iss)
        self.assertIn("Assert-Utf8Bom", self.script_test)

    def test_build_stage_retains_blender_installer_payload(self):
        self.assertIn("tools\\blender-addon", self.build_script)
        self.assertIn("connectors 'blender'", self.build_script)
        self.assertIn("app\\connectors\\blender\\windows\\Install-SHIYINBlenderAddon.ps1", self.iss)


if __name__ == "__main__":
    unittest.main()
