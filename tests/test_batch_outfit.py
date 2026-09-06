import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

import main
from tests.test_pose_replicate_prompts import task_request


ROOT = Path(__file__).resolve().parent.parent
ECOMMERCE_HTML = (ROOT / "static" / "ecommerce.html").read_text(encoding="utf-8")
ECOMMERCE_JS = (ROOT / "static" / "js" / "ecommerce.js").read_text(encoding="utf-8")
BATCH_JS = (ROOT / "static" / "js" / "ecommerce-batch-outfit.js").read_text(encoding="utf-8")
BATCH_CSS = (ROOT / "static" / "css" / "ecommerce.css").read_text(encoding="utf-8")
POSE_SETTINGS_JS = (ROOT / "static" / "js" / "pose-replicate-settings.js").read_text(encoding="utf-8")
APP_SETTINGS_HTML = (ROOT / "static" / "app-settings.html").read_text(encoding="utf-8")
APP_SETTINGS_JS = (ROOT / "static" / "js" / "app-settings.js").read_text(encoding="utf-8")


def test_batch_outfit_tab_replaces_retired_ecommerce_pages():
    assert 'data-operation="batch_outfit"' in ECOMMERCE_HTML
    assert "batchOutfit:true" in ECOMMERCE_JS
    tab_positions = [ECOMMERCE_HTML.index(f'data-operation="{operation}"') for operation in ("universal", "batch_outfit", "try_on", "pose_transfer")]
    assert tab_positions == sorted(tab_positions)
    assert 'data-operation="batch_outfit"><span>02</span>' in ECOMMERCE_HTML
    assert 'data-operation="try_on"><span>03</span>' in ECOMMERCE_HTML
    for retired in ("prop_replace", "angle_change", "background_change"):
        assert retired not in ECOMMERCE_HTML
        assert retired not in ECOMMERCE_JS
    for label in ("目标图", "服装参考", "模特主体", "场景", "查看"):
        assert label in BATCH_JS


def test_batch_outfit_layout_and_work_actions_are_explicit():
    for element_id in (
        "batchOutfitControl", "batchOutfitGroups", "addBatchOutfit", "runAllBatchOutfit",
        "batchOutfitWorks", "batchOutfitDialog", "batchOutfitStyleName", "batchOutfitFileInput",
    ):
        assert f'id="{element_id}"' in ECOMMERCE_HTML
    assert "grid-template-columns:repeat(5,minmax(0,1fr))" in BATCH_CSS
    assert "aspect-ratio:var(--ec-batch-card-aspect)" in BATCH_CSS
    assert "object-fit:contain" in BATCH_CSS
    assert "--ec-batch-shadow-card" in BATCH_CSS
    assert ".ec-batch-card-shadow.one" in BATCH_CSS
    assert ".ec-batch-outfit-groups.is-single" in BATCH_CSS
    assert "justify-content:center" in BATCH_CSS
    for action in ("data-batch-download-selected", "data-batch-download-all", "data-batch-delete-selected", "data-batch-delete-all"):
        assert action in BATCH_JS
    batch_control = ECOMMERCE_HTML.split('id="batchOutfitControl"', 1)[1].split('</section>', 1)[0]
    assert "<textarea" not in batch_control


def test_batch_outfit_works_support_hover_and_fullscreen_navigation():
    for element_id in (
        "batchOutfitPreview", "batchOutfitPreviewStage", "batchOutfitPreviewImage",
        "batchOutfitPreviewTitle", "batchOutfitPreviewCount", "closeBatchOutfitPreview",
        "batchOutfitPreviewZoomOut", "batchOutfitPreviewZoomReset", "batchOutfitPreviewZoomIn",
        "batchOutfitPreviewMedia", "batchOutfitPreviewTargetImage", "batchOutfitPreviewCompareHandle",
    ):
        assert f'id="{element_id}"' in ECOMMERCE_HTML
    assert 'data-batch-work-preview' in BATCH_JS
    assert 'data-batch-work-step="-1"' in BATCH_JS
    assert 'data-batch-work-step="1"' in BATCH_JS
    assert 'data-batch-preview-step="-1"' in ECOMMERCE_HTML
    assert 'data-batch-preview-step="1"' in ECOMMERCE_HTML
    assert "function openWorkPreview()" in BATCH_JS
    assert "function stepWork(delta)" in BATCH_JS
    assert "function setPreviewZoom(value)" in BATCH_JS
    assert "function beginPreviewInteraction(event)" in BATCH_JS
    assert "function setPreviewDivider(value)" in BATCH_JS
    assert "group.inputs?.pose_reference" in BATCH_JS
    assert "setPointerCapture(event.pointerId)" in BATCH_JS
    assert "event.target.closest('button')" in BATCH_JS
    assert "['ArrowLeft','ArrowRight'].includes(event.key)" in BATCH_JS
    assert "workStageHovered:false" in BATCH_JS
    assert "workStage?.matches?.(':hover')" in BATCH_JS
    assert ".ec-batch-work-stage:hover .ec-batch-work-nav:not(:disabled)" in BATCH_CSS
    assert ".ec-batch-preview-stage .ec-batch-work-nav:not(:disabled)" in BATCH_CSS
    assert "width:100vw" in BATCH_CSS
    assert "height:100vh" in BATCH_CSS
    assert "box-sizing:border-box" in BATCH_CSS
    assert "--ec-batch-preview-scale" in BATCH_CSS
    assert ".ec-batch-preview-stage.is-panning" in BATCH_CSS
    assert ".ec-batch-preview-after-clip" in BATCH_CSS
    assert "--ec-batch-preview-divider" in BATCH_CSS
    assert ".ec-batch-preview-compare-handle" in BATCH_CSS


def test_model_settings_are_collapsed_by_default_and_remember_manual_expansion():
    assert 'id="advancedSettings" class="ec-model-panel collapsed"' in ECOMMERCE_HTML
    assert 'id="modelPanelToggle" class="ec-model-panel-toggle" type="button" aria-expanded="false"' in ECOMMERCE_HTML
    assert "modelPanelCollapsed:true" in ECOMMERCE_JS
    assert "saved.model_panel_collapsed !== false" in ECOMMERCE_JS
    assert "state.modelPanelCollapsed = !state.modelPanelCollapsed" in ECOMMERCE_JS


def test_batch_page_reuses_pose_replicate_runtime_and_shared_prompts():
    assert "/api/person-depth/component/status" in BATCH_JS
    assert "/api/person-depth/component/install" in BATCH_JS
    assert "/api/person-depth/estimate" in BATCH_JS
    assert "mode:'depth'" in BATCH_JS
    assert "batch-outfit-depth" in BATCH_JS
    assert "/api/canvas/pose-replicate-tasks" in BATCH_JS
    assert "PoseReplicateSettings.sharedPromptPolicy" in BATCH_JS
    assert "user_instruction:''" in BATCH_JS
    assert "pose_replicate_prompt_templates_v1" in POSE_SETTINGS_JS
    assert "BroadcastChannel(SHARED_CHANNEL_NAME)" in POSE_SETTINGS_JS
    assert "pose-replicate-templates-changed" in POSE_SETTINGS_JS
    assert "sharedOverridesForNode(node)" in POSE_SETTINGS_JS


def test_batch_outfit_supports_multi_garment_stack_and_independent_grid_ratio():
    assert 'id="batchOutfitFileInput" type="file" accept="image/png,image/jpeg,image/webp" multiple' in ECOMMERCE_HTML
    assert 'id="batchOutfitGridRatioField"' in ECOMMERCE_HTML
    assert 'id="batchOutfitGridRatio"' in ECOMMERCE_HTML
    assert "const TARGET_IMAGE_MAX = 20" in BATCH_JS
    assert "group.inputs.target_image = [...currentTargets, ...images]" in BATCH_JS
    assert "targetImages.map(async (targetImage, index)" in BATCH_JS
    assert "Promise.allSettled(submissions)" in BATCH_JS
    assert "data-batch-input-step" in BATCH_JS
    assert "grid_ratio:state.gridRatio" in BATCH_JS
    assert "'16:9'" in BATCH_JS


def test_batch_outfit_settings_surface_has_dedicated_directory():
    for element_id in ("batchOutfitOutputDir", "chooseBatchOutfitOutput", "resetBatchOutfitOutput"):
        assert f'id="{element_id}"' in APP_SETTINGS_HTML
    assert "batch_outfit_output_dir" in APP_SETTINGS_JS
    assert "/api/app-settings/select-batch-outfit-output-directory" in APP_SETTINGS_JS


def test_style_name_validation_blocks_traversal_and_windows_reserved_names():
    assert main.validate_batch_outfit_style_name("SS26-夹克-001") == "SS26-夹克-001"
    for invalid in ("../escape", "look\\outside", "CON", "款号."):
        with pytest.raises(ValueError):
            main.validate_batch_outfit_style_name(invalid)


def test_batch_outfit_images_archive_under_style_folder_idempotently():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / "generated.png"
        source.write_bytes(b"image-data")
        output = root / "batch-output"
        record = {"id": "history-1", "images": ["/assets/output/generated.png"]}
        context = {"group_id": "outfit_1", "style_name": "SS26-001"}
        with (
            patch.object(main, "read_app_config", return_value={"batch_outfit_output_dir": str(output)}),
            patch.object(main, "output_file_from_url", return_value=str(source)),
        ):
            first = main.archive_batch_outfit_images(record, context)
            second = main.archive_batch_outfit_images(record, context)
        assert first == second
        archived = Path(first[0]["path"])
        assert archived.parent == output / "SS26-001"
        assert archived.read_bytes() == b"image-data"
        assert first[0]["relative_path"].startswith("SS26-001/")


def test_pose_replicate_batch_context_reaches_shared_generation_pipeline():
    payload = task_request(model=True, scene=True)
    payload.batch_outfit = main.BatchOutfitContext(group_id="outfit_group_1", style_name="SS26-001")
    submit = AsyncMock(return_value={"task_id": "batch-task", "status": "queued"})
    with (
        patch.object(main, "create_canvas_image_task", submit),
        patch.object(main, "resolve_image_generation_selection", return_value={"provider_id": payload.generation.provider_id, "model": payload.generation.model}),
    ):
        asyncio.run(main.create_pose_replicate_task(payload))
    image_payload = submit.await_args.args[0]
    assert image_payload.operation == "pose_replicate"
    assert image_payload.prompt_context["batch_outfit"] == {"group_id": "outfit_group_1", "style_name": "SS26-001"}


def test_batch_delete_only_accepts_archive_paths_inside_configured_root():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        archive = root / "SS26-001" / "result.png"
        archive.parent.mkdir(parents=True)
        archive.write_bytes(b"image")
        request = main.BatchOutfitDeleteImagesRequest(
            work_ids=["work-1"],
            archive_paths=["SS26-001/result.png", "../outside.png"],
        )
        with (
            patch.object(main, "batch_outfit_output_root", return_value=root),
            patch.object(main, "all_works_with_canvas", return_value=[{"id": "work-1"}]),
            patch.object(main, "_delete_selected_work_files", return_value={"deleted_files": 1, "deleted_records": 1, "file_errors": []}),
        ):
            result = asyncio.run(main.delete_batch_outfit_images(request))
        assert not archive.exists()
        assert result["deleted_archives"] == 1
        assert result["deleted_work_files"] == 1
        assert result["success"] is False
        assert any("超出" in item["error"] for item in result["errors"])
