import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from canvas_core.bridge_package import BridgePackageError, read_bridge_package, write_bridge_package
from tests.test_bridge_manifest import sample_manifest


class BridgePackageTests(unittest.TestCase):
    def test_write_read_roundtrip_and_checksums(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = root / "frame.png"
            image.write_bytes(b"png-data")
            output = root / "bridge.filmbridge.zip"
            result = write_bridge_package(sample_manifest(), {"images/original/001.png": image}, output)
            self.assertTrue(Path(result["path"]).is_file())
            package = read_bridge_package(output, root / "imports")
            self.assertEqual(package.manifest["bridge_id"], "film:project-1:board-1")
            self.assertEqual(package.files["images/original/001.png"].read_bytes(), b"png-data")
            package.cleanup()
            self.assertFalse(package.root.exists())

    def test_tampered_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = root / "frame.png"
            image.write_bytes(b"png-data")
            output = root / "bridge.zip"
            write_bridge_package(sample_manifest(), {"images/original/001.png": image}, output)
            tampered = root / "tampered.zip"
            with zipfile.ZipFile(output, "r") as source, zipfile.ZipFile(tampered, "w") as target:
                for item in source.infolist():
                    data = source.read(item.filename)
                    if item.filename == "images/original/001.png": data += b"tampered"
                    target.writestr(item, data)
            with self.assertRaises(BridgePackageError):
                read_bridge_package(tampered, root / "imports")

    def test_zip_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "bad.zip"
            manifest = json.dumps(sample_manifest()).encode("utf-8")
            with zipfile.ZipFile(output, "w") as archive:
                archive.writestr("manifest.json", manifest)
                archive.writestr("../escape.png", b"bad")
            with self.assertRaises(BridgePackageError):
                read_bridge_package(output, root / "imports")

    def test_output_write_is_atomic_and_rejects_non_image_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "notes.txt"
            source.write_text("not image", encoding="utf-8")
            with self.assertRaises(BridgePackageError):
                write_bridge_package(sample_manifest(), {"images/original/001.txt": source}, root / "bridge.zip")
            self.assertFalse(list(root.glob("*.partial")))


if __name__ == "__main__":
    unittest.main()
