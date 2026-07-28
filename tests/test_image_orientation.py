import unittest
from io import BytesIO

from PIL import Image

from canvas_core.image_upload import normalize_image_orientation


class ImageOrientationTests(unittest.TestCase):
    def jpeg_bytes(self, orientation=None):
        image = Image.new("RGB", (40, 20), (180, 60, 40))
        output = BytesIO()
        exif = image.getexif()
        if orientation is not None:
            exif[274] = orientation
        image.save(output, format="JPEG", quality=92, exif=exif.tobytes())
        return output.getvalue()

    def test_portrait_exif_is_baked_into_pixels(self):
        normalized, width, height, changed = normalize_image_orientation(self.jpeg_bytes(6))
        self.assertTrue(changed)
        self.assertEqual((width, height), (20, 40))
        with Image.open(BytesIO(normalized)) as image:
            self.assertEqual(image.size, (20, 40))
            self.assertIn(image.getexif().get(274, 1), (1, None))

    def test_upright_image_is_not_recompressed(self):
        source = self.jpeg_bytes(1)
        normalized, width, height, changed = normalize_image_orientation(source)
        self.assertFalse(changed)
        self.assertEqual(normalized, source)
        self.assertEqual((width, height), (40, 20))


if __name__ == "__main__":
    unittest.main()
