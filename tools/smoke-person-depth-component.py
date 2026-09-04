from __future__ import annotations

import argparse
import functools
import http.server
import json
import sys
import tempfile
import threading
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from canvas_core.person_depth_components import PersonDepthComponentManager


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_root", type=Path)
    args = parser.parse_args()
    candidate_root = args.candidate_root.resolve()
    manifest_path = candidate_root / "candidate-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    handler = functools.partial(QuietHandler, directory=str(candidate_root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        manifest["enabled"] = True
        for package in manifest["packages"]:
            package["domestic_url"] = f"http://127.0.0.1:{port}/{package['local_file']}"
            package["official_url"] = ""
        with tempfile.TemporaryDirectory(prefix="person-depth-component-smoke-") as temp_root:
            manager = PersonDepthComponentManager(Path(temp_root), manifest=manifest, proxy_provider=lambda: {})
            if not manager.ensure_now():
                raise RuntimeError(str(manager.status().get("error") or "候选组件安装失败"))
            if not manager.verify_installed(run_smoke=False):
                raise RuntimeError("候选组件安装后校验失败")
            command = manager.worker_command()
            installation = manager.installation_path()
            result = {
                "ok": True,
                "version": manifest["version"],
                "state": manager.public_status()["state"],
                "source_label": manager.public_status()["source_label"],
                "worker": str(Path(command[0]).relative_to(installation)) if installation else "",
            }
            print(json.dumps(result, ensure_ascii=False))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
