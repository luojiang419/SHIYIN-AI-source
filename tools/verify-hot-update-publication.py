"""从客户端目录验证热更新签名、发布版本与整包下载 SHA-256。"""
import argparse
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
import requests


def verify(snapshot: Path, url: str):
    expected = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    client = requests.Session()
    client.trust_env = False
    client.headers.update({"X-Shiyin-Version": "2.0.5/20260922173125", "X-Shiyin-Capabilities": "package-v3,fast-extract-v1"})
    response = client.get(url.rstrip("/") + "/v1/catalog", timeout=15)
    response.raise_for_status()
    envelope = response.json()
    key = Ed25519PublicKey.from_public_bytes(bytes.fromhex((Path(__file__).resolve().parents[1] / "src-tauri/distribution-public-key.hex").read_text().strip()))
    key.verify(bytes.fromhex(envelope["signature"]), envelope["payload"].encode())
    manifest = json.loads(envelope["payload"])
    assert manifest["version"] == expected["version"]
    assert manifest["min_desktop_version"] == "2.0.5"
    if envelope.get("plan_payload"):
        key.verify(bytes.fromhex(envelope["plan_signature"]), envelope["plan_payload"].encode())
        assert json.loads(envelope["plan_payload"])["target_version"] == expected["version"]
    package = manifest["package"]
    assert package["sha256"] == expected["package"]["sha256"]
    digest = hashlib.sha256()
    size = 0
    with client.get(url.rstrip("/") + "/v1/blobs/" + package["sha256"], timeout=30, stream=True) as download:
        download.raise_for_status()
        for chunk in download.iter_content(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    assert digest.hexdigest() == package["sha256"] and size == package["size"]
    result = {"version": manifest["version"], "signature_verified": True, "download_sha256_verified": True, "bytes": size, "sha256": digest.hexdigest(), "files": len(manifest["files"]), "url": url}
    (snapshot / "publication-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--url", default="http://192.168.0.24:3011")
    args = parser.parse_args()
    verify(args.snapshot.resolve(), args.url)
