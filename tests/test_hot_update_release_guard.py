import importlib.util
import marshal
from pathlib import Path
import zlib

import pytest


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("build_hot_update", ROOT / "tools" / "build-hot-update.py")
BUILD_HOT_UPDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD_HOT_UPDATE)


def test_default_hot_update_floor_matches_current_baseline():
    assert BUILD_HOT_UPDATE.DEFAULT_HOT_UPDATE_MIN_DESKTOP_VERSION == "2.0.6"


def test_publish_guard_rejects_a_release_that_skips_connected_clients():
    status = {"clients": [{"version": "2.0.1 / 20260921151023"}, {"version": "2.0.2/20260921154055"}]}
    BUILD_HOT_UPDATE.assert_active_client_compatibility(status, "2.0.1")
    with pytest.raises(ValueError, match="2.0.1"):
        BUILD_HOT_UPDATE.assert_active_client_compatibility(status, "2.0.2")


def test_try_on_depth_guard_rejects_overlay_missing_helpers():
    base = compile("async def prepare_universal_pose_depth(snapshot):\n    return snapshot\n", "main.py", "exec")
    overlay = "async def prepare_universal_pose_depth(snapshot):\n    return await render_try_on_depth('pose.png', {})\n"
    wrapper = compile(
        "import marshal as _m, zlib as _z\n"
        f"exec(_m.loads(_z.decompress({zlib.compress(marshal.dumps(base))!r})))\n"
        f"exec(compile({overlay!r}, 'main', 'exec'))\n",
        "main.py", "exec",
    )
    assert not BUILD_HOT_UPDATE.try_on_depth_helpers_available(wrapper)


def test_try_on_depth_guard_accepts_overlay_with_helpers():
    module = compile(
        "def adjust_try_on_depth(content, controls):\n    return content\n"
        "async def render_try_on_depth(path, settings):\n    return adjust_try_on_depth(b'x', {})\n"
        "async def prepare_universal_pose_depth(snapshot):\n    return await render_try_on_depth('pose.png', {})\n",
        "main.py", "exec",
    )
    assert BUILD_HOT_UPDATE.try_on_depth_helpers_available(module)
