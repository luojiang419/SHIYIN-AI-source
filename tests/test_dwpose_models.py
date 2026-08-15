import hashlib
import io
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from canvas_core.dwpose_models import DWPoseModelManager, DWPoseModelSpec


class _FakeResponse:
    def __init__(self, status_code, chunks):
        self.status_code = status_code
        self._chunks = list(chunks)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        del chunk_size
        yield from self._chunks


class _FakeSession:
    def __init__(self, response):
        self.response = response
        self.headers = None

    def get(self, _url, *, headers, **_kwargs):
        self.headers = dict(headers)
        return self.response

    def close(self):
        return None


class DWPoseModelManagerTests(unittest.TestCase):
    detector = b"detector-model"
    pose = b"pose-model-data"

    def specs(self):
        return (
            DWPoseModelSpec(
                "yolox_l.onnx", len(self.detector), hashlib.sha256(self.detector).hexdigest(), "official://detector"
            ),
            DWPoseModelSpec(
                "dw-ll_ucoco_384.onnx", len(self.pose), hashlib.sha256(self.pose).hexdigest(), "official://pose"
            ),
        )

    def archive(self, detector=None, pose=None):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("dwpose/yolox_l.onnx", self.detector if detector is None else detector)
            bundle.writestr("dwpose/dw-ll_ucoco_384.onnx", self.pose if pose is None else pose)
        return buffer.getvalue()

    def make_manager(self, root, *, proxies=None, archive_size=None):
        archive_size = len(self.archive()) if archive_size is None else archive_size
        return DWPoseModelManager(
            Path(root) / "models",
            specs=self.specs(),
            domestic_archive_url="domestic://dwpose.zip",
            domestic_archive_size=archive_size,
            proxy_provider=lambda: dict(proxies or {}),
        )

    def test_domestic_archive_is_preferred_and_committed_after_hash_verification(self):
        with tempfile.TemporaryDirectory() as root:
            manager = self.make_manager(root)
            archive = self.archive()
            calls = []

            def fake_download(url, target, **kwargs):
                calls.append((url, kwargs["source_label"]))
                target.write_bytes(archive)

            with patch.object(manager, "_download_url", side_effect=fake_download):
                self.assertTrue(manager.ensure_now())
            self.assertEqual(calls, [("domestic://dwpose.zip", "腾讯国内镜像直连")])
            self.assertEqual(manager.model_path("yolox_l.onnx").read_bytes(), self.detector)
            self.assertEqual(manager.model_path("dw-ll_ucoco_384.onnx").read_bytes(), self.pose)
            self.assertTrue(manager.status()["ready"])
            self.assertFalse((manager.download_root / "dwpose-tencent.zip").exists())

    def test_corrupt_domestic_archive_falls_back_to_official_source(self):
        with tempfile.TemporaryDirectory() as root:
            manager = self.make_manager(root, archive_size=len(self.archive(pose=b"bad")))
            bad_archive = self.archive(pose=b"bad")
            calls = []

            def fake_download(url, target, **kwargs):
                calls.append((url, kwargs["source_label"]))
                if url.startswith("domestic:"):
                    target.write_bytes(bad_archive)
                elif url.endswith("detector"):
                    target.write_bytes(self.detector)
                else:
                    target.write_bytes(self.pose)

            with patch.object(manager, "_download_url", side_effect=fake_download):
                self.assertTrue(manager.ensure_now())
            self.assertEqual(calls[0][0], "domestic://dwpose.zip")
            self.assertEqual([item[0] for item in calls[-2:]], ["official://detector", "official://pose"])
            self.assertEqual(manager.status()["source_label"], "Hugging Face 官方源直连")

    def test_source_order_uses_system_proxy_before_official_direct(self):
        with tempfile.TemporaryDirectory() as root:
            manager = self.make_manager(root, proxies={"https": "http://127.0.0.1:7890"})
            calls = []

            def fake_download(url, target, **kwargs):
                calls.append((url, kwargs["source_label"], dict(kwargs.get("proxies") or {})))
                if kwargs["source_label"] != "Hugging Face 官方源（系统代理）":
                    raise RuntimeError("simulated source failure")
                target.write_bytes(self.detector if url.endswith("detector") else self.pose)

            with patch.object(manager, "_download_url", side_effect=fake_download):
                self.assertTrue(manager.ensure_now())
            labels = [item[1] for item in calls]
            self.assertEqual(labels[:3], [
                "腾讯国内镜像直连",
                "腾讯国内镜像（系统代理）",
                "Hugging Face 官方源（系统代理）",
            ])
            self.assertEqual(calls[2][2]["https"], "http://127.0.0.1:7890")

    def test_existing_models_are_reused_without_network_after_upgrade(self):
        with tempfile.TemporaryDirectory() as root:
            manager = self.make_manager(root)
            manager.model_root.mkdir(parents=True)
            manager.model_path("yolox_l.onnx").write_bytes(self.detector)
            manager.model_path("dw-ll_ucoco_384.onnx").write_bytes(self.pose)
            with patch.object(manager, "_download_url", side_effect=AssertionError("network must not be used")):
                self.assertTrue(manager.ensure_now())
            self.assertTrue(manager.status()["ready"])
            self.assertEqual(manager.status()["source_label"], "已安装模型")

    def test_range_resume_appends_partial_download(self):
        with tempfile.TemporaryDirectory() as root:
            manager = self.make_manager(root)
            target = Path(root) / "file.bin"
            partial = target.with_name("file.bin.part")
            partial.write_bytes(b"abc")
            session = _FakeSession(_FakeResponse(206, [b"def", b"ghi"]))
            with patch.object(manager, "_new_session", return_value=session):
                manager._download_url(
                    "test://file",
                    target,
                    expected_size=9,
                    proxies=None,
                    source_label="test",
                )
            self.assertEqual(session.headers["Range"], "bytes=3-")
            self.assertEqual(target.read_bytes(), b"abcdefghi")

    def test_background_start_deduplicates_concurrent_requests(self):
        with tempfile.TemporaryDirectory() as root:
            manager = self.make_manager(root)
            entered = threading.Event()
            release = threading.Event()

            def slow_ensure():
                entered.set()
                release.wait(2)
                return False

            with patch.object(manager, "ensure_now", side_effect=slow_ensure):
                self.assertTrue(manager.start_background())
                self.assertTrue(entered.wait(1))
                self.assertFalse(manager.start_background())
                release.set()
                manager.wait(2)


if __name__ == "__main__":
    unittest.main()
