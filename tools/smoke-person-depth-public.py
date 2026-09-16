"""Exercise a fresh person-depth mirror install outside user data."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from canvas_core.person_depth_components import PersonDepthComponentManager


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--component-root", type=Path, default=Path(".build/182-public-person-smoke"))
    args = parser.parse_args()
    manager = PersonDepthComponentManager(
        args.component_root,
        manifest_path=Path("canvas_core/person_depth_manifest.json"),
        proxy_provider=lambda: {},
        smoke_runner=lambda _command, _root: None,
    )
    manager.set_lan_source("http://127.0.0.1:1")
    if not manager.ensure_now():
        raise RuntimeError(manager.status().get("error") or "Public person-depth installation failed")
    installation = manager.installation_path()
    print({"source": manager.status()["source_label"], "ready": manager.status()["ready"],
           "required_files": len(manager.manifest["required_paths"]),
           "installation": str(installation)})


if __name__ == "__main__":
    main()
