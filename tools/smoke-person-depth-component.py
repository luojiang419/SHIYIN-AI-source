from __future__ import annotations

import argparse
import functools
import hashlib
import http.server
import json
import sys
import tempfile
import threading
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from canvas_core.person_depth_components import PersonDepthComponentManager
from canvas_core.person_depth_client import PersonDepthWorkerClient


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_root", type=Path)
    parser.add_argument("--sample", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--bit-depth", type=int, choices=(8, 16), default=16)
    args = parser.parse_args()
    if bool(args.sample) != bool(args.output_dir):
        parser.error("--sample and --output-dir must be provided together")
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
            if args.sample and args.output_dir:
                source_path = args.sample.resolve()
                if not source_path.is_file():
                    raise FileNotFoundError(source_path)
                output_dir = args.output_dir.resolve()
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / f"{source_path.stem}_person_depth_{args.bit_depth}bit.png"
                trace_path = output_dir / "trace-manifest.json"
                if output_path.exists() or trace_path.exists():
                    raise FileExistsError("sample regression output already exists")
                source_content = source_path.read_bytes()
                started = time.perf_counter()
                client = PersonDepthWorkerClient(manager)
                try:
                    depth = client.estimate(source_content, bit_depth=args.bit_depth)
                finally:
                    client.close()
                elapsed_ms = round((time.perf_counter() - started) * 1000)
                output_path.write_bytes(depth.content)
                trace = {
                    "schema_version": 1,
                    "component": "person-depth",
                    "component_version": manifest["version"],
                    "source": {
                        "name": source_path.name,
                        "size": len(source_content),
                        "sha256": hashlib.sha256(source_content).hexdigest(),
                        "width": depth.width,
                        "height": depth.height,
                    },
                    "models": manifest.get("model_sources") or {},
                    "parameters": {
                        "bit_depth": depth.bit_depth,
                        "depth_input_size": 1078,
                        "mask_input_size": 1024,
                        "foreground_percentiles": [1.0, 99.0],
                        "mask_alpha_range": [0.03, 0.95],
                        "depth_direction": "near-white",
                        "background_value": 0,
                    },
                    "runtime": {
                        "worker": result["worker"],
                        "elapsed_ms": elapsed_ms,
                    },
                    "output": {
                        "file": output_path.name,
                        "size": len(depth.content),
                        "sha256": hashlib.sha256(depth.content).hexdigest(),
                        "width": depth.width,
                        "height": depth.height,
                        "bit_depth": depth.bit_depth,
                    },
                }
                trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                result["sample"] = {
                    "output": str(output_path),
                    "trace_manifest": str(trace_path),
                    "elapsed_ms": elapsed_ms,
                }
            print(json.dumps(result, ensure_ascii=False))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
