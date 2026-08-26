import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

import main


class AngleStyleCalibrationTests(unittest.TestCase):
    def test_color_calibration_moves_generated_palette_toward_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            target = root / "target.png"
            Image.fromarray(np.full((32, 32, 3), [180, 120, 80], dtype=np.uint8), "RGB").save(source)
            Image.fromarray(np.full((32, 32, 3), [70, 100, 180], dtype=np.uint8), "RGB").save(target)

            original = main.output_file_from_url
            try:
                main.output_file_from_url = lambda url: str(root / Path(str(url)).name)
                self.assertTrue(main.harmonize_generated_image_style("/assets/input/source.png", "/assets/output/target.png"))
            finally:
                main.output_file_from_url = original

            result = np.asarray(Image.open(target).convert("RGB"), dtype=np.float32).mean(axis=(0, 1))
            self.assertTrue(np.linalg.norm(result - np.array([180, 120, 80], dtype=np.float32)) < 30)


if __name__ == "__main__":
    unittest.main()
