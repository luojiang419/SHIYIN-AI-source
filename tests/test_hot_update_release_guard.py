import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("build_hot_update", ROOT / "tools" / "build-hot-update.py")
BUILD_HOT_UPDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD_HOT_UPDATE)


def test_default_hot_update_floor_matches_current_baseline():
    assert BUILD_HOT_UPDATE.DEFAULT_HOT_UPDATE_MIN_DESKTOP_VERSION == "2.0.5"


def test_publish_guard_rejects_a_release_that_skips_connected_clients():
    status = {"clients": [{"version": "2.0.1 / 20260921151023"}, {"version": "2.0.2/20260921154055"}]}
    BUILD_HOT_UPDATE.assert_active_client_compatibility(status, "2.0.1")
    with pytest.raises(ValueError, match="2.0.1"):
        BUILD_HOT_UPDATE.assert_active_client_compatibility(status, "2.0.2")
