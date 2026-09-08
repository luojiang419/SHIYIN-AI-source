"""可灵官方自包含包与独立 Node：构建和客户端共用，无需 npm。"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import shutil
import tarfile
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from canvas_core.paths import APP_PATHS

CLI_VERSION = "0.1.3"
NODE_VERSION = "22.23.2"
NODE_SHA256 = "1177b4137ba5adaa56354ae40f1080c7450e8ae09cecb47da459d1c52ac99f97"
CLI_INTEGRITY = {
    "china": ("cli-cn", "schksAOdI/Vafbe6rTxHERJ76nqqIByE2gLg7mYnV9lqtd6jzooEhUKnh29UfimWNouM26PEtc34c/f2+VJtyQ=="),
    "global": ("cli-global", "RAfuf0aNsiXjw+67i568fYzt44qtwoTvAl8Ulh40eCE2CEQHxWWqpM3t7fvSAklsqXGnUVigzd0ahmWzpjpI3g=="),
}
_PREPARE_LOCK = threading.Lock()


def runtime_root() -> Path:
    return APP_PATHS.data_root / "system" / "components" / "kling-cli"


def bundled_root() -> Path:
    return APP_PATHS.app_root / "runtime" / "kling"


def selected_region() -> str:
    try:
        region = json.loads((runtime_root() / "region.json").read_text(encoding="utf-8"))["region"]
        return region if region in CLI_INTEGRITY else ""
    except (OSError, ValueError, KeyError, TypeError):
        return ""


def select_region(region: str) -> None:
    if region not in CLI_INTEGRITY:
        raise RuntimeError("可灵账号区域必须是 china 或 global。")
    root = runtime_root()
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=root, delete=False) as stream:
        json.dump({"region": region}, stream)
        temp = Path(stream.name)
    try:
        temp.replace(root / "region.json")
    finally:
        temp.unlink(missing_ok=True)


def cli_entry(root: Path, region: str) -> Path:
    return root / f"{region}-{CLI_VERSION}" / "package" / "dist" / "cli.js"


def node_entry(root: Path) -> Path:
    return root / f"node-{NODE_VERSION}-win-x64" / "node.exe"


def find_runtime(region: str) -> tuple[str, str]:
    roots = (runtime_root(), bundled_root())
    entry = next((cli_entry(root, region) for root in roots if cli_entry(root, region).is_file()), None)
    node = next((node_entry(root) for root in roots if os.name == "nt" and node_entry(root).is_file()), None)
    return str(node) if node else "", str(entry) if entry else ""


def _download(url: str, destination: Path, algorithm: str, expected: bytes) -> None:
    digest = hashlib.new(algorithm)
    size = 0
    deadline = time.monotonic() + 300
    # urllib 支持系统代理/环境代理；不使用构建机的 npm 配置或执行包脚本。
    with urllib.request.urlopen(url, timeout=45) as response, destination.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            if time.monotonic() > deadline:
                raise RuntimeError("可灵组件下载超时，请检查网络后重试。")
            size += len(chunk)
            if size > 100 * 1024 * 1024:
                raise RuntimeError("可灵组件下载大小超出预期。")
            digest.update(chunk)
            output.write(chunk)
    if digest.digest() != expected:
        raise RuntimeError("可灵组件校验失败，请重试；未启用下载内容。")


def _unpack_cli(archive: Path, target: Path) -> None:
    total = 0
    with tarfile.open(archive, "r:gz") as package:
        for member in package.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or "\\" in member.name or ":" in member.name or not path.parts or path.parts[0] != "package":
                raise RuntimeError("可灵组件包含非法路径。")
            if member.isdir():
                continue
            if not member.isfile():
                raise RuntimeError("可灵组件包含不支持的文件类型。")
            total += member.size
            if total > 10 * 1024 * 1024:
                raise RuntimeError("可灵组件解压大小超出预期。")
            destination = target.joinpath(*path.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with package.extractfile(member) as source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)
    metadata = json.loads((target / "package" / "package.json").read_text(encoding="utf-8"))
    if metadata.get("version") != CLI_VERSION or metadata.get("dependencies"):
        raise RuntimeError("可灵组件版本或依赖与锁定配置不匹配。")
    if not (target / "package" / "dist" / "cli.js").is_file():
        raise RuntimeError("可灵组件缺少启动入口。")


def prepare_runtime(root: Path, regions: tuple[str, ...], *, include_node: bool = True, repair: bool = False) -> None:
    """仅在完整下载、校验与解包之后原子发布目录，失败不污染已就绪版本。"""
    if not regions or any(region not in CLI_INTEGRITY for region in regions):
        raise RuntimeError("可灵账号区域必须是 china 或 global。")
    with _PREPARE_LOCK:
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".prepare-", dir=root) as temporary:
            staging = Path(temporary)
            if include_node and (repair or not node_entry(root).is_file()):
                archive = staging / "node.zip"
                _download(
                    f"https://nodejs.org/dist/v{NODE_VERSION}/node-v{NODE_VERSION}-win-x64.zip",
                    archive, "sha256", bytes.fromhex(NODE_SHA256),
                )
                node_dir = staging / "node"
                node_dir.mkdir()
                with zipfile.ZipFile(archive) as package:
                    for name in ("node.exe", "LICENSE"):
                        with package.open(f"node-v{NODE_VERSION}-win-x64/{name}") as source, (node_dir / name).open("wb") as output:
                            shutil.copyfileobj(source, output)
                _publish_directory(node_dir, node_entry(root).parent)
            for region in regions:
                if not repair and cli_entry(root, region).is_file():
                    continue
                name, integrity = CLI_INTEGRITY[region]
                archive = staging / f"{region}.tgz"
                _download(f"https://registry.npmjs.org/@klingai/{name}/-/{name}-{CLI_VERSION}.tgz",
                          archive, "sha512", base64.b64decode(integrity))
                package_dir = staging / region
                package_dir.mkdir()
                _unpack_cli(archive, package_dir)
                _publish_directory(package_dir, cli_entry(root, region).parents[2])


def _publish_directory(staging: Path, target: Path) -> None:
    # 修复缺文件的旧组件；仅移动本组件目录，失败还原，旧副本由本次临时目录清理。
    previous = staging.with_name(staging.name + "-previous")
    if target.exists():
        target.replace(previous)
    try:
        staging.replace(target)
    except OSError:
        if previous.exists():
            previous.replace(target)
        raise


def ensure_runtime(region: str, *, repair: bool = False) -> tuple[str, str]:
    if region not in CLI_INTEGRITY:
        raise RuntimeError("可灵账号区域必须是 china 或 global。")
    node, entry = find_runtime(region)
    if node and entry and not repair:
        return node, entry
    supported_windows = os.name == "nt" and platform.machine().lower() in {"amd64", "x86_64"}
    if not supported_windows:
        node = shutil.which("node") or ""
        if not node:
            raise RuntimeError("当前免安装组件支持 Windows x64；此平台请提供 Node.js 18+，无需 npm。")
    if repair or not entry or not node:
        prepare_runtime(runtime_root(), (region,), include_node=supported_windows and (repair or not node), repair=repair)
    managed_node, entry = find_runtime(region)
    return managed_node or node, entry
