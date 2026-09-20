"""构建可整体复制的拾影离线培训教程套件。"""
from __future__ import annotations

from html.parser import HTMLParser
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from training_tutorial_sidebar import build_sidebar, sidebar_css, sidebar_js


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT/'案例'
BATCH = CASES/'批量复刻培训-20260920'
UNIVERSAL = CASES/'全能双风格'/'imgx-20260920'
VIDEO = CASES/'视频生成培训-20260921'
OUTPUT = CASES/'拾影培训教程-20260920'
ARCHIVE = OUTPUT.with_suffix('.zip')


def inject_sidebar(path: Path, active: str, batch_href: str, universal_href: str, video_href: str) -> None:
    page = path.read_text(encoding='utf-8')
    sidebar = build_sidebar(active, batch_href, universal_href, video_href)
    if 'id="tutorialSidebar"' in page:
        raise RuntimeError(f'页面已包含教程侧栏，不能重复注入：{path}')
    page = page.replace('</style>', sidebar_css()+'</style>', 1)
    page = page.replace('<body>', '<body>'+sidebar, 1)
    page = page.replace('</body>', '<script>'+sidebar_js()+'</script></body>', 1)
    path.write_text(page, encoding='utf-8')


class LocalReferences(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, _tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if key in {'src', 'href', 'data-image'} and value:
                if not value.startswith(('http:', 'https:', '#', 'data:', 'mailto:')):
                    self.refs.append(value.split('#', 1)[0])


def verify_page(path: Path) -> None:
    parser = LocalReferences()
    parser.feed(path.read_text(encoding='utf-8'))
    missing = []
    for ref in parser.refs:
        candidate = (path.parent/ref).resolve()
        if not candidate.exists():
            missing.append(ref)
    if missing:
        raise RuntimeError(f'{path} 缺少本地资源：{missing}')


def directory_stats(path: Path) -> dict[str, int]:
    files = [item for item in path.rglob('*') if item.is_file()]
    return {'files': len(files), 'bytes': sum(item.stat().st_size for item in files)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-build', action='store_true', help='使用现有两份报告，不重新运行其构建脚本')
    args = parser.parse_args()
    if not args.skip_build:
        subprocess.run([sys.executable, str(ROOT/'tools/build-batch-training-report.py')], check=True)
        subprocess.run([sys.executable, str(ROOT/'tools/build-universal-sales-report.py'), str(UNIVERSAL)], check=True)

    staging = ROOT/'.codex-tmp'/'training-tutorial-suite'
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    shutil.copytree(BATCH, staging, dirs_exist_ok=True)
    universal_output = staging/'全能模式'
    shutil.copytree(UNIVERSAL, universal_output)
    shutil.copy2(universal_output/'实测论述报告.html', universal_output/'index.html')

    subprocess.run([sys.executable, str(ROOT/'tools/build-video-generation-training.py')], check=True)
    video_output = staging/'视频生成'
    shutil.copytree(VIDEO, video_output)
    inject_sidebar(staging/'index.html', 'batch', 'index.html', '全能模式/index.html', '视频生成/index.html')
    inject_sidebar(universal_output/'index.html', 'universal', '../index.html', 'index.html', '../视频生成/index.html')
    inject_sidebar(video_output/'index.html', 'video', '../index.html', '../全能模式/index.html', 'index.html')
    (staging/'使用说明.txt').write_text(
        '拾影离线培训教程\n\n'
        '1. 将整个“拾影培训教程-20260920”文件夹复制到演示电脑。\n'
        '2. 双击根目录 index.html 打开。\n'
        '3. 使用左侧教程导航切换“批量换款”、“全能模式”和“视频生成”。\n'
        '4. 页面所需图片、视频、证据与说明均在本目录内，不需要联网。\n'
        '5. 不要只复制单个 HTML；需要分享时发送整个文件夹或 ZIP。\n',
        encoding='utf-8',
    )
    verify_page(staging/'index.html')
    verify_page(universal_output/'index.html')
    verify_page(video_output/'index.html')
    manifest = {
        'name': '拾影培训教程',
        'entry': 'index.html',
        'tutorials': [
            {'name': '批量换款', 'entry': 'index.html'},
            {'name': '全能模式', 'entry': '全能模式/index.html'},
            {'name': '视频生成', 'entry': '视频生成/index.html'},
        ],
        'portable': True,
        'stats': directory_stats(staging),
    }
    (staging/'tutorial-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    if OUTPUT.exists():
        if OUTPUT.parent != CASES or OUTPUT.name != '拾影培训教程-20260920':
            raise RuntimeError(f'拒绝替换非预期目录：{OUTPUT}')
        shutil.rmtree(OUTPUT)
    shutil.move(str(staging), str(OUTPUT))
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with zipfile.ZipFile(ARCHIVE, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for file in OUTPUT.rglob('*'):
            if file.is_file():
                archive.write(file, file.relative_to(OUTPUT.parent))
    with zipfile.ZipFile(ARCHIVE) as archive:
        broken = archive.testzip()
        if broken:
            raise RuntimeError(f'ZIP 完整性检查失败：{broken}')
    print(OUTPUT/'index.html')
    print(ARCHIVE)


if __name__ == '__main__':
    main()
