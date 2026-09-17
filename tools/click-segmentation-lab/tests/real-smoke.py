from __future__ import annotations

import io
import sys
from pathlib import Path

import requests
from PIL import Image


def main() -> None:
    image_path = Path(sys.argv[1])
    with image_path.open("rb") as handle:
        upload = requests.post("http://127.0.0.1:8791/api/images", files={"image": (image_path.name, handle)}, timeout=60)
    upload.raise_for_status()
    metadata = upload.json()
    request = {
        "session_id": metadata["session_id"],
        "points": [{"x": metadata["width"] / 2, "y": metadata["height"] / 2, "label": 1}],
        "threshold": 0.5,
        "feather": 1.5,
    }
    segmented = requests.post("http://127.0.0.1:8791/api/segment", json=request, timeout=900)
    segmented.raise_for_status()
    exported = requests.post("http://127.0.0.1:8791/api/export/cutout", json=request, timeout=900)
    exported.raise_for_status()
    with Image.open(io.BytesIO(exported.content)) as result:
        assert result.size == (metadata["width"], metadata["height"])
        assert result.mode == "RGBA"
        extrema = result.getchannel("A").getextrema()
        assert extrema[1] > 0
    print({"input": str(image_path), "size": result.size, "alpha_extrema": extrema})


if __name__ == "__main__":
    main()
