from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError


EXIF_ORIENTATION_TAG = 274


def normalize_image_orientation(content: bytes) -> tuple[bytes, int, int, bool]:
    """Bake EXIF orientation into image pixels while leaving upright files byte-for-byte intact."""
    try:
        with Image.open(BytesIO(content)) as source:
            image_format = str(source.format or "").upper()
            source.load()
            orientation = int(source.getexif().get(EXIF_ORIENTATION_TAG, 1) or 1)
            if orientation not in range(2, 9):
                return content, int(source.width), int(source.height), False

            normalized = ImageOps.exif_transpose(source)
            if image_format == "JPEG" and normalized.mode not in ("RGB", "L", "CMYK"):
                normalized = normalized.convert("RGB")
            exif = normalized.getexif()
            exif[EXIF_ORIENTATION_TAG] = 1
            save_options = {}
            if source.info.get("icc_profile"):
                save_options["icc_profile"] = source.info["icc_profile"]
            if len(exif):
                save_options["exif"] = exif.tobytes()
            if image_format == "JPEG":
                save_options.update(quality=95, subsampling=0, optimize=True)
            elif image_format == "WEBP":
                save_options.update(quality=95, method=4)
            elif image_format == "PNG":
                save_options.update(compress_level=6)

            output = BytesIO()
            normalized.save(output, format=image_format, **save_options)
            return output.getvalue(), int(normalized.width), int(normalized.height), True
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError(f"无法读取图片：{exc}") from exc
