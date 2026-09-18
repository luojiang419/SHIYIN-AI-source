"""Publish a signed hot-update snapshot to the public ModelScope update repository."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from modelscope.hub.api import HubApi

ROOT = Path(__file__).resolve().parents[1]
DATA = Path('D:/SHIYIN-Distribution')
REPOSITORY = 'jiangjiang419/shiyingai-updates'


def sha256(path: Path) -> str:
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def file_url(path: str) -> str:
    return f'https://modelscope.cn/api/v1/models/{REPOSITORY}/repo?Revision=master&FilePath={path}'


def read_public(path: str, expected: Path) -> None:
    request = urllib.request.Request(file_url(path), headers={'Range': 'bytes=0-'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=120) as response:
        target = expected.with_suffix(expected.suffix + '.remote-check')
        with target.open('wb') as handle:
            while chunk := response.read(1024 * 1024):
                handle.write(chunk)
    try:
        if target.stat().st_size != expected.stat().st_size or sha256(target) != sha256(expected):
            raise ValueError(f'ModelScope 匿名回读校验失败：{path}')
    finally:
        target.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('snapshot', type=Path, help='包含 manifest.json 和 .shiyin-update 的构建目录')
    parser.add_argument('--repo', default=REPOSITORY)
    args = parser.parse_args()
    snapshot = args.snapshot.resolve(strict=True)
    manifest = json.loads((snapshot / 'manifest.json').read_text('utf-8-sig'))
    version = str(manifest['version'])
    package = snapshot / manifest['package']['name']
    if not package.is_file() or sha256(package) != manifest['package']['sha256']:
        raise ValueError('本地增量包缺失或哈希不符')
    key = Ed25519PrivateKey.from_private_bytes((DATA / 'signing-key').read_bytes())
    payload = json.dumps(manifest, ensure_ascii=False, separators=(',', ':'))
    plan_payload = json.dumps({'protocol_version': 1, 'target_version': version}, separators=(',', ':'))
    public_key = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    envelope = json.dumps({'payload': payload, 'signature': key.sign(payload.encode()).hex(),
                           'public_key': public_key, 'plan_payload': plan_payload,
                           'plan_signature': key.sign(plan_payload.encode()).hex()}, separators=(',', ':'))
    api = HubApi()
    release_path = f'releases/{version}/{package.name}'
    api.upload_file(path_or_fileobj=str(package), path_in_repo=release_path, repo_id=args.repo,
                    commit_message=f'publish hot update {version}', disable_tqdm=False)
    read_public(release_path, package)
    api.upload_file(path_or_fileobj=envelope.encode(), path_in_repo='public/catalog.json', repo_id=args.repo,
                    commit_message=f'activate hot update {version}', disable_tqdm=True)
    print(json.dumps({'repo': args.repo, 'version': version, 'package': release_path,
                      'sha256': manifest['package']['sha256'], 'catalog': file_url('public/catalog.json')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
