from __future__ import annotations

import re
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Iterable


_NAME_PATTERN = re.compile(r"^SHIYIN-(\d+)-\d{8}\.[^.]+$", re.IGNORECASE)
_EXPORT_LOCK = threading.Lock()


def _next_sequence(directory: Path) -> int:
    highest = 0
    for path in directory.iterdir():
        if not path.is_file():
            continue
        match = _NAME_PATTERN.match(path.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def export_generated_files(
    source_paths: Iterable[str | Path],
    output_directory: str | Path,
    *,
    generated_at: datetime | None = None,
) -> list[dict[str, str | int]]:
    directory = Path(output_directory).expanduser().resolve()
    sources = [Path(path).resolve() for path in source_paths if Path(path).is_file()]
    if not sources:
        return []
    date_part = (generated_at or datetime.now()).strftime("%Y%m%d")
    exported: list[dict[str, str | int]] = []
    with _EXPORT_LOCK:
        directory.mkdir(parents=True, exist_ok=True)
        sequence = _next_sequence(directory)
        for source in sources:
            extension = source.suffix.lower() or ".png"
            filename = f"SHIYIN-{sequence:06d}-{date_part}{extension}"
            destination = directory / filename
            shutil.copy2(source, destination)
            exported.append({"name": filename, "path": str(destination), "sequence": sequence})
            sequence += 1
    return exported
