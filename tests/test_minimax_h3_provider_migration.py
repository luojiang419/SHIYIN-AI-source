"""已有客户端的平台名称迁移，覆盖所有画布共用的配置加载入口。"""
from unittest.mock import patch

import main


def test_saved_h3_provider_name_migrates_without_changing_connection_or_selection():
    saved = {
        "id": "minimax-h3",
        "name": "MiniMax H3",
        "base_url": "https://cp.compshare.cn",
        "protocol": "minimax-h3",
        "enabled": True,
        "video_models": ["MiniMax-H3"],
    }
    with patch.object(main.ADMIN_DATABASE, "load_providers", return_value=[saved]):
        loaded = main.load_api_providers()
    provider = next(item for item in loaded if item["id"] == saved["id"])
    assert provider["name"] == "优云智算 MiniMax H3"
    for field in ("id", "base_url", "protocol", "enabled", "video_models"):
        assert provider[field] == saved[field]
    assert saved["name"] == "MiniMax H3"
    migrated = main.merge_default_api_providers(loaded)
    assert next(item for item in migrated if item["id"] == saved["id"]) == provider


def test_disabled_h3_provider_stays_disabled_after_name_migration():
    loaded = main.merge_default_api_providers([
        {"id": "minimax-h3", "name": "MiniMax H3", "enabled": False},
    ])
    provider = next(item for item in loaded if item["id"] == "minimax-h3")
    assert provider["name"] == "优云智算 MiniMax H3"
    assert provider["enabled"] is False
