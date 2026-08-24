import asyncio
import base64
import io
import os
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
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
        self.assertIn("const PAGE_LIMIT = 120", self.works_js)
        self.assertIn("new URLSearchParams({limit:String(PAGE_LIMIT),include_trashed:'true'})", self.works_js)
        self.assertIn("params.set('cursor', cursor)", self.works_js)
        self.assertIn("state.nextCursor = data.next_cursor || ''", self.works_js)
        self.assertIn("/favorite`,{method:'PUT'", self.works_js)
        self.assertIn("/metadata`,{method:'PUT'", self.works_js)
        self.assertIn("function renderVirtual(force=false)", self.works_js)
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
        self.assertIn("SHIYIN-${padSequence(work?.download_sequence || 1)}-${workDatePart(work)}${extensionFromWork(work)}", self.works_js)
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
        self.assertIn("display:block", self.works_css)
        self.assertIn(".works-virtual-spacer", self.works_css)
        self.assertIn("position:absolute;width:${metrics.cardWidth}px", self.works_js)
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

    def test_generated_asset_route_maps_output_url_to_generated_directory(self):
        with tempfile.TemporaryDirectory() as root:
            media = Path(root) / "media"
            generated = media / "generated"
            generated.mkdir(parents=True)
            image = generated / "history.png"
            image.write_bytes(b"history-image")
            with patch.object(self.main, "DATA_LAYOUT", SimpleNamespace(media=media)):
                response = self.main.account_asset_file("output/history.png")
        self.assertEqual(Path(response.path), image)

    def test_works_api_normalizes_legacy_loopback_media_urls(self):
        works = self.main.finalize_work_items([{
            "id": "legacy-work",
            "name": "legacy.png",
            "original_name": "legacy.png",
            "url": "http://localhost:3000/assets/output/legacy.png?old=1",
            "source_url": "http://127.0.0.1:3000/assets/input/source.png",
            "references": [{"url": "http://localhost:3000/assets/uploads/ref.png"}],
            "created_at": 10,
        }])
        self.assertEqual(works[0]["url"], "/assets/output/legacy.png?old=1")
        self.assertEqual(works[0]["source_url"], "/assets/input/source.png")
        self.assertEqual(works[0]["references"][0]["url"], "/assets/uploads/ref.png")

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
        with tempfile.TemporaryDirectory() as root:
            database = CanvasDatabase(Path(root) / "canvas.db")
            database.initialize()
            database.prepend_history({"id": "active-history", "type": "ecommerce", "timestamp": 20, "images": ["/output/active.png"]})
            database.prepend_history({"id": "trash-history", "type": "ecommerce", "timestamp": 10, "images": ["/output/trash.png"]})
            work_id = self.main.work_item_id("trash-history", 0, "/output/trash.png")
            database.put_document("works", "metadata", {work_id: {"trashed": True, "updated_at": 30, "trashed_at": 30}})
            database.rebuild_work_items({work_id: {"trashed": True, "updated_at": 30, "trashed_at": 30}})
            with patch.object(self.main, "DATABASE", database):
                visible = asyncio.run(self.main.list_generated_works(limit=100))
                complete = asyncio.run(self.main.list_generated_works(limit=100, include_trashed=True))
        self.assertEqual([item["history_id"] for item in visible["works"]], ["active-history"])
        self.assertEqual([item["history_id"] for item in complete["works"]], ["active-history", "trash-history"])

    def test_works_api_returns_cursor_pages_from_sqlite_index(self):
        with tempfile.TemporaryDirectory() as root:
            database = CanvasDatabase(Path(root) / "canvas.db")
            database.initialize()
            for index in range(5):
                database.prepend_history({
                    "id": f"history-{index}",
                    "type": "online",
                    "timestamp": 100 + index,
                    "prompt": f"prompt {index}",
                    "images": [f"/output/{index}.png"],
                }, limit=10)
            with patch.object(self.main, "DATABASE", database):
                first = asyncio.run(self.main.list_generated_works(limit=2))
                second = asyncio.run(self.main.list_generated_works(limit=2, cursor=first["next_cursor"]))
        self.assertEqual(first["total"], 5)
        self.assertEqual([item["history_id"] for item in first["works"]], ["history-4", "history-3"])
        self.assertTrue(first["next_cursor"])
        self.assertEqual([item["history_id"] for item in second["works"]], ["history-2", "history-1"])

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

    def test_canvas_work_items_use_actual_filename_and_file_modified_time(self):
        with tempfile.TemporaryDirectory() as root:
            first = Path(root) / "SHIYIN-000101-20260824.png"
            second = Path(root) / "SHIYIN-000102-20260824.png"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            os.utime(first, (100, 100))
            os.utime(second, (200, 200))
            indexed = {
                "items": [
                    {
                        "id": "asset-1",
                        "url": "/assets/output/SHIYIN-000101-20260824.png",
                        "name": "同一个节点名称",
                        "kind": "image",
                        "created_at": 999,
                    },
                    {
                        "id": "asset-2",
                        "url": "/assets/output/SHIYIN-000102-20260824.png",
                        "name": "同一个节点名称",
                        "kind": "image",
                        "created_at": 999,
                    },
                ]
            }
            paths = {
                "/assets/output/SHIYIN-000101-20260824.png": str(first),
                "/assets/output/SHIYIN-000102-20260824.png": str(second),
            }
            with (
                patch.object(self.main, "canvas_assets_index", return_value=indexed),
                patch.object(self.main, "output_file_from_url", side_effect=lambda url: paths.get(url, "")),
            ):
                works = self.main.canvas_generated_work_items({})
        self.assertEqual([item["original_name"] for item in works], [first.name, second.name])
        self.assertEqual([item["created_at"] for item in works], [100.0, 200.0])
        self.assertEqual(len({item["name"] for item in works}), 2)

    def test_generated_work_items_use_each_local_file_modified_time(self):
        with tempfile.TemporaryDirectory() as root:
            first = Path(root) / "SHIYIN-000201-20260824.png"
            second = Path(root) / "SHIYIN-000202-20260824.png"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            os.utime(first, (300, 300))
            os.utime(second, (400, 400))
            paths = {
                "/assets/output/SHIYIN-000201-20260824.png": str(first),
                "/assets/output/SHIYIN-000202-20260824.png": str(second),
            }
            with patch.object(self.main, "output_file_from_url", side_effect=lambda url: paths.get(url, "")):
                works = self.main.finalize_work_items([
                    {
                        "id": "work-first",
                        "url": "/assets/output/SHIYIN-000201-20260824.png",
                        "original_name": first.name,
                        "name": first.name,
                        "created_at": 999,
                    },
                    {
                        "id": "work-second",
                        "url": "/assets/output/SHIYIN-000202-20260824.png",
                        "original_name": second.name,
                        "name": second.name,
                        "created_at": 999,
                    },
                ])
        self.assertEqual([item["created_at"] for item in works], [300.0, 400.0])

    def test_reveal_work_falls_back_to_legacy_exports_generated_path(self):
        with tempfile.TemporaryDirectory() as root:
            exports = Path(root) / "exports"
            legacy = exports / "generated"
            legacy.mkdir(parents=True)
            image = legacy / "legacy.png"
            image.write_bytes(b"image")
            data_layout = SimpleNamespace(exports=exports)
            work = {"id": "work-legacy", "url": "/assets/output/legacy.png", "original_name": "legacy.png", "created_at": 20}
            with (
                patch.object(self.main, "DATA_LAYOUT", data_layout),
                patch.object(self.main, "OUTPUT_DIR", str(Path(root) / "exports-root")),
                patch.object(self.main, "output_file_from_url", return_value=""),
                patch.object(self.main, "local_media_file_by_basename", return_value=None),
            ):
                self.assertEqual(self.main.work_local_file_path(work), str(image.resolve()))

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

    def test_media_reconcile_counts_references_and_cleans_orphans(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            output = root_path / "output"
            input_dir = root_path / "input"
            uploads = root_path / "uploads"
            legacy_output = root_path / "legacy-output"
            assets = root_path / "assets"
            for folder in (output, input_dir, uploads, legacy_output, assets):
                folder.mkdir(parents=True)
            used = output / "used.png"
            task_used = output / "task-used.png"
            orphan = output / "orphan.png"
            used.write_bytes(b"used")
            task_used.write_bytes(b"task-used")
            orphan.write_bytes(b"orphan")
            old = time.time() - 3 * 24 * 60 * 60
            os.utime(orphan, (old, old))
            database = CanvasDatabase(root_path / "canvas.db")
            database.initialize()
            database.prepend_history({
                "id": "history-media",
                "type": "ecommerce",
                "timestamp": 20,
                "images": ["/assets/output/used.png"],
            })
            database.save_canvas({
                "id": "canvas-media",
                "title": "媒体引用",
                "project": "default",
                "kind": "classic",
                "updated_at": 30,
                "nodes": [{"id": "node-used", "url": "/assets/output/used.png"}],
            }, touch=False)
            database.upsert_task("ecommerce", {
                "id": "ecommerce-media-reference",
                "status": "succeeded",
                "result": {"images": ["/assets/output/task-used.png"]},
            })
            with (
                patch.object(self.main, "DATABASE", database),
                patch.object(self.main, "OUTPUT_OUTPUT_DIR", str(output)),
                patch.object(self.main, "OUTPUT_INPUT_DIR", str(input_dir)),
                patch.object(self.main, "LOCAL_UPLOAD_DIR", str(uploads)),
                patch.object(self.main, "OUTPUT_DIR", str(legacy_output)),
                patch.object(self.main, "ASSETS_DIR", str(assets)),
            ):
                reconciled = self.main.reconcile_internal_media_index()
                self.assertEqual(reconciled["summary"]["categories"]["output"]["count"], 3)
                self.assertEqual(reconciled["summary"]["orphaned"]["output"]["count"], 1)
                dry_run = self.main.cleanup_orphan_internal_media(grace_seconds=24 * 60 * 60, dry_run=True)
                self.assertEqual(dry_run["candidate_count"], 1)
                self.assertTrue(orphan.exists())
                cleaned = self.main.cleanup_orphan_internal_media(grace_seconds=24 * 60 * 60, dry_run=False)
                self.assertEqual(cleaned["deleted_files"], 1)
                self.assertFalse(orphan.exists())
                self.assertTrue(used.exists())
                self.assertTrue(task_used.exists())


if __name__ == "__main__":
    unittest.main()
