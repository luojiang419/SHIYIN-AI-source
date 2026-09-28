import asyncio
from unittest.mock import AsyncMock, patch


def test_pose_transfer_skips_automatic_review_and_completes_before_export():
    import main

    task = {"id": "pose-delivery", "status": "running"}
    route = {"provider_id": "test", "provider_name": "Test", "model": "test"}
    snapshot = {
        "operation": "pose_transfer", "mode": "standard", "options": {}, "inputs": [],
        "prompt": "pose", "route_candidates": [route], "size": "1024x1024",
        "quality": "high", "count": 1, "aspect_ratio": "2:3", "resolution": "2k",
        "parameters": {},
    }
    original = "/assets/output/original.png"
    batch = {
        "provider": {"id": "test", "name": "Test"}, "model": "test",
        "images": [original], "image_items": [{"url": original}], "raw": {},
        "generation_started_at": 1, "generation_completed_at": 2,
        "generation_elapsed_seconds": 1,
    }
    events = []

    async def passthrough(current):
        return current, None

    def save(record, export_generated_files_first=True):
        assert export_generated_files_first is False
        events.append(("indexed", record["id"], record["images"][:]))

    def export(record):
        assert task["status"] == "succeeded"
        assert events[0][0] == "indexed"
        events.append(("exported", record["id"]))

    with (patch.object(main, "current_account_task", return_value=task),
          patch.object(main, "update_ecommerce_task", side_effect=lambda _id, changes: task.update(changes)),
          patch.object(main, "enrich_ecommerce_snapshot_with_garment_analysis", new=passthrough),
          patch.object(main, "enrich_ecommerce_snapshot_with_universal_analysis", new=passthrough),
          patch.object(main, "prepare_universal_pose_depth", new=AsyncMock(return_value=([], "pose", {}))),
          patch.object(main, "prepare_universal_product_anchor", new=AsyncMock(return_value=([], "pose", {}))),
          patch.object(main, "execute_ai_image_batch", new=AsyncMock(return_value=batch)),
          patch.object(main, "apply_selected_studio_background", new=AsyncMock(return_value=batch)),
          patch.object(main, "apply_fabric_enhancement", new_callable=AsyncMock) as review,
          patch.object(main.DATABASE, "prepend_history", side_effect=lambda record, limit=5000: events.append(("updated", record["id"]))),
          patch.object(main, "save_to_history", side_effect=save),
          patch.object(main, "save_generated_images_to_user_directory", side_effect=export),
          patch.object(main, "publish_entity_changed"),
          patch.object(main, "GLOBAL_LOOP", None)):
        asyncio.run(main.execute_ecommerce_task(task["id"], snapshot))

    assert task["status"] == "succeeded", task.get("error")
    review.assert_not_awaited()
    assert task["result"]["images"] == [original]
    assert events == [("indexed", task["id"], [original]), ("exported", task["id"]), ("updated", task["id"])]
