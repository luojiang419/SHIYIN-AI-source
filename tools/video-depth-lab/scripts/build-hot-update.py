"""构建供独立分发中心导入的 SHIYIN-Depth-Batch 签名增量包快照。"""
import argparse, hashlib, json, shutil, time, zipfile
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
INCLUDE = ('SHIYIN-Depth-Batch.exe', 'worker', 'worker-overlays', 'scripts/prepare-components.ps1', 'runtime-manifest.json', 'model-download-manifest.json', 'PORTABLE.md')

def digest(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', default=time.strftime('%Y%m%d%H%M%S'))
    parser.add_argument('--notes', default='功能优化与问题修复')
    parser.add_argument('--signing-key', default='D:/SHIYIN-Distribution/signing-key')
    args = parser.parse_args()
    if len(args.version) != 14 or not args.version.isdigit(): raise ValueError('更新版本必须是14位时间序号')
    stage = PROJECT / '.build' / 'depth-batch-installer-stage'
    if not stage.is_dir(): raise RuntimeError('请先运行 npm run installer:build 生成安装器暂存文件')
    snapshot = PROJECT / 'dist' / 'depth-batch-hot-update' / args.version
    if snapshot.exists(): raise RuntimeError(f'更新快照已存在：{snapshot}')
    files_root = snapshot / 'files'; files_root.mkdir(parents=True)
    files = []
    for item in INCLUDE:
        source = stage / item
        if source.is_file(): paths = [source]
        elif source.is_dir(): paths = [path for path in source.rglob('*') if path.is_file() and '__pycache__' not in path.parts]
        else: raise RuntimeError(f'安装器暂存文件缺失：{source}')
        for path in paths:
            rel = path.relative_to(stage)
            target = files_root / rel; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, target)
            files.append({'path': rel.as_posix(), 'size': path.stat().st_size, 'sha256': digest(path)})
    package_name = f'SHIYIN-Depth-Batch-Update-{args.version}.shiyin-update'
    package = snapshot / package_name
    with zipfile.ZipFile(package, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for item in files: archive.write(files_root / item['path'], item['path'])
    manifest = {'protocol_version': 3, 'product': 'depth-batch', 'version': args.version, 'notes': args.notes, 'prune_roots': [], 'files': files, 'package': {'name': package_name, 'size': package.stat().st_size, 'sha256': digest(package)}}
    payload = json.dumps(manifest, ensure_ascii=False, separators=(',', ':'))
    (snapshot / 'manifest.json').write_text(payload, encoding='utf-8')
    key_path = Path(args.signing_key)
    if not key_path.is_file() or key_path.stat().st_size != 32: raise RuntimeError('签名私钥不存在或长度无效')
    key = Ed25519PrivateKey.from_private_bytes(key_path.read_bytes())
    public_key = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    expected_public_key = (ROOT / 'src-tauri/distribution-public-key.hex').read_text('ascii').strip()
    if public_key != expected_public_key: raise RuntimeError('签名私钥与客户端内置公钥不匹配')
    catalog = {'payload': payload, 'signature': key.sign(payload.encode()).hex(), 'public_key': public_key}
    (snapshot / 'catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(json.dumps({'snapshot': str(snapshot), 'files': len(files), 'version': args.version}, ensure_ascii=False))

if __name__ == '__main__': main()
