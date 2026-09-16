"""Exercise a fresh public video-depth runtime install outside user data."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from canvas_core.component_profiles import RuntimeCapabilities
from canvas_core.person_depth_components import PersonDepthComponentManager
from canvas_core.video_depth import smoke_video_depth_runtime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--component-root", type=Path, default=Path(".build/182-public-runtime-smoke"))
    args = parser.parse_args()
    manager = PersonDepthComponentManager(
        args.component_root,
        manifest_path=Path("canvas_core/video_depth_runtime_manifest.json"),
        component_name="video-depth-runtime",
        display_name="深度视频运行时",
        lan_path="video-depth-runtime",
        capability_provider=lambda: RuntimeCapabilities("windows", "x86_64", "cpu"),
        proxy_provider=lambda: {},
        smoke_runner=smoke_video_depth_runtime,
    )
    manager.set_lan_source("http://127.0.0.1:1")
    if not manager.ensure_now():
        raise RuntimeError(manager.status().get("error") or "Public runtime installation failed")
    status = manager.status()
    print({"variant": manager.selected_variant_id, "source": status["source_label"],
           "ready": status["ready"], "attempts": status["attempts"]})


if __name__ == "__main__":
    main()
