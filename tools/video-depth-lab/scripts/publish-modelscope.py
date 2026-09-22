"""发布深度批量工具，公开回读通过后激活；可清理已确认错误的旧版本。"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from modelscope.hub.api import HubApi

REPO = 'jiangjiang419/SHIYIN-Depth-Batch'
ROOT = Path(__file__).resolve().parents[1]
OBSOLETE = [f'releases/{v}/SHIYIN-Depth-Batch-Setup-{v}.exe' for v in ('1.0.1', '1.0.2', '1.0.3')]
OBSOLETE += [f'updates/{v}/SHIYIN-Depth-Batch-Update-{v}.shiyin-update' for v in
             ('20260922102509', '20260922103240', '20260922105200', '20260922105810')]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def url(path):
    return f'https://modelscope.cn/api/v1/models/{REPO}/repo?' + urllib.parse.urlencode(
        {'Revision': 'master', 'FilePath': path})


def verify_public(path, expected):
    request = urllib.request.Request(url(path), headers={'Range': 'bytes=0-', 'Cache-Control': 'no-cache'})
    checksum, size = hashlib.sha256(), 0
    with urllib.request.urlopen(request, timeout=120) as response:
        while chunk := response.read(1024 * 1024):
            checksum.update(chunk)
            size += len(chunk)
    if size != expected.stat().st_size or checksum.hexdigest() != digest(expected):
        raise RuntimeError(f'公开文件校验失败：{path}')
    print(f'公开校验通过：{path} ({size} bytes)', flush=True)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('installer', type=Path)
    parser.add_argument('--remove-obsolete', action='store_true', help='清理固定清单内的 7 个错误版本文件')
    parser.add_argument('--cleanup-checkout', type=Path, help='用于普通 Git 删除提交的已认证魔搭仓库副本')
    parser.add_argument('--cleanup-only', action='store_true', help='继续已发布版本的清理，核对远端哈希与当前清单')
    args = parser.parse_args()
    snapshot = args.snapshot.resolve(strict=True)
    installer = args.installer.resolve(strict=True)
    app_version = json.loads((ROOT / 'package.json').read_text('utf-8'))['version']
    if installer.name != f'SHIYIN-Depth-Batch-Setup-{app_version}.exe':
        raise ValueError('安装包名称与当前软件版本不匹配')
    envelope = json.loads((snapshot / 'catalog.json').read_text('utf-8'))
    key = bytes.fromhex((ROOT / 'src-tauri/distribution-public-key.hex').read_text().strip())
    if envelope['public_key'] != key.hex():
        raise ValueError('更新签名公钥不匹配')
    Ed25519PublicKey.from_public_bytes(key).verify(bytes.fromhex(envelope['signature']), envelope['payload'].encode())
    manifest = json.loads(envelope['payload'])
    if manifest['product'] != 'depth-batch' or manifest['version'] != snapshot.name:
        raise ValueError('更新产品或版本不匹配')
    package = snapshot / manifest['package']['name']
    if digest(package) != manifest['package']['sha256'] or package.stat().st_size != manifest['package']['size']:
        raise ValueError('更新包哈希或长度不符')
    with zipfile.ZipFile(package) as archive:
        for entry in manifest['files']:
            payload = archive.read(entry['path'])
            if len(payload) != entry['size'] or hashlib.sha256(payload).hexdigest() != entry['sha256']:
                raise ValueError(f"更新文件校验失败：{entry['path']}")
    api = HubApi()
    before = api.get_model_files(REPO, recursive=True)
    if not (snapshot / 'remote-before.json').exists():
        (snapshot / 'remote-before.json').write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding='utf-8')
    installer_path = f'releases/{app_version}/{installer.name}'
    package_path = f"updates/{manifest['version']}/{package.name}"
    remote_hashes = {item['Path']: item.get('Sha256') for item in before}
    for local, remote in ((installer, installer_path), (package, package_path)):
        if args.cleanup_only:
            if remote_hashes.get(remote) != digest(local):
                raise ValueError('远端发布文件与本地不一致，不能继续清理')
            continue
        if remote_hashes.get(remote) != digest(local):
            api.upload_file(path_or_fileobj=str(local), path_in_repo=remote, repo_id=REPO,
                            commit_message=f'发布 {app_version} 修复版本文件', disable_tqdm=True)
        verify_public(remote, local)
    readme = ROOT / 'MODELSCOPE_README.md'
    activation = snapshot / 'activation'
    (activation / 'public').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(snapshot / 'catalog.json', activation / 'public/catalog.json')
    shutil.copyfile(readme, activation / 'README.md')
    if not args.cleanup_only:
        api.upload_folder(repo_id=REPO, folder_path=str(activation),
                          allow_patterns=['public/catalog.json', 'README.md'],
                          commit_message=f'启用 {app_version} 签名更新与安装说明')
    verify_public('public/catalog.json', snapshot / 'catalog.json')
    verify_public('README.md', readme)
    cleanup_record = snapshot / 'remote-cleanup.json'
    removed = json.loads(cleanup_record.read_text('utf-8')).get('deleted_files', []) if cleanup_record.exists() else []
    if args.remove_obsolete:
        existing = {item['Path'] for item in before if item['Type'] == 'blob'}
        targets = [path for path in OBSOLETE if path in existing]
        if targets:
            if args.cleanup_checkout is None:
                raise ValueError('清理旧版本需要 --cleanup-checkout 指定仓库副本')
            checkout = args.cleanup_checkout.resolve(strict=True)
            def git(*arguments):
                return subprocess.check_output(['git', '-C', str(checkout), *arguments], encoding='utf-8').strip()
            remote = urllib.parse.urlparse(git('remote', 'get-url', 'origin'))
            repo_path = remote.path.removesuffix('.git').strip('/').removeprefix('models/')
            if remote.hostname not in ('modelscope.cn', 'www.modelscope.cn') or repo_path != REPO:
                raise ValueError('清理副本的 origin 不属于目标魔搭仓库')
            if git('status', '--porcelain'):
                raise ValueError('清理副本存在未提交修改')
            git('fetch', '--quiet', 'origin')
            git('merge', '--ff-only', 'origin/master')
            tracked = set(git('ls-files', 'releases', 'updates').splitlines())
            if not set(targets).issubset(tracked):
                raise ValueError('已核实旧文件与 Git 副本不一致')
            git('rm', '--', *targets)
            git('commit', '-m', 'release: remove seven broken depth-batch release artifacts')
            git('push', 'origin', 'HEAD:master')
            result = {'deleted_files': targets, 'failed_files': [], 'commit': git('rev-parse', 'HEAD')}
            (snapshot / 'remote-cleanup.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            removed = result['deleted_files']
        expected = {installer_path, package_path, 'public/catalog.json', 'README.md', 'configuration.json'}
        for attempt in range(4):
            after = api.get_model_files(REPO, recursive=True)
            remaining = {item['Path'] for item in after if item['Type'] == 'blob'}
            if not remaining.intersection(OBSOLETE) and expected.issubset(remaining):
                break
            time.sleep(2 ** attempt)
        else:
            raise RuntimeError('清理后远端文件列表异常')
        (snapshot / 'remote-after.json').write_text(json.dumps(after, ensure_ascii=False, indent=2), encoding='utf-8')
    report = {'repo': REPO, 'app_version': app_version, 'release': manifest['version'],
              'installer': installer_path, 'installer_sha256': digest(installer),
              'package': package_path, 'package_sha256': digest(package), 'removed': removed}
    (snapshot / 'publication.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
