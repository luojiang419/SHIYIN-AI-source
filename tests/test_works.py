import asyncio
import base64
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from canvas_core.database import CanvasDatabase


class WorksFrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent.parent
        cls.index = (root / "static" / "index.html").read_text(encoding="utf-8")
        cls.ecommerce = (root / "static" / "ecommerce.html").read_text(encoding="utf-8")
        cls.works = (root / "static" / "works.html").read_text(encoding="utf-8")
        cls.works_js = (root / "static" / "js" / "works.js").read_text(encoding="utf-8")
        cls.works_css = (root / "static" / "css" / "works.css").read_text(encoding="utf-8")
        cls.compare_js = (root / "static" / "js" / "compare-viewer.js").read_text(encoding="utf-8")

    def test_works_navigation_is_directly_below_asset_library(self):
        asset = self.index.index("switchUI(this, 'asset-manager')")
        works = self.index.index("switchUI(this, 'works')")
        self.assertLess(asset, works)
        self.assertIn('id="frame-works"', self.index)
        self.assertIn("'works'", self.index)

    def test_works_has_all_and_favorite_tabs_with_persistent_api(self):
        self.assertIn('data-tab="all"', self.works)
        self.assertIn('data-tab="favorite"', self.works)
        self.assertIn('data-tab="trash"', self.works)
        self.assertIn("/api/works?limit=1000&include_trashed=true", self.works_js)
        self.assertIn("/favorite`,{method:'PUT'", self.works_js)
        self.assertIn("/metadata`,{method:'PUT'", self.works_js)
        self.assertIn('id="worksQuickCompare"', self.works)
        self.assertIn('id="worksDownloadAll"', self.works)
        self.assertIn('id="worksClearAll"', self.works)
        self.assertIn('id="compareTargetFile"', self.works)

    def test_compare_viewer_supports_fullscreen_wheel_zoom_and_middle_pan(self):
        self.assertIn("event.button === 1", self.compare_js)
        self.assertIn("addEventListener('wheel'", self.compare_js)
        self.assertIn("clamp(value,1,8)", self.compare_js)
        self.assertIn("requestFullscreen", self.compare_js)
        self.assertIn("data-compare-fullscreen", self.works)
        self.assertIn("compareBaseFile", self.works)

    def test_download_uses_attachment_proxy_and_enterprise_name(self):
        self.assertIn('data-download-work="${escapeHtml(item.id)}"', self.works_js)
        self.assertIn("/api/download-output?url=${encodeURIComponent(work.url)}&name=${encodeURIComponent(name)}", self.works_js)
        self.assertIn("function workDownloadName(work)", self.works_js)
        self.assertIn("SHIYIN-${padSequence(sequence)}-${workDatePart(work)}${extensionFromWork(work)}", self.works_js)
        self.assertIn("work?.download_name", self.works_js)
        self.assertIn("desktop.download.finished", self.works_js)
        self.assertNotIn('<a href="${escapeHtml(item.url)}" download=', self.works_js)

    def test_rename_action_is_replaced_by_open_directory_and_bulk_download(self):
        self.assertNotIn("worksRenameDialog", self.works + self.works_js)
        self.assertNotIn("data-rename-work", self.works_js)
        self.assertIn("data-reveal-work", self.works_js)
        self.assertIn("/api/works/${encodeURIComponent(work.id)}/reveal", self.works_js)
        self.assertIn("/api/works/download-all?name=${encodeURIComponent(name)}", self.works_js)
        self.assertIn("fetchJson('/api/works',{method:'DELETE'})", self.works_js)
        self.assertIn("window.showSaveFilePicker", self.works_js)
        self.assertIn("suggestedName:name", self.works_js)
        self.assertIn("works-download-all", self.works_css)
        self.assertIn("works-danger-button", self.works_css)

    def test_work_card_actions_remain_visible_in_dense_grids(self):
        self.assertIn("grid-auto-rows:max-content", self.works_css)
        self.assertIn("align-items:start", self.works_css)
        self.assertIn("padding:1px 4px 84px 1px", self.works_css)
        self.assertIn(".works-card { position:relative; min-width:0; min-height:334px; display:grid; grid-template-rows:auto minmax(164px,auto)", self.works_css)
        self.assertIn(".works-card-media { position:relative; width:100%; aspect-ratio:4/3; display:block", self.works_css)
        self.assertIn(".works-card-body { min-height:164px; display:flex; flex-direction:column", self.works_css)
        self.assertIn(".works-card-actions { flex:0 0 auto; display:grid", self.works_css)
        self.assertIn("margin-top:auto; padding-top:11px", self.works_css)
        self.assertIn(".works-card { min-height:286px; grid-template-rows:auto minmax(154px,auto); }", self.works_css)

    def test_ecommerce_no_longer_exposes_preview_publish_switch(self):
        self.assertNotIn('id="modeToggle"', self.ecommerce)
        self.assertNotIn("快速预览", self.ecommerce)
        self.assertNotIn("上架品质", self.ecommerce)
        self.assertIn("compare-viewer.js", self.ecommerce)


class WorksBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main
        cls.main = main

    def test_work_metadata_overrides_name_and_keeps_soft_trash_recoverable(self):
        record = {
            "_history_id": "history-1",
            "type": "ecommerce",
            "timestamp": 10,
            "images": ["/output/result.png"],
            "image_items": [{"width": 1200, "height": 1600}],
            "inputs": [{"role": "source", "url": "/input/source.png"}],
        }
        work_id = self.main.work_item_id("history-1", 0, "/output/result.png")
        works = self.main.generated_work_items([record], {
            work_id: {"name": "主图 A", "favorite": True, "trashed": True, "trashed_at": 12},
        })
        self.assertEqual(works[0]["name"], "主图 A")
        self.assertEqual(works[0]["original_name"], "result.png")
        self.assertTrue(works[0]["favorite"])
        self.assertTrue(works[0]["trashed"])
        self.assertEqual(works[0]["url"], "/output/result.png")
        self.assertRegex(works[0]["download_name"], r"^SHIYIN-000001-\d{8}\.png$")
        self.assertEqual(works[0]["download_sequence"], 1)

    def test_default_work_name_uses_enterprise_name_instead_of_random_source_name(self):
        record = {
            "_history_id": "history-1",
            "type": "ecommerce",
            "timestamp": 10,
            "images": ["/assets/output/ecommerce_0205d638aa.png"],
        }
        works = self.main.generated_work_items([record], {})
        self.assertRegex(works[0]["name"], r"^SHIYIN-000001-\d{8}\.png$")
        self.assertEqual(works[0]["original_name"], "ecommerce_0205d638aa.png")

    def test_save_ai_image_to_output_can_use_enterprise_filename_sequence(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "output"
            output.mkdir()
            (output / "SHIYIN-000004-20260722.png").write_bytes(b"old")
            payload = {
                "type": "b64",
                "value": base64.b64encode(b"image-bytes").decode("ascii"),
                "mime_type": "image/png",
            }
            with patch.object(self.main, "OUTPUT_OUTPUT_DIR", str(output)):
                url = asyncio.run(self.main.save_ai_image_to_output(
                    payload,
                    prefix="ecommerce_",
                    enterprise_filename=True,
                ))
            self.assertRegex(url, r"^/assets/output/SHIYIN-000005-\d{8}\.png$")
            self.assertTrue((output / Path(url).name).exists())

    def test_works_api_hides_trash_by_default_and_can_include_it(self):
        items = [
            {"id": "active", "name": "A", "kind": "ecommerce", "favorite": False, "trashed": False},
            {"id": "trash", "name": "B", "kind": "ecommerce", "favorite": False, "trashed": True},
        ]
        with patch.object(self.main, "all_generated_works", return_value=items):
            visible = asyncio.run(self.main.list_generated_works(limit=100))
            complete = asyncio.run(self.main.list_generated_works(limit=100, include_trashed=True))
        self.assertEqual([item["id"] for item in visible["works"]], ["active"])
        self.assertEqual([item["id"] for item in complete["works"]], ["active", "trash"])

    def test_rename_trash_and_restore_are_persisted_in_sqlite_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            database = CanvasDatabase(Path(root) / "canvas.db")
            database.initialize()
            database.prepend_history({
                "id": "history-2",
                "type": "ecommerce",
                "timestamp": 20,
                "images": ["/output/work.png"],
                "inputs": [{"role": "source", "url": "/input/source.png"}],
            })
            with patch.object(self.main, "DATABASE", database):
                work_id = self.main.all_generated_works()[0]["id"]
                renamed, revision = self.main.update_work_metadata(work_id, name="商品主图", favorite=True, trashed=True)
                self.assertGreater(revision, 0)
                self.assertEqual(renamed["name"], "商品主图")
                self.assertTrue(renamed["favorite"])
                self.assertTrue(renamed["trashed"])
                restored, _ = self.main.update_work_metadata(work_id, trashed=False)
                self.assertFalse(restored["trashed"])
                self.assertEqual(restored["name"], "商品主图")

    def test_reveal_work_opens_local_file_location(self):
        with tempfile.TemporaryDirectory() as root:
            image = Path(root) / "work.png"
            image.write_bytes(b"image")
            work = {"id": "work-a", "url": "/output/work.png", "original_name": "work.png", "created_at": 20}
            with (
                patch.object(self.main, "all_generated_works", return_value=[work]),
                patch.object(self.main, "output_file_from_url", return_value=str(image)),
                patch.object(self.main.subprocess, "Popen") as popen,
            ):
                result = asyncio.run(self.main.reveal_generated_work("work-a"))
            self.assertTrue(result["revealed"])
            self.assertEqual(Path(result["path"]), image)
            popen.assert_called_once()

    def test_download_all_works_creates_enterprise_named_zip(self):
        with tempfile.TemporaryDirectory() as root:
            first = Path(root) / "first.png"
            second = Path(root) / "second.jpg"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            works = [
                {"id": "work-a", "url": "/output/first.png", "original_name": "first.png", "created_at": 20, "trashed": False},
                {"id": "work-b", "url": "/output/second.jpg", "original_name": "second.jpg", "created_at": 20, "trashed": False},
                {"id": "work-trash", "url": "/output/trash.png", "original_name": "trash.png", "created_at": 20, "trashed": True},
            ]
            paths = {"/output/first.png": str(first), "/output/second.jpg": str(second)}
            with (
                patch.object(self.main, "all_generated_works", return_value=works),
                patch.object(self.main, "output_file_from_url", side_effect=lambda url: paths.get(url, "")),
            ):
                response = asyncio.run(self.main.download_all_generated_works())
            with zipfile.ZipFile(io.BytesIO(response.body)) as archive:
                names = archive.namelist()
                self.assertEqual(archive.read(names[0]), b"first")
                self.assertEqual(archive.read(names[1]), b"second")
            self.assertEqual(names, ["SHIYIN-000001-19700101.png", "SHIYIN-000002-19700101.jpg"])

    def test_clear_all_works_deletes_history_metadata_and_local_output_files(self):
        with tempfile.TemporaryDirectory() as root:
            database = CanvasDatabase(Path(root) / "canvas.db")
            database.initialize()
            output = Path(root) / "output"
            output.mkdir()
            image = output / "first.png"
            image.write_bytes(b"first")
            database.prepend_history({
                "id": "history-clear",
                "type": "ecommerce",
                "timestamp": 30,
                "images": ["/assets/output/first.png"],
            })
            work_id = self.main.work_item_id("history-clear", 0, "/assets/output/first.png")
            database.put_document("works", "metadata", {work_id: {"favorite": True}})
            with (
                patch.object(self.main, "DATABASE", database),
                patch.object(self.main, "OUTPUT_OUTPUT_DIR", str(output)),
                patch.object(self.main, "publish_entity_changed"),
            ):
                result = asyncio.run(self.main.clear_generated_works())
                self.assertTrue(result["success"])
                self.assertEqual(result["total"], 1)
                self.assertEqual(result["deleted_records"], 1)
                self.assertEqual(result["deleted_files"], 1)
                self.assertFalse(image.exists())
                self.assertEqual(database.list_history(), [])
                self.assertEqual(self.main.work_metadata(), {})


if __name__ == "__main__":
    unittest.main()
