import unittest

from PIL import Image, ImageDraw

from canvas_core.grid_crop import detect_grid


def collage(rows, cols, cell_w=120, cell_h=96, gap=8):
    width = cols * cell_w + (cols - 1) * gap
    height = rows * cell_h + (rows - 1) * gap
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    palette = ["#d84a4a", "#467bd8", "#47a568", "#d89b43", "#7c57c9", "#34a7a0"]
    for row in range(rows):
        for col in range(cols):
            x = col * (cell_w + gap)
            y = row * (cell_h + gap)
            draw.rectangle((x, y, x + cell_w - 1, y + cell_h - 1), fill=palette[(row * cols + col) % len(palette)])
    return image


class GridCropDetectionTests(unittest.TestCase):
    def test_detects_three_by_two_collage(self):
        result = detect_grid(collage(3, 2))
        self.assertEqual((result.rows, result.cols), (3, 2))
        self.assertGreaterEqual(result.confidence, 0.5)

    def test_detects_four_by_three_collage(self):
        result = detect_grid(collage(4, 3, gap=6))
        self.assertEqual((result.rows, result.cols), (4, 3))

    def test_detects_single_axis_portrait_strip(self):
        result = detect_grid(collage(3, 1))
        self.assertEqual((result.rows, result.cols), (3, 1))

    def test_plain_image_is_not_guessed_as_grid(self):
        result = detect_grid(Image.new("RGB", (420, 280), "#7890a0"))
        self.assertEqual((result.rows, result.cols), (1, 1))
        self.assertEqual(result.confidence, 0.0)


if __name__ == "__main__":
    unittest.main()
