from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from canvas_core.person_depth_components import PersonDepthComponentManager


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_root", type=Path)
    parser.add_argument(
        "--component-root",
        type=Path,
        default=PROJECT_ROOT / "data" / "system" / "components" / "person-depth",
    )
    parser.add_argument("--accept-noncommercial-license", action="store_true")
    args = parser.parse_args()
    if not args.accept_noncommercial_license:
        parser.error("--accept-noncommercial-license is required for Depth Anything V2 Large")

    candidate_root = args.candidate_root.resolve()
    manifest = json.loads((candidate_root / "candidate-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("release_status") != "candidate" or manifest.get("enabled") is not False:
        raise RuntimeError("local installer only accepts a disabled candidate manifest")
    packages = {
        str(package["id"]): candidate_root / str(package["local_file"])
        for package in manifest.get("packages") or []
    }
    manager = PersonDepthComponentManager(args.component_root, manifest=manifest)
    manager.install_local_archives(packages)

    reloaded = PersonDepthComponentManager(args.component_root)
    status = reloaded.status()
    if not status.get("ready"):
        raise RuntimeError(str(status.get("error") or "local component did not survive manager reload"))
    print(
        json.dumps(
            {
                "ok": True,
                "version": status["version"],
                "state": status["state"],
                "source_label": status["source_label"],
                "component_root": str(args.component_root.resolve()),
                "manifest": str(reloaded.manifest_path),
                "installation": str(reloaded.installation_path()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
