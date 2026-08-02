import asyncio
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from PIL import Image
from canvas_core.database import CanvasDatabase

from canvas_core.ecommerce import (
    QUALITY_CHECKS,
    build_universal_auto_instruction,
    build_model_catalog,
    build_prompt,
    parse_garment_analysis,
    parse_universal_reference_analysis,
    primary_pose_reference,
    comparison_reference,
    public_capabilities,
    resolve_generation_settings,
    route_candidates,
    safe_fallback_error,
    target_size,
    universal_composition_mode,
    validate_input_roles,
)


class EcommerceContractTests(unittest.TestCase):
    def setUp(self):
        self.providers = [
            {
                "id": "modelscope",
                "name": "ModelScope",
                "enabled": True,
                "primary": False,
                "image_models": ["Qwen/Qwen-Image-Edit-2511", "black-forest-labs/FLUX.2-klein-9B"],
            },
            {
                "id": "grsai",
                "name": "Grsai",
                "enabled": True,
                "primary": True,
                "image_models": ["nano-banana-fast", "gpt-image-2-vip", "text-only-model"],
            },
            {
                "id": "disabled",
                "enabled": False,
                "image_models": ["Qwen-Image-Edit-2511"],
            },
        ]

    def test_standard_route_uses_single_quality_priority(self):
        catalog = build_model_catalog(self.providers)
        self.assertEqual(route_candidates(catalog, "standard")[0]["model"], "gpt-image-2-vip")
        self.assertEqual(route_candidates(catalog, "preview")[0]["model"], "gpt-image-2-vip")
        self.assertEqual(route_candidates(catalog, "publish")[0]["model"], "gpt-image-2-vip")
        self.assertIn("text-only-model", [item["model"] for item in catalog])
        self.assertNotIn("disabled", [item["provider_id"] for item in catalog])

    def test_same_model_prefers_primary_provider(self):
        providers = [
            {"id": "first", "enabled": True, "primary": False, "image_models": ["gpt-image-2-vip"]},
            {"id": "preferred", "enabled": True, "primary": True, "image_models": ["gpt-image-2-vip"]},
        ]
        routes = route_candidates(build_model_catalog(providers), "standard", model="gpt-image-2-vip")
        self.assertEqual(routes[0]["provider_id"], "preferred")

    def test_gemini_3_and_nano_banana_pro_accept_fourteen_references(self):
        providers = [{
            "id": "image-provider",
            "enabled": True,
            "image_models": ["gemini-3-pro-image-preview", "nano-banana-pro-4k-vip", "nano-banana-fast"],
        }]
        limits = {item["model"]: item["max_reference_images"] for item in build_model_catalog(providers)}
        self.assertEqual(limits["gemini-3-pro-image-preview"], 14)
        self.assertEqual(limits["nano-banana-pro-4k-vip"], 14)
        self.assertEqual(limits["nano-banana-fast"], 3)

    def test_roles_prompts_and_target_resolution(self):
        try_on_inputs = [
            {"role": "source", "url": "/assets/input/person.png"},
            {"role": "garment", "url": "/assets/input/top.png"},
        ]
        self.assertEqual(len(validate_input_roles("try_on", try_on_inputs)), 2)
        prompt = build_prompt("try_on", try_on_inputs, {"garment_category": "upper"})
        self.assertIn("Change only the requested dimension", prompt)
        self.assertIn("ORDERED REFERENCE MAP", prompt)
        self.assertIn("Image 1 = [SOURCE / EDIT BASE]", prompt)
        self.assertIn("Image 2 = [GARMENT PRODUCT SOURCE]", prompt)
        self.assertIn("logo", prompt.lower())
        self.assertIn("high-fidelity fabric weave", prompt)
        self.assertIn("marketplace-ready", prompt)
        self.assertIn("SKU-level garment fidelity", prompt)
        self.assertIn("material micro-texture", prompt)
        self.assertIn("Avoid plastic or waxy skin", prompt)
        outfit_inputs = [
            {"role": "source", "url": "/assets/input/person.png"},
            {"role": "upper_garment", "url": "/assets/input/top.png", "label": "米白上装"},
            {"role": "lower_garment", "url": "/assets/input/pants.png", "label": "深色长裤"},
            {"role": "shoes", "url": "/assets/input/shoes.png"},
            {"role": "pose", "url": "/assets/input/pose.png"},
        ]
        self.assertEqual(len(validate_input_roles("try_on", outfit_inputs)), 5)
        outfit_prompt = build_prompt("try_on", outfit_inputs, {})
        self.assertIn("upper garment", outfit_prompt)
        self.assertIn("lower garment", outfit_prompt)
        self.assertIn("shoes", outfit_prompt)
        self.assertIn("natural dress-up layer order", outfit_prompt)
        self.assertIn("Use Image 5 only as the spatial / pose template", outfit_prompt)
        self.assertIn("Do not copy the pose reference person's identity", outfit_prompt)
        with self.assertRaises(ValueError):
            validate_input_roles("try_on", [{"role": "source", "url": "/assets/input/person.png"}])
        self.assertEqual(target_size(1600, 900, "standard"), "2048x1152")
        self.assertEqual(target_size(900, 1600, "standard"), "1152x2048")
        self.assertEqual(target_size(900, 1600, "preview", "4:5", "1k"), "1024x1280")
        self.assertEqual(target_size(900, 1600, "publish", "4:5", "2k"), "1632x2040")
        with self.assertRaises(ValueError):
            validate_input_roles("pose_transfer", [{"role": "source", "url": "/assets/input/person.png"}], {"pose_source": "reference"})
        with self.assertRaises(ValueError):
            validate_input_roles("background_change", [{"role": "source", "url": "/assets/input/product.png"}], {"background_mode": "reference"})

    def test_all_operation_prompts_use_listing_detail_directive(self):
        cases = {
            "try_on": (
                [{"role": "source", "url": "/assets/input/person.png"}, {"role": "garment", "url": "/assets/input/top.png"}],
                {},
            ),
            "pose_transfer": ([{"role": "source", "url": "/assets/input/person.png"}], {}),
            "prop_replace": (
                [{"role": "source", "url": "/assets/input/model.png"}, {"role": "prop", "url": "/assets/input/bag.png"}],
                {"target_description": "the handbag"},
            ),
            "angle_change": ([{"role": "source", "url": "/assets/input/product.png"}], {"azimuth": 45}),
            "background_change": (
                [{"role": "source", "url": "/assets/input/product.png"}],
                {"background_mode": "prompt", "background_prompt": "premium marble counter with soft side light"},
            ),
            "universal": (
                [{"reference_id": "detail", "reference_type": "detail", "role": "detail", "url": "/assets/input/detail.png"}],
                {},
            ),
        }
        for operation, (inputs, options) in cases.items():
            with self.subTest(operation=operation):
                prompt = build_prompt(operation, inputs, options)
                self.assertIn("marketplace-ready", prompt)
                self.assertIn("SKU-level", prompt)
                self.assertIn("material micro-texture", prompt)
                self.assertIn("clean edges", prompt)
                self.assertIn("logos", prompt)
                self.assertIn("ZOOM-READY QUALITY GATE", prompt)
                self.assertIn("Use reference pixels as evidence", prompt)
                self.assertIn("Do not denoise away weave", prompt)
                self.assertIn("NANO BANANA PRO EXECUTION", prompt)
                self.assertIn("NANO BANANA PRO MULTI-REFERENCE MAP", prompt)
                self.assertIn("COMMERCIAL PHOTO DIRECTION", prompt)
                self.assertIn("TEXT, LOGO, AND BRANDING DIRECTIVE", prompt)
                self.assertIn("4K-ready detail", prompt)

    def test_all_tabs_accept_studio_reference_lock(self):
        cases = {
            "try_on": ([{"role": "source", "url": "/assets/input/person.png"}, {"role": "garment", "url": "/assets/input/top.png"}], {}),
            "pose_transfer": ([{"role": "source", "url": "/assets/input/person.png"}], {}),
            "prop_replace": ([{"role": "source", "url": "/assets/input/model.png"}, {"role": "prop", "url": "/assets/input/bag.png"}], {"target_description": "the handbag"}),
            "angle_change": ([{"role": "source", "url": "/assets/input/product.png"}], {"azimuth": 45}),
            "background_change": ([{"role": "source", "url": "/assets/input/product.png"}], {"background_mode": "preset"}),
            "universal": ([{"reference_id": "detail", "reference_type": "detail", "role": "detail", "url": "/assets/input/detail.png"}], {}),
        }
        for operation, (inputs, options) in cases.items():
            with self.subTest(operation=operation):
                prompt = build_prompt(operation, inputs, {**options, "studio_reference": "studio_white"})
                self.assertIn("STUDIO REFERENCE LOCK", prompt)
                self.assertIn("White studio", prompt)
                self.assertIn("backdrop color family", prompt)
                self.assertIn("must not override reference-owned", prompt)
                self.assertIn("FINAL STUDIO BACKGROUND OVERRIDE", prompt)
                self.assertTrue(prompt.rstrip().endswith("selected studio."))
                if operation != "universal":
                    self.assertIn("selected studio replaces", prompt)

        pose_prompt = build_prompt(
            "pose_transfer",
            [{"role": "source", "url": "/assets/input/person.png"}],
            {"pose_source": "preset", "studio_reference": "studio_black"},
        )
        self.assertNotIn("skin texture, and background from the source image", pose_prompt)
        presets = public_capabilities(self.providers)["studio_reference_presets"]
        self.assertIn("studio_white", [item["id"] for item in presets])
        self.assertIn("studio_black", [item["id"] for item in presets])

    def test_selected_studio_overrides_universal_reference_backgrounds(self):
        references = [
            {"reference_id": "model", "reference_type": "subject", "role": "subject", "url": "/assets/input/model.png"},
            {"reference_id": "scene", "reference_type": "scene", "role": "scene", "url": "/assets/input/scene.png"},
        ]
        prompt = build_prompt("universal", references, {"studio_reference": "studio_gray"})
        self.assertIn("STUDIO BACKGROUND AUTHORITY", prompt)
        self.assertIn("selected Gray studio", prompt)
        self.assertIn("It overrides every source, base, scene, style, and background-reference environment", prompt)
        self.assertIn("Do not use, preserve, blend, or infer any reference-image background", prompt)
        self.assertIn("Scene references do not contribute background", prompt)
        self.assertIn("The selected studio is highest priority for the final background", prompt)
        self.assertNotIn("Scene references own environment appearance", prompt)

        base_transfer_prompt = build_prompt(
            "universal",
            [{"reference_id": "product", "reference_type": "detail", "role": "detail", "url": "/assets/input/product.png"}],
            {"studio_reference": "studio_black"},
        )
        self.assertIn("the selected studio exclusively owns the final background", base_transfer_prompt)
        self.assertIn("Do not preserve or reuse Image 1's background", base_transfer_prompt)

    def test_all_tabs_have_operation_specific_high_quality_locks(self):
        cases = {
            "try_on": (
                [{"role": "source", "url": "/assets/input/person.png"}, {"role": "garment", "url": "/assets/input/top.png"}],
                {},
                ("TRY-ON MATERIAL LOCK", "Warp garment reference textures", "do not repaint the garment with a generic textile"),
            ),
            "pose_transfer": (
                [{"role": "source", "url": "/assets/input/person.png"}],
                {"pose_preset": "walking"},
                ("POSE TRANSFER SOURCE LOCK", "reproject source clothing textures", "do not redesign, denoise, simplify"),
            ),
            "prop_replace": (
                [{"role": "source", "url": "/assets/input/model.png"}, {"role": "prop", "url": "/assets/input/bag.png"}],
                {"target_description": "the handbag"},
                ("PROP REPLACEMENT MATERIAL LOCK", "pixel-grounded material and branding source", "ghost fragments"),
            ),
            "angle_change": (
                [{"role": "source", "url": "/assets/input/product.png"}],
                {"azimuth": 45, "elevation": 10, "distance": "close"},
                ("ANGLE REGENERATION SKU LOCK", "never mirror or garble logos/text", "Newly visible surfaces"),
            ),
            "background_change": (
                [{"role": "source", "url": "/assets/input/product.png"}],
                {"background_mode": "prompt", "background_prompt": "premium marble counter with soft side light"},
                ("BACKGROUND REPLACEMENT FOREGROUND LOCK", "change only the environment", "do not retouch, denoise, redraw foreground"),
            ),
            "universal": (
                [{"reference_id": "detail", "reference_type": "detail", "role": "detail", "url": "/assets/input/detail.png"}],
                {},
                ("MATERIAL EVIDENCE LOCK", "pixel-grounded material fidelity", "Scene, style, pose, and model identity references must never override product material"),
            ),
        }
        for operation, (inputs, options, phrases) in cases.items():
            with self.subTest(operation=operation):
                prompt = build_prompt(operation, inputs, options)
                for phrase in phrases:
                    self.assertIn(phrase, prompt)

    def test_background_change_locks_source_framing_and_foreground_as_an_immutable_plate(self):
        prompt = build_prompt(
            "background_change",
            [{"role": "source", "url": "/assets/input/couple-half-body.png"}],
            {"background_mode": "preset", "background_preset": "studio_white"},
        )
        for phrase in (
            "IMMUTABLE FOREGROUND AND COMPOSITION LOCK",
            "exact output canvas and source aspect ratio",
            "subject count, subject size, subject placement",
            "hand and leg positions, face/gaze direction",
            "extend a half-body or close-up into a full-body image",
            "Only the environment outside the foreground silhouette may change",
            "SOURCE PHOTOGRAPHIC CHARACTER LOCK",
            "Preserve the exact hairstyle",
            "analog film grain or ISO noise",
            "Do not denoise, beauty-retouch, face-smooth, plasticize",
        ):
            self.assertIn(phrase, prompt)

    def test_single_subject_universal_studio_uses_background_only_composition_lock(self):
        source = [{
            "reference_id": "couple",
            "reference_type": "subject",
            "role": "subject",
            "url": "/assets/input/couple-half-body.png",
        }]
        studio_prompt = build_prompt("universal", source, {"studio_reference": "studio_gray"})
        plain_prompt = build_prompt("universal", source, {})
        self.assertIn("IMMUTABLE FOREGROUND AND COMPOSITION LOCK", studio_prompt)
        self.assertIn("Do not zoom out, zoom in, reframe, recrop, outpaint", studio_prompt)
        self.assertIn("SOURCE PHOTOGRAPHIC CHARACTER LOCK", studio_prompt)
        self.assertNotIn("IMMUTABLE FOREGROUND AND COMPOSITION LOCK", plain_prompt)

    def test_try_on_accepts_separate_body_identity_pose_and_detail_references(self):
        references = [
            {"role": "source", "url": "/assets/input/body.png", "label": "A 身体模特"},
            {"role": "model_identity", "url": "/assets/input/identity.png", "label": "C 模特形象"},
            {"role": "upper_garment", "url": "/assets/input/top.png", "label": "白色衬衫"},
            {"role": "detail", "url": "/assets/input/detail.png", "label": "胸前 Logo 细节"},
            {"role": "pose", "url": "/assets/input/pose.png", "label": "B 姿势"},
        ]
        normalized = validate_input_roles("try_on", references, {})
        self.assertEqual([item["role"] for item in normalized], ["source", "model_identity", "upper_garment", "detail", "pose"])
        prompt = build_prompt("try_on", references, {})
        self.assertIn("Use Image 2 only as model identity", prompt)
        self.assertIn("face, hairstyle, skin tone, makeup", prompt)
        self.assertIn("Use Image 5 only as the spatial / pose template", prompt)
        self.assertIn("Use detail references only to refine corresponding garment or product fidelity", prompt)
        self.assertIn("without changing body identity, pose, framing, or unrelated garment regions", prompt)

    def test_try_on_manual_prompt_is_used_verbatim(self):
        references = [
            {"role": "source", "reference_id": "slot_1", "url": "/assets/input/model.png", "label": "图1模特"},
            {"role": "detail", "reference_id": "slot_2", "url": "/assets/input/waist.png", "label": "图2腰头细节"},
            {"role": "detail", "reference_id": "slot_3", "url": "/assets/input/pocket.png", "label": "图3口袋细节"},
            {"role": "lower_garment", "reference_id": "slot_4", "url": "/assets/input/pants.png", "label": "图4裤子"},
        ]
        normalized = validate_input_roles("try_on", references, {})
        self.assertEqual([item["reference_id"] for item in normalized], ["slot_1", "slot_2", "slot_3", "slot_4"])
        self.assertEqual([item["role"] for item in normalized], ["source", "detail", "detail", "lower_garment"])

        instruction = "按图1的模特，图2、图3保留局部细节，图4作为裤子生成"
        prompt = build_prompt("try_on", references, {"instruction": instruction})
        self.assertEqual(prompt, instruction)

    def test_user_prompt_mode_bypasses_all_automatic_operation_rules(self):
        cases = {
            "try_on": (
                [{"role": "source", "url": "/assets/input/model.png"}, {"role": "garment", "url": "/assets/input/top.png"}],
                {"instruction": "图1穿上图2，并在白墙前拍摄"},
            ),
            "pose_transfer": (
                [{"role": "source", "url": "/assets/input/model.png"}],
                {"pose_preset": "walking", "instruction": "图1坐在沙发上"},
            ),
            "prop_replace": (
                [{"role": "source", "url": "/assets/input/model.png"}, {"role": "prop", "url": "/assets/input/bag.png"}],
                {"target_description": "the handbag", "instruction": "图1手持图2"},
            ),
            "angle_change": (
                [{"role": "source", "url": "/assets/input/model.png"}],
                {"azimuth": 90, "instruction": "图1正面近景"},
            ),
            "background_change": (
                [{"role": "source", "url": "/assets/input/model.png"}],
                {"background_preset": "outdoor_daylight", "instruction": "图1置于红色摄影棚"},
            ),
            "universal": (
                [{"reference_id": "subject", "reference_type": "subject", "role": "subject", "url": "/assets/input/model.png"}, {"reference_id": "scene", "reference_type": "scene", "role": "scene", "url": "/assets/input/scene.png"}],
                {"studio_reference": "studio_black", "instruction": "图1穿图2的同款风格服装"},
            ),
        }
        for operation, (references, options) in cases.items():
            with self.subTest(operation=operation):
                prompt = build_prompt(operation, references, options)
                self.assertEqual(prompt, options["instruction"])

    def test_free_creation_requires_and_preserves_verbatim_prompt(self):
        references = [
            {"reference_id": "subject", "reference_type": "subject", "role": "subject", "url": "/assets/input/model.png"},
            {"reference_id": "style", "reference_type": "style", "role": "style", "url": "/assets/input/style.png"},
        ]
        instruction = "  图1作为主体，完全按照图2的笔触自由创作。\n不要添加文字。  "
        prompt = build_prompt("universal", references, {"prompt_policy": "free", "instruction": instruction})
        self.assertEqual(prompt, instruction)
        self.assertNotIn("ORDERED REFERENCE MAP", prompt)
        self.assertNotIn("MATERIAL EVIDENCE LOCK", prompt)
        text_only_prompt = build_prompt("universal", [], {"prompt_policy": "free", "instruction": instruction})
        self.assertEqual(text_only_prompt, instruction)
        self.assertEqual(validate_input_roles("universal", [], {"prompt_policy": "free"}), [])
        with self.assertRaisesRegex(ValueError, "必须填写提示词"):
            build_prompt("universal", references, {"prompt_policy": "free", "instruction": "   "})
        with self.assertRaisesRegex(ValueError, "仅支持全能模式"):
            build_prompt("pose_transfer", [{"role": "source", "url": "/assets/input/model.png"}], {"prompt_policy": "free", "instruction": "自由生成"})

    def test_universal_model_identity_has_exclusive_ownership(self):
        references = [
            {"reference_id": "body", "reference_type": "subject", "role": "subject", "url": "/assets/input/body.png"},
            {"reference_id": "identity", "reference_type": "model_identity", "role": "model_identity", "url": "/assets/input/identity.png"},
            {"reference_id": "pose", "reference_type": "pose", "role": "pose", "url": "/assets/input/pose.png"},
        ]
        prompt = build_prompt("universal", references, {})
        self.assertIn("[MODEL IDENTITY]", prompt)
        self.assertIn("Use Image 2 only as the MODEL IDENTITY reference", prompt)
        self.assertIn("Model identity references own face, hair, skin tone", prompt)
        self.assertIn("they do not own body proportions, pose, clothing", prompt)
        self.assertIn("the primary pose reference as highest-priority spatial authority", prompt)

    def test_generation_parameter_defaults_and_overrides(self):
        standard = resolve_generation_settings(1600, 900, "standard")
        self.assertEqual((standard["size"], standard["quality"], standard["count"]), ("2048x1152", "high", 1))
        custom = resolve_generation_settings(1600, 900, "standard", "4:5", "4k", "low", 3)
        self.assertEqual(custom["size"], "2560x3200")
        self.assertEqual(custom["resolution"], "4k")
        self.assertEqual(custom["quality"], "low")
        self.assertEqual(custom["count"], 3)
        with self.assertRaises(ValueError):
            resolve_generation_settings(1600, 900, "preview", "5:7")

    def test_universal_prompt_assigns_each_reference_an_exclusive_role(self):
        references = [
            {"reference_id": "model", "reference_type": "subject", "role": "subject", "url": "/assets/input/1.png", "label": "模特"},
            {"reference_id": "outfit", "reference_type": "full_garment", "role": "full_garment", "url": "/assets/input/2.png", "label": "蓝色连衣裙"},
            {"reference_id": "shoes", "reference_type": "shoes", "role": "shoes", "url": "/assets/input/3.png", "label": "运动鞋"},
            {"reference_id": "necklace", "reference_type": "accessory", "role": "accessory", "url": "/assets/input/4.png", "label": "项链"},
            {"reference_id": "pose", "reference_type": "pose", "role": "pose", "url": "/assets/input/5.png"},
            {"reference_id": "scene", "reference_type": "scene", "role": "scene", "url": "/assets/input/6.png"},
        ]
        prompt = build_prompt("universal", references, {})
        for index in range(1, 7):
            self.assertIn(f"Image {index} =", prompt)
        self.assertIn("AUTO FINAL COMPOSITION", prompt)
        self.assertIn("Dress the model in the exact full outfit or dress from Image 2", prompt)
        self.assertIn("Put the exact shoes from Image 3", prompt)
        self.assertIn("Have the model wear the exact item from Image 4", prompt)
        self.assertIn("Place the model and products inside the scene from Image 6", prompt)
        self.assertIn("REFERENCE OWNERSHIP RULES", prompt)
        self.assertIn("never copy their identity", prompt)
        self.assertIn("CONFLICT PRIORITY", prompt)
        self.assertIn("premium commercial photography", prompt)
        self.assertIn("marketplace-ready", prompt)
        self.assertIn("SKU-level product fidelity", prompt)
        self.assertIn("physically correct contact shadows", prompt)
        self.assertTrue(QUALITY_CHECKS["universal"])

    def test_universal_preserves_subject_native_shoes_and_accessories_by_default(self):
        references = [
            {"reference_id": "model", "reference_type": "subject", "role": "subject", "url": "/assets/input/1.png", "label": "模特自带黑色短靴、金色项链和手表"},
            {"reference_id": "dress", "reference_type": "full_garment", "role": "full_garment", "url": "/assets/input/2.png", "label": "红色连衣裙商品图"},
            {"reference_id": "pose", "reference_type": "pose", "role": "pose", "url": "/assets/input/3.png"},
        ]
        prompt = build_prompt("universal", references, {})
        self.assertIn("[PRIMARY SUBJECT / BODY MODEL / NATIVE STYLING]", prompt)
        self.assertIn("all visible native shoes, jewelry, bags, belts, watches, eyewear, hats, socks, and styling accessories", prompt)
        self.assertIn("SUBJECT-NATIVE STYLING LOCK", prompt)
        self.assertIn("Treat these as subject-owned unchanged styling by default", prompt)
        self.assertIn("Do not erase, simplify, replace, recolor, or borrow alternatives from garment", prompt)
        self.assertIn("Only replace a subject-native shoe, accessory, bag, jewelry item, or prop", prompt)
        self.assertIn("Explicit mapped styling overrides: none", prompt)
        self.assertIn("Subject references own the primary body, body proportions, base silhouette, identity, and visible native shoes/accessories/styling", prompt)

    def test_universal_allows_explicit_mapped_shoe_or_accessory_override(self):
        references = [
            {"reference_id": "model", "reference_type": "subject", "role": "subject", "url": "/assets/input/1.png", "label": "模特自带黑色短靴和金色项链"},
            {"reference_id": "dress", "reference_type": "full_garment", "role": "full_garment", "url": "/assets/input/2.png", "label": "红色连衣裙"},
            {"reference_id": "heels", "reference_type": "shoes", "role": "shoes", "url": "/assets/input/3.png", "label": "银色高跟鞋"},
        ]
        instruction = "使用图3的银色高跟鞋，其他配饰仍保持主体图"
        prompt = build_prompt("universal", references, {"instruction": instruction})
        self.assertEqual(prompt, instruction)

    def test_universal_prompt_anchors_texture_to_reference_pixels(self):
        references = [
            {"reference_id": "model", "reference_type": "subject", "role": "subject", "url": "/assets/input/model.png", "label": "模特"},
            {"reference_id": "jacket", "reference_type": "upper_garment", "role": "upper_garment", "url": "/assets/input/jacket.png", "label": "米白外套"},
            {"reference_id": "cuff", "reference_type": "detail", "role": "detail", "url": "/assets/input/cuff.png", "label": "袖口细节"},
            {"reference_id": "style", "reference_type": "style", "role": "style", "url": "/assets/input/style.png", "label": "柔和棚拍"},
        ]
        analysis = {
            "jacket": {
                "item_name": "米白亚麻外套",
                "visual_details": "短款廓形、贝壳扣、胸前小标",
                "material_signature": "slub linen weave, visible cross-thread grain, matte uneven yarn texture",
            },
            "cuff": {
                "item_name": "袖口微距",
                "material_signature": "dense topstitching, slight seam puckering, raised woven label edge",
            },
        }
        prompt = build_prompt("universal", references, {"reference_analysis": analysis})
        for phrase in (
            "MATERIAL EVIDENCE LOCK",
            "pixel-grounded material fidelity",
            "Image 2: upper garment material evidence",
            "slub linen weave",
            "Image 3: detail material evidence",
            "dense topstitching",
            "Scene, style, pose, and model identity references must never override product material",
            "do not redraw it from a generic fabric description",
            "smooth it, plasticize it, or replace it",
        ):
            self.assertIn(phrase, prompt)
        parsed = parse_universal_reference_analysis(
            '{"item_name":"针织衫","subject_presence":"product_only","face_presence":"no_face","material_signature":"visible rib knit loops and wool fuzz","face_direction":"face looks toward viewer right","body_direction":"torso angled toward viewer right","left_right_semantics":"right hand is on viewer left, left foot leads on viewer right","mirror_risk":"side-profile face would fail if flipped","confidence":0.9}'
        )
        self.assertEqual(parsed["subject_presence"], "product_only")
        self.assertEqual(parsed["face_presence"], "no_face")
        self.assertEqual(parsed["material_signature"], "visible rib knit loops and wool fuzz")
        self.assertEqual(parsed["face_direction"], "face looks toward viewer right")
        self.assertEqual(parsed["body_direction"], "torso angled toward viewer right")
        self.assertIn("left foot leads", parsed["left_right_semantics"])
        self.assertIn("side-profile", parsed["mirror_risk"])

    def test_pose_reference_is_the_primary_spatial_composition_authority(self):
        references = [
            {"reference_id": "model", "reference_type": "subject", "role": "subject", "url": "/assets/input/model.png"},
            {"reference_id": "dress", "reference_type": "full_garment", "role": "full_garment", "url": "/assets/input/dress.png"},
            {"reference_id": "pose-a", "reference_type": "pose", "role": "pose", "url": "/assets/input/pose-a.png"},
            {"reference_id": "pose-b", "reference_type": "pose", "role": "pose", "url": "/assets/input/pose-b.png"},
            {"reference_id": "scene", "reference_type": "scene", "role": "scene", "url": "/assets/input/scene.png"},
        ]
        self.assertEqual(primary_pose_reference(references)["url"], "/assets/input/pose-a.png")
        self.assertEqual(comparison_reference(references)["url"], "/assets/input/pose-a.png")
        instruction = "保持横向 4:3 输出"
        prompt = build_prompt("universal", references, {"instruction": instruction})
        self.assertEqual(prompt, instruction)

    def test_pose_transfer_reference_owns_framing_unless_user_overrides_it(self):
        references = [
            {"role": "source", "url": "/assets/input/model.png"},
            {"role": "pose", "url": "/assets/input/pose.png"},
        ]
        instruction = "改成近景"
        prompt = build_prompt("pose_transfer", references, {"pose_source": "reference", "instruction": instruction})
        self.assertEqual(prompt, instruction)
        self.assertNotIn("Additional user instruction", prompt)

    def test_universal_auto_instruction_chooses_prop_interactions(self):
        references = [
            {"reference_id": "model", "reference_type": "subject", "role": "subject", "url": "/assets/input/1.png", "label": "模特"},
            {"reference_id": "bag", "reference_type": "accessory", "role": "accessory", "url": "/assets/input/2.png", "label": "黑色手提包"},
            {"reference_id": "phone", "reference_type": "prop", "role": "prop", "url": "/assets/input/3.png", "label": "手机"},
            {"reference_id": "chair", "reference_type": "prop", "role": "prop", "url": "/assets/input/4.png", "label": "木椅"},
        ]
        auto = build_universal_auto_instruction(references, {})
        self.assertIn("naturally carry the exact item from Image 2", auto)
        self.assertIn("naturally hold the exact item from Image 3", auto)
        self.assertIn("Place the exact item from Image 4", auto)
        analysis = parse_universal_reference_analysis('{"item_name":"银色项链","category":"项链","interaction":"wear","visual_details":"细链条","confidence":0.91}')
        self.assertEqual(analysis["interaction"], "wear")
        prompt = build_prompt("universal", references[:2], {"reference_analysis": {"bag": {"item_name": "亮面黑色手提包", "interaction": "carry"}}})
        self.assertIn("亮面黑色手提包", prompt)

    def test_universal_accepts_detail_only_inputs_and_at_most_fourteen_images(self):
        subject = {"reference_id": "model", "reference_type": "subject", "role": "subject", "url": "/assets/input/1.png"}
        self.assertEqual(validate_input_roles("universal", [subject], {})[0]["reference_type"], "subject")
        detail = {"reference_id": "detail-a", "reference_type": "detail", "role": "detail", "url": "/assets/input/2.png"}
        self.assertEqual(validate_input_roles("universal", [detail], {})[0]["reference_type"], "detail")
        self.assertEqual(universal_composition_mode([detail]), "base_transfer")
        with self.assertRaisesRegex(ValueError, "至少需要一张"):
            validate_input_roles("universal", [], {})
        too_many = [dict(subject, reference_id=f"r{index}") for index in range(15)]
        with self.assertRaisesRegex(ValueError, "最多上传 14"):
            validate_input_roles("universal", too_many, {})

    def test_detail_only_universal_prompt_uses_first_image_as_base(self):
        references = [
            {"reference_id": "detail-a", "reference_type": "detail", "role": "detail", "url": "/assets/input/a.png", "label": "A 款细节图"},
            {"reference_id": "detail-b", "reference_type": "detail", "role": "detail", "url": "/assets/input/b.png", "label": "B 款细节图"},
        ]
        prompt = build_prompt("universal", references, {})
        self.assertEqual(comparison_reference(references)["url"], "/assets/input/a.png")
        self.assertIn("Image 1 = [BASE IMAGE / PRODUCT DETAIL]", prompt)
        self.assertIn("Image 2 = [DETAIL REPLACEMENT SOURCE]", prompt)
        self.assertIn("Image 1 owns the final layout", prompt)
        self.assertIn("Replace the product/detail content in Image 1", prompt)
        self.assertIn("Do not blend old and new product identities", prompt)

    def test_universal_no_model_product_base_uses_b_product_and_details_only(self):
        references = [
            {"reference_id": "a-base", "reference_type": "subject", "role": "subject", "url": "/assets/input/a.png", "label": "A 款产品图，没有人脸"},
            {"reference_id": "b-main", "reference_type": "full_garment", "role": "full_garment", "url": "/assets/input/b.png", "label": "B 款连衣裙产品图，画面里搭配了鞋子和包"},
            {"reference_id": "b-collar", "reference_type": "detail", "role": "detail", "url": "/assets/input/b-collar.png", "label": "B 款领口细节图"},
            {"reference_id": "b-fabric", "reference_type": "detail", "role": "detail", "url": "/assets/input/b-fabric.png", "label": "B 款面料细节图"},
        ]
        options = {
            "reference_analysis": {
                "a-base": {
                    "item_name": "A 款无脸商品主体",
                    "category": "服装商品图",
                    "subject_presence": "product_only",
                    "face_presence": "no_face",
                    "shot_type": "白底商品主图",
                },
                "b-main": {
                    "item_name": "B 款连衣裙",
                    "category": "连衣裙",
                    "visual_details": "主体是连衣裙，旁边可见搭配鞋子和手提包",
                    "material_signature": "细密梭织纹理",
                },
            }
        }
        prompt = build_prompt("universal", references, options)
        self.assertEqual(universal_composition_mode(references, options), "base_transfer")
        self.assertIn("Image 1 = [BASE IMAGE / PRODUCT TEMPLATE]", prompt)
        self.assertIn("A-style product/body template", prompt)
        self.assertIn("not as a real human model", prompt)
        self.assertIn("mapped B replacement product", prompt)
        self.assertIn("auxiliary local detail evidence for the primary B replacement product", prompt)
        self.assertIn("Extract only the explicitly mapped target item", prompt)
        self.assertIn("ignore incidental shoes, bags, jewelry", prompt.lower())
        self.assertIn("unless uploaded and labeled as their own mapped reference", prompt)
        self.assertNotIn("BASE SUBJECT SPATIAL LOCK", prompt)

    def test_ecommerce_prompt_locks_color_pants_shape_and_named_detail_regions(self):
        references = [
            {"reference_id": "model", "reference_type": "subject", "role": "subject", "url": "/assets/input/model.png", "label": "图1模特姿势"},
            {"reference_id": "pants", "reference_type": "lower_garment", "role": "lower_garment", "url": "/assets/input/pants.png", "label": "橙色阔腿裤"},
            {"reference_id": "waist", "reference_type": "detail", "role": "detail", "url": "/assets/input/waist.png", "label": "裤子腰头细节图"},
            {"reference_id": "side", "reference_type": "detail", "role": "detail", "url": "/assets/input/side.png", "label": "侧边细节图"},
        ]
        prompt = build_prompt("universal", references, {})
        self.assertIn("ECOMMERCE COLOR FIDELITY LOCK", prompt)
        self.assertIn("exact SKU color", prompt)
        self.assertIn("LOWER-GARMENT / PANTS SHAPE LOCK", prompt)
        self.assertIn("wide-leg", prompt)
        self.assertIn("waistband high and flat", prompt)
        self.assertIn("side seams straight", prompt)
        self.assertIn("NAMED DETAIL REGION LOCK", prompt)
        self.assertIn("裤子腰头细节图", prompt)
        self.assertIn("侧边细节图", prompt)
        self.assertIn("BASE SUBJECT SPATIAL LOCK", prompt)
        self.assertIn("leg position, hand position", prompt)

    def test_user_instruction_can_lock_waistband_redline_geometry(self):
        references = [
            {"reference_id": "model", "reference_type": "subject", "role": "subject", "url": "/assets/input/model.png", "label": "图1模特姿势"},
            {"reference_id": "pants", "reference_type": "lower_garment", "role": "lower_garment", "url": "/assets/input/pants.png", "label": "橙色阔腿裤"},
        ]
        instruction = "参考产品图腰头红线标识，把前中下凹处补高到与左右两侧同一水平高度"
        prompt = build_prompt("universal", references, {"instruction": instruction})
        self.assertEqual(prompt, instruction)

        ordinary = build_prompt("universal", references, {"instruction": "保持横向 4:3 输出"})
        self.assertNotIn("USER-REQUESTED WAISTBAND GEOMETRY LOCK", ordinary)

    def test_capabilities_do_not_expose_provider_secrets(self):
        providers = [dict(self.providers[0], api_key="secret", key_preview="abcd")]
        capabilities = public_capabilities(providers)
        self.assertEqual(capabilities["modes"], ["standard"])
        self.assertEqual(capabilities["defaults"]["standard"]["count"], 1)
        self.assertEqual(capabilities["defaults"]["standard"]["resolution"], "2k")
        self.assertTrue(capabilities["quality_checks"]["try_on"])
        self.assertNotIn("api_key", str(capabilities))
        self.assertNotIn("secret", str(capabilities))
        self.assertEqual(capabilities["universal_reference_limit"], 14)
        self.assertTrue(capabilities["universal_reference_roles"])

    def test_only_explicit_unsupported_errors_allow_route_fallback(self):
        self.assertTrue(safe_fallback_error(405, "Method Not Allowed"))
        self.assertTrue(safe_fallback_error(400, "model is unsupported"))
        self.assertFalse(safe_fallback_error(502, "timeout"))
        self.assertFalse(safe_fallback_error(400, "insufficient balance"))

    def test_garment_analysis_normalizes_local_vision_json(self):
        analysis = parse_garment_analysis('```json\n{"category":"上装","garment_type":"短袖 T 恤","confidence":0.93,"reason":"短袖圆领"}\n```')
        self.assertEqual(analysis["category"], "upper")
        self.assertEqual(analysis["garment_type"], "短袖 T 恤")
        self.assertEqual(analysis["confidence"], 0.93)


class EcommerceBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main
        cls.main = main

    def make_image(self, path: Path, size=(100, 80), image_format="PNG"):
        Image.new("RGB", size, "white").save(path, image_format)

    def test_provider_list_keeps_user_added_platform_ids_and_default_presets(self):
        class FakeDatabase:
            def load_providers(self):
                return [
                    {"id": "modelscope", "name": "ModelScope", "enabled": True, "image_models": ["Qwen-Image-Edit-2511"]},
                    {"id": "grsai", "name": "Grsai", "base_url": "https://grsaiapi.com", "enabled": True, "image_models": ["gpt-image-2-vip"]},
                    {"id": "lingjing", "name": "灵境", "enabled": True, "image_models": ["gpt-image-2"]},
                ]

        with patch.object(self.main, "DATABASE", FakeDatabase()):
            providers = self.main.load_api_providers()
        self.assertEqual(
            [item["id"] for item in providers],
            ["modelscope", "grsai", "lingjing", "shiying", "local-vision"],
        )
        self.assertEqual(providers[3]["base_url"], "https://www.shiying-api.com")
        self.assertEqual(providers[3]["model_protocols"]["gemini-3-pro-image-preview"], "gemini")
        self.assertEqual(providers[4]["chat_models"], ["qwen3.5-9b-vlm"])
        self.assertEqual(providers[4]["image_models"], [])

    def test_grsai_builtin_provider_uses_documented_root_and_models(self):
        provider = self.main.normalize_provider({
            "id": "grsai",
            "name": "Grsai API",
            "base_url": "https://grsaiapi.com/v1/api",
            "protocol": "gemini",
            "image_request_mode": "openai-json",
        })
        self.assertEqual(provider["base_url"], "https://grsaiapi.com")
        self.assertEqual(provider["protocol"], "openai")
        self.assertEqual(provider["image_request_mode"], "openai")
        self.assertEqual(provider["image_models"], [])
        defaults = {item["id"]: item for item in self.main.default_api_providers()}
        self.assertEqual(defaults["grsai"]["base_url"], "https://grsaiapi.com")
        self.assertEqual(defaults["grsai"]["image_models"], ["nano-banana-2", "gpt-image-2"])

    def test_grsai_probe_accepts_nonexistent_healthcheck_task_without_generation(self):
        class FakeResponse:
            status_code = 404
            text = '{"error":"result not exist, valid for 2 hours"}'

        class FakeClient:
            def __init__(self):
                self.calls = []

            async def get(self, url, **kwargs):
                self.calls.append((url, kwargs))
                return FakeResponse()

        client = FakeClient()
        ok, probe = asyncio.run(self.main.probe_grsai_endpoint(client, "https://grsaiapi.com/v1", "test-key"))
        self.assertTrue(ok)
        self.assertEqual(probe["status"], 404)
        self.assertEqual(client.calls[0][0], "https://grsaiapi.com/v1/api/result")
        self.assertEqual(client.calls[0][1]["params"]["id"], "healthcheck_probe_do_not_submit")

    def test_grsai_task_id_accepts_documented_id_without_task_prefix(self):
        self.assertEqual(
            self.main.grsai_task_id({"id": "12-2d8f8afe-98b8-4779-abf1-433cc557e002", "status": "processing"}),
            "12-2d8f8afe-98b8-4779-abf1-433cc557e002",
        )

    def test_grsai_nano_request_uses_documented_body_and_response(self):
        class FakeResponse:
            status_code = 200
            text = '{"id":"12-abc","status":"succeeded","results":[{"url":"https://files.example/image.png"}]}'

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "id": "12-abc",
                    "status": "succeeded",
                    "results": [{"url": "https://files.example/image.png"}],
                }

        class FakeClient:
            def __init__(self):
                self.post_call = None

            async def post(self, url, **kwargs):
                self.post_call = (url, kwargs)
                return FakeResponse()

        fake_client = FakeClient()

        class FakeAsyncClient:
            def __init__(self, **kwargs):
                return None

            async def __aenter__(self):
                return fake_client

            async def __aexit__(self, exc_type, exc, tb):
                return False

        provider = {"id": "grsai", "base_url": "https://grsaiapi.com"}
        with (
            patch.object(self.main.httpx, "AsyncClient", FakeAsyncClient),
            patch.object(self.main, "provider_env_key_value", return_value="test-key"),
        ):
            image, raw = asyncio.run(self.main.generate_grsai_nano_provider_image(
                "a test prompt", "1024x1024", "nano-banana-2", provider=provider
            ))
        self.assertEqual(image, {"type": "url", "value": "https://files.example/image.png"})
        self.assertEqual(raw["status"], "succeeded")
        self.assertEqual(fake_client.post_call[0], "https://grsaiapi.com/v1/api/generate")
        request_body = fake_client.post_call[1]["json"]
        self.assertEqual(request_body["model"], "nano-banana-2")
        self.assertEqual(request_body["images"], [])
        self.assertEqual(request_body["aspectRatio"], "1:1")
        self.assertEqual(request_body["imageSize"], "1K")
        self.assertEqual(request_body["replyType"], "json")

    def test_local_vision_url_auto_completion(self):
        cases = {
            "115.231.35.105:12345": "http://115.231.35.105:12345/v1",
            "localhost:8000": "http://localhost:8000/v1",
            "vision.example.com": "https://vision.example.com/v1",
            "vision.example.com:8443": "https://vision.example.com:8443/v1",
            "https://vision.example.com/openai/v1/": "https://vision.example.com/openai/v1",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(self.main.normalize_openai_compatible_base_url(raw), expected)
        with self.assertRaises(self.main.HTTPException):
            self.main.normalize_openai_compatible_base_url("https://user:pass@example.com")

    def test_ecommerce_auxiliary_prompts_extract_nano_banana_pro_evidence(self):
        self.assertIn("Nano Banana Pro", self.main.ECOMMERCE_UNIVERSAL_REFERENCE_ANALYSIS_PROMPT)
        self.assertIn("角色归属 + 保真证据", self.main.ECOMMERCE_UNIVERSAL_REFERENCE_ANALYSIS_PROMPT)
        self.assertIn("material_signature", self.main.ECOMMERCE_UNIVERSAL_REFERENCE_ANALYSIS_PROMPT)
        self.assertIn("Logo、吊牌、包装和衣服印字", self.main.ECOMMERCE_UNIVERSAL_REFERENCE_ANALYSIS_PROMPT)
        self.assertIn("material_evidence", self.main.ASSET_CLASSIFICATION_PROMPT)
        self.assertIn("brand_text", self.main.ASSET_CLASSIFICATION_PROMPT)
        self.assertIn("reference_role_suggestion", self.main.ASSET_CLASSIFICATION_PROMPT)

    def test_static_cache_versioning_preserves_workspace_query_parameters(self):
        source = '<iframe data-src="/static/ecommerce.html?workspace=free-creation&amp;v=old"></iframe>'
        with (
            patch.object(self.main, "current_app_version", return_value="9.9.9"),
            patch.object(self.main.os.path, "isfile", return_value=False),
        ):
            rendered = self.main.versioned_static_html(source)
        self.assertIn('/static/ecommerce.html?workspace=free-creation&amp;v=9.9.9', rendered)
        self.assertNotIn('?v=9.9.9?workspace=', rendered)

    def test_builtin_local_vision_key_is_seeded_only_once(self):
        class FakeDatabase:
            def __init__(self, done=False):
                self.done = done
                self.saved = None

            def get_setting(self, key, default):
                return {"value": {"done": self.done}}

            def save_setting(self, key, value, only_if_empty=False):
                self.saved = (key, value, only_if_empty)

        updates = []
        fake = FakeDatabase()
        with (
            patch.object(self.main, "DATABASE", fake),
            patch.object(self.main, "provider_env_key_value", return_value=""),
            patch.object(self.main, "update_env_values", side_effect=lambda value: updates.append(value)),
        ):
            result = self.main.seed_builtin_local_vision_secret_once()
        self.assertTrue(result["seeded"])
        self.assertEqual(updates[0][self.main.provider_key_env("local-vision")], self.main.LOCAL_VISION_BUILTIN_API_KEY)
        self.assertTrue(fake.saved[1]["done"])

        with (
            patch.object(self.main, "DATABASE", FakeDatabase(done=True)),
            patch.object(self.main, "update_env_values") as update,
        ):
            result = self.main.seed_builtin_local_vision_secret_once()
        self.assertTrue(result["skipped"])
        update.assert_not_called()

    def test_ecommerce_capabilities_only_include_configured_provider(self):
        providers = [
            {"id": "grsai", "name": "Grsai", "enabled": True, "image_models": ["gpt-image-2-vip"]},
            {"id": "missing-key", "name": "Missing", "enabled": True, "image_models": ["gpt-image-2"]},
        ]
        with (
            patch.object(self.main, "load_api_providers", return_value=providers),
            patch.object(self.main, "provider_env_key_value", side_effect=lambda provider_id: "configured" if provider_id == "grsai" else ""),
        ):
            capabilities = asyncio.run(self.main.get_ecommerce_capabilities())
        self.assertEqual(capabilities["providers"], [{"id": "grsai", "name": "Grsai"}])
        self.assertTrue(capabilities["models"])
        self.assertEqual({item["provider_id"] for item in capabilities["models"]}, {"grsai"})

    def test_ecommerce_capabilities_include_arbitrary_configured_image_models(self):
        providers = [
            {"id": "custom-a", "name": "Custom A", "enabled": True, "image_models": ["future-image-v9"]},
            {"id": "custom-b", "name": "Custom B", "enabled": True, "image_models": ["vendor-render-alpha"]},
        ]
        with (
            patch.object(self.main, "load_api_providers", return_value=providers),
            patch.object(self.main, "provider_env_key_value", return_value="configured"),
        ):
            capabilities = asyncio.run(self.main.get_ecommerce_capabilities())
        self.assertEqual(
            capabilities["providers"],
            [{"id": "custom-a", "name": "Custom A"}, {"id": "custom-b", "name": "Custom B"}],
        )
        self.assertEqual(
            {(item["provider_id"], item["model"]) for item in capabilities["models"]},
            {("custom-a", "future-image-v9"), ("custom-b", "vendor-render-alpha")},
        )

    def test_reference_slot_types_are_normalized_and_saved_globally(self):
        class FakeDatabase:
            def __init__(self):
                self.value = {}

            def get_setting(self, key, default):
                return {"value": self.value or default, "revision": 7, "updated_at": 11}

            def save_setting(self, key, value, base_revision=0, only_if_empty=False):
                self.value = value
                return {"value": value, "revision": 8, "updated_at": 12}

        fake = FakeDatabase()
        payload = self.main.ReferenceSlotTypesRequest(types=[
            self.main.ReferenceSlotTypeItem(id="Bag Type", role="unknown-role", label_zh="包袋", label_en="Bag"),
            self.main.ReferenceSlotTypeItem(id="subject", role="subject", label_zh="真人模特", label_en="Model"),
            self.main.ReferenceSlotTypeItem(id="model_identity", role="prop", label_zh="旧形象类型", label_en="Legacy identity"),
            self.main.ReferenceSlotTypeItem(id="detail", role="prop", label_zh="旧细节类型", label_en="Legacy detail"),
        ])
        with (
            patch.object(self.main, "DATABASE", fake),
            patch.object(self.main, "publish_entity_changed") as publish,
        ):
            result = self.main.update_reference_slot_types(payload)
            loaded = self.main.get_reference_slot_types()

        custom = next(item for item in result["types"] if item["id"] == "bag_type")
        subject = next(item for item in result["types"] if item["id"] == "subject")
        model_identity = next(item for item in result["types"] if item["id"] == "model_identity")
        detail = next(item for item in result["types"] if item["id"] == "detail")
        self.assertEqual(custom["role"], "prop")
        self.assertEqual(custom["label_zh"], "包袋")
        self.assertTrue(subject["locked"])
        self.assertEqual(model_identity["role"], "model_identity")
        self.assertTrue(model_identity["locked"])
        self.assertEqual(detail["role"], "detail")
        self.assertTrue(detail["locked"])
        self.assertTrue(any(item["id"] == "upper_garment" for item in result["types"]))
        self.assertEqual(loaded["revision"], 7)
        self.assertTrue(any(item["id"] == "bag_type" for item in loaded["types"]))
        publish.assert_called_once()

    def test_ecommerce_task_rejects_provider_without_api_key_before_queueing(self):
        provider = {"id": "grsai", "name": "Grsai", "enabled": True, "image_models": ["gpt-image-2-vip"]}
        payload = self.main.EcommerceTaskRequest(
            operation="angle_change",
            mode="standard",
            inputs=[self.main.AIReference(role="source", url="/assets/input/source.png")],
        )
        with (
            patch.object(self.main, "load_api_providers", return_value=[provider]),
            patch.object(self.main, "provider_env_key_value", return_value=""),
            patch.object(self.main, "validate_ecommerce_local_inputs", return_value=([{"role": "source", "url": "/assets/input/source.png"}], (100, 100))),
        ):
            with self.assertRaises(self.main.HTTPException) as error:
                self.main.prepare_ecommerce_request(payload)
        self.assertEqual(error.exception.status_code, 400)
        self.assertIn("没有找到兼容", error.exception.detail)

    def test_ecommerce_task_applies_selected_generation_parameters(self):
        provider = {"id": "shiying", "name": "shiying", "enabled": True, "image_models": ["gemini-3-pro-image-preview"]}
        payload = self.main.EcommerceTaskRequest(
            operation="angle_change",
            mode="standard",
            inputs=[self.main.AIReference(role="source", url="/assets/input/source.png")],
            provider_id="shiying",
            model="gemini-3-pro-image-preview",
            aspect_ratio="4:5",
            resolution="2k",
            quality="high",
            count=3,
        )
        with (
            patch.object(self.main, "configured_ecommerce_providers", return_value=[provider]),
            patch.object(self.main, "validate_ecommerce_local_inputs", return_value=([{"role": "source", "url": "/assets/input/source.png"}], (900, 1600))),
        ):
            snapshot = self.main.prepare_ecommerce_request(payload)
        self.assertEqual(snapshot["size"], "1632x2040")
        self.assertEqual(snapshot["aspect_ratio"], "4:5")
        self.assertEqual(snapshot["resolution"], "2k")
        self.assertEqual(snapshot["quality"], "high")
        self.assertEqual(snapshot["count"], 3)
        self.assertEqual(snapshot["parameters"], {"aspect_ratio": "4:5", "resolution": "2k", "quality": "high", "count": 3})

    def test_background_replacement_always_forces_source_ratio(self):
        provider = {"id": "shiying", "name": "shiying", "enabled": True, "image_models": ["gemini-3-pro-image-preview"]}
        base = {
            "operation": "background_change",
            "mode": "standard",
            "inputs": [self.main.AIReference(role="source", url="/assets/input/source.png")],
            "provider_id": "shiying",
            "model": "gemini-3-pro-image-preview",
            "aspect_ratio": "4:5",
            "resolution": "2k",
        }
        with (
            patch.object(self.main, "configured_ecommerce_providers", return_value=[provider]),
            patch.object(self.main, "validate_ecommerce_local_inputs", return_value=([{"role": "source", "url": "/assets/input/source.png"}], (900, 1600))),
        ):
            locked = self.main.prepare_ecommerce_request(self.main.EcommerceTaskRequest(**base))
            attempted_override = self.main.prepare_ecommerce_request(self.main.EcommerceTaskRequest(**{**base, "options": {"preserve_source_composition": False}}))
        self.assertTrue(locked["source_composition_locked"])
        self.assertEqual((locked["aspect_ratio"], locked["size"]), ("source", "1152x2048"))
        self.assertTrue(attempted_override["source_composition_locked"])
        self.assertEqual((attempted_override["aspect_ratio"], attempted_override["size"]), ("source", "1152x2048"))

    def test_user_prompt_request_preserves_universal_panel_reference_order_without_prompt_injection(self):
        provider = {"id": "shiying", "name": "shiying", "enabled": True, "image_models": ["gemini-3-pro-image-preview"]}
        inputs = [
            {"role": "subject", "reference_type": "subject", "reference_id": "panel_1", "url": "/assets/input/1.png"},
            {"role": "detail", "reference_type": "detail", "reference_id": "panel_2", "url": "/assets/input/2.png"},
            {"role": "scene", "reference_type": "scene", "reference_id": "panel_3", "url": "/assets/input/3.png"},
        ]
        payload = self.main.EcommerceTaskRequest(
            operation="universal",
            inputs=[self.main.AIReference(**item) for item in inputs],
            options={"instruction": "图1使用图2材质，图3作为背景"},
            provider_id="shiying",
            model="gemini-3-pro-image-preview",
        )
        observed = {}

        def validate_local_inputs(values, operation):
            observed["operation"] = operation
            observed["reference_ids"] = [item["reference_id"] for item in values]
            return values, (100, 100)

        with (
            patch.object(self.main, "configured_ecommerce_providers", return_value=[provider]),
            patch.object(self.main, "validate_ecommerce_local_inputs", side_effect=validate_local_inputs),
        ):
            snapshot = self.main.prepare_ecommerce_request(payload)

        self.assertEqual(observed["operation"], "universal")
        self.assertEqual(observed["reference_ids"], ["panel_1", "panel_2", "panel_3"])
        self.assertEqual([item["reference_id"] for item in snapshot["inputs"]], ["panel_1", "panel_2", "panel_3"])
        self.assertEqual(snapshot["prompt"], "图1使用图2材质，图3作为背景")

    def test_pose_reference_controls_source_ratio_and_comparison_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            subject = Path(root) / "subject.png"
            pose = Path(root) / "pose.png"
            self.make_image(subject, (120, 80))
            self.make_image(pose, (60, 120))
            lookup = {"/assets/input/subject.png": str(subject), "/assets/input/pose.png": str(pose)}
            inputs = [
                {"role": "subject", "reference_type": "subject", "reference_id": "model", "url": "/assets/input/subject.png"},
                {"role": "pose", "reference_type": "pose", "reference_id": "pose", "url": "/assets/input/pose.png"},
            ]
            with patch.object(self.main, "output_file_from_url", side_effect=lambda url: lookup.get(url)):
                checked, source_dimensions = self.main.validate_ecommerce_local_inputs(inputs)
            self.assertEqual(source_dimensions, (60, 120))

        provider = {"id": "shiying", "name": "shiying", "enabled": True, "image_models": ["gemini-3-pro-image-preview"]}
        payload = self.main.EcommerceTaskRequest(
            operation="universal",
            inputs=[self.main.AIReference(**item) for item in inputs],
            provider_id="shiying",
            model="gemini-3-pro-image-preview",
            aspect_ratio="source",
        )
        with (
            patch.object(self.main, "configured_ecommerce_providers", return_value=[provider]),
            patch.object(self.main, "validate_ecommerce_local_inputs", return_value=(checked, (60, 120))),
        ):
            snapshot = self.main.prepare_ecommerce_request(payload)
        self.assertEqual(snapshot["pose_reference_url"], "/assets/input/pose.png")
        self.assertEqual(snapshot["comparison_reference_url"], "/assets/input/pose.png")
        self.assertEqual(snapshot["size"], "1024x2048")

    def test_detail_only_universal_request_uses_first_image_dimensions_and_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            detail_a = Path(root) / "detail-a.png"
            detail_b = Path(root) / "detail-b.png"
            self.make_image(detail_a, (160, 100))
            self.make_image(detail_b, (80, 160))
            lookup = {"/assets/input/a.png": str(detail_a), "/assets/input/b.png": str(detail_b)}
            inputs = [
                {"role": "detail", "reference_type": "detail", "reference_id": "detail-a", "url": "/assets/input/a.png"},
                {"role": "detail", "reference_type": "detail", "reference_id": "detail-b", "url": "/assets/input/b.png"},
            ]
            with patch.object(self.main, "output_file_from_url", side_effect=lambda url: lookup.get(url)):
                checked, source_dimensions = self.main.validate_ecommerce_local_inputs(inputs, "universal")
            self.assertEqual(source_dimensions, (160, 100))

        provider = {"id": "shiying", "name": "shiying", "enabled": True, "image_models": ["gemini-3-pro-image-preview"]}
        payload = self.main.EcommerceTaskRequest(
            operation="universal",
            inputs=[self.main.AIReference(**item) for item in inputs],
            provider_id="shiying",
            model="gemini-3-pro-image-preview",
            aspect_ratio="source",
        )
        with (
            patch.object(self.main, "configured_ecommerce_providers", return_value=[provider]),
            patch.object(self.main, "validate_ecommerce_local_inputs", return_value=(checked, (160, 100))),
        ):
            snapshot = self.main.prepare_ecommerce_request(payload)
        self.assertEqual(snapshot["composition_mode"], "base_transfer")
        self.assertEqual(snapshot["base_reference_id"], "detail-a")
        self.assertEqual(snapshot["base_reference_url"], "/assets/input/a.png")
        self.assertEqual(snapshot["comparison_reference_url"], "/assets/input/a.png")
        self.assertEqual(snapshot["size"], "2048x1280")

    def test_removed_provider_presets_are_pruned_once(self):
        class FakeDatabase:
            def __init__(self):
                self.saved = None
                self.marker = None

            def get_setting(self, key, default):
                return default

            def load_providers(self):
                return [
                    {"id": "modelscope"},
                    {"id": "grsai"},
                    {"id": "lingjing"},
                    {"id": "custom-provider"},
                ]

            def save_providers(self, providers):
                self.saved = list(providers)

            def save_setting(self, key, value, only_if_empty=False):
                self.marker = (key, value, only_if_empty)

        fake = FakeDatabase()
        with patch.object(self.main, "DATABASE", fake):
            report = self.main.prune_removed_provider_presets_once()
        self.assertEqual(report["removed"], ["modelscope", "lingjing"])
        self.assertEqual([item["id"] for item in fake.saved], ["grsai", "custom-provider"])
        self.assertTrue(fake.marker[1]["done"])

    def test_prompt_only_background_replacement_rejects_mask_input(self):
        with self.assertRaises(ValueError) as error:
            validate_input_roles("background_change", [
                {"role": "source", "url": "/assets/input/source.png"},
                {"role": "mask", "url": "/assets/input/mask.png"},
            ])
        self.assertIn("已移除蒙版", str(error.exception))

    def test_local_inputs_accept_mpo_as_jpeg(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "source.png"
            garment = Path(root) / "garment.jpg"
            self.make_image(source)
            first = Image.new("RGB", (100, 80), "red")
            second = Image.new("RGB", (100, 80), "blue")
            first.save(garment, "MPO", save_all=True, append_images=[second])
            lookup = {"/assets/input/source.png": str(source), "/assets/input/garment.jpg": str(garment)}
            inputs = [
                {"role": "source", "url": "/assets/input/source.png"},
                {"role": "garment", "url": "/assets/input/garment.jpg"},
            ]
            with patch.object(self.main, "output_file_from_url", side_effect=lambda url: lookup.get(url)):
                checked, dimensions = self.main.validate_ecommerce_local_inputs(inputs)
            self.assertEqual(dimensions, (100, 80))
            self.assertEqual(checked[1]["mime"], "image/jpeg")

    def test_ecommerce_vision_route_prefers_local_vlm(self):
        providers = [
            {"id": "chat", "name": "Chat", "enabled": True, "chat_models": ["qwen3.5-9b-vlm"]},
            {"id": "local-vision", "name": "本地视觉模型", "enabled": True, "chat_models": ["qwen3.5-9b-vlm"]},
        ]
        with patch.object(self.main, "provider_env_key_value", return_value="configured"):
            route = self.main.configured_ecommerce_vision_route(providers)
        self.assertEqual(route["provider_id"], "local-vision")

    def test_universal_vision_analysis_runs_in_parallel_and_reuses_cache(self):
        with tempfile.TemporaryDirectory() as root:
            paths = []
            for index in range(3):
                path = Path(root) / f"ref-{index}.png"
                self.make_image(path)
                paths.append(path)
            inputs = [
                {"reference_id": f"ref-{index}", "reference_type": "prop", "role": "prop", "url": f"/assets/input/ref-{index}.png"}
                for index in range(3)
            ]
            active = 0
            max_active = 0

            async def caption(*args, **kwargs):
                nonlocal active, max_active
                active += 1
                max_active = max(max_active, active)
                await asyncio.sleep(0.02)
                active -= 1
                return '{"item_name":"商品","category":"道具","interaction":"hold"}', "qwen3.5-9b-vlm"

            self.main.ECOMMERCE_VISION_CACHE.clear()
            route = {"provider_id": "local-vision", "provider_name": "本地视觉模型", "model": "qwen3.5-9b-vlm"}
            mocked_caption = AsyncMock(side_effect=caption)
            with (
                patch.object(self.main, "configured_ecommerce_vision_route", return_value=route),
                patch.object(self.main, "output_file_from_url", side_effect=lambda url: str(paths[int(re.search(r"(\d+)", url).group(1))])),
                patch.object(self.main, "caption_image_with_provider", mocked_caption),
            ):
                first = asyncio.run(self.main.analyze_ecommerce_universal_references(inputs))
                second = asyncio.run(self.main.analyze_ecommerce_universal_references(inputs))
            self.assertEqual(first["succeeded"], 3)
            self.assertGreaterEqual(max_active, 2)
            self.assertEqual(mocked_caption.await_count, 3)
            self.assertTrue(all(item.get("cached") for item in second["items"].values()))

    def test_auto_garment_analysis_enriches_prompt(self):
        snapshot = {
            "operation": "try_on",
            "inputs": [
                {"role": "source", "url": "/assets/input/source.png"},
                {"role": "garment", "url": "/assets/input/garment.jpg"},
            ],
            "options": {"garment_category": "auto"},
            "prompt": "before",
        }
        analysis = {"status": "succeeded", "category": "upper", "garment_type": "短袖 T 恤", "confidence": 0.96}
        with patch.object(self.main, "analyze_ecommerce_garment", new=AsyncMock(return_value=analysis)):
            enriched, returned = asyncio.run(self.main.enrich_ecommerce_snapshot_with_garment_analysis(snapshot))
        self.assertEqual(returned, analysis)
        self.assertEqual(enriched["options"]["garment_category"], "upper")
        self.assertIn("upper-body garment", enriched["prompt"])
        self.assertIn("短袖 T 恤", enriched["prompt"])

    def test_free_creation_skips_universal_reference_analysis(self):
        prompt = "图1作为主体，图2只提供色彩风格"
        snapshot = {
            "operation": "universal",
            "inputs": [
                {"reference_id": "subject", "reference_type": "subject", "role": "subject", "url": "/assets/input/source.png"},
                {"reference_id": "style", "reference_type": "style", "role": "style", "url": "/assets/input/style.png"},
            ],
            "options": {"prompt_policy": "free", "instruction": prompt},
            "prompt": prompt,
        }
        analyzer = AsyncMock()
        with patch.object(self.main, "analyze_ecommerce_universal_references", new=analyzer):
            enriched, returned = asyncio.run(self.main.enrich_ecommerce_snapshot_with_universal_analysis(snapshot))
        analyzer.assert_not_awaited()
        self.assertIsNone(returned)
        self.assertEqual(enriched["prompt"], prompt)
        self.assertNotIn("reference_analysis", enriched["options"])

    def test_free_creation_request_allows_zero_reference_images(self):
        provider = {"id": "shiying", "name": "shiying", "enabled": True, "image_models": ["gemini-3-pro-image-preview"]}
        prompt = "一座漂浮在云海上的玻璃城市，清晨柔光，电影感广角构图"
        payload = self.main.EcommerceTaskRequest(
            operation="universal",
            inputs=[],
            options={"prompt_policy": "free", "instruction": prompt},
            provider_id="shiying",
            model="gemini-3-pro-image-preview",
            aspect_ratio="16:9",
            resolution="2k",
        )
        self.assertEqual(
            self.main.validate_ecommerce_local_inputs([], "universal", allow_empty=True),
            ([], (1024, 1024)),
        )
        with patch.object(self.main, "configured_ecommerce_providers", return_value=[provider]):
            snapshot = self.main.prepare_ecommerce_request(payload)
        self.assertEqual(snapshot["inputs"], [])
        self.assertEqual(snapshot["source_dimensions"], {"width": 1024, "height": 1024})
        self.assertEqual(snapshot["composition_mode"], "")
        self.assertEqual(snapshot["base_reference_url"], "")
        self.assertEqual(snapshot["comparison_reference_url"], "")
        self.assertEqual(snapshot["prompt"], prompt)
        self.assertEqual(snapshot["aspect_ratio"], "16:9")
        self.assertTrue(snapshot["route_candidates"])

    def test_approval_requires_every_quality_check(self):
        task_id = "ecommerce_test_approval"
        self.main.ECOMMERCE_TASKS[task_id] = {
            "id": task_id,
            "operation": "try_on",
            "status": "succeeded",
            "result": {"images": ["/assets/output/result.png"]},
        }
        incomplete = self.main.EcommerceApprovalRequest(output_index=0, checks={"identity": True})
        with self.assertRaises(self.main.HTTPException) as error:
            asyncio.run(self.main.approve_ecommerce_task(task_id, incomplete))
        self.assertEqual(error.exception.status_code, 400)

        checks = {item["id"]: True for item in QUALITY_CHECKS["try_on"]}
        complete = self.main.EcommerceApprovalRequest(output_index=0, checks=checks)
        with patch.object(self.main, "update_ecommerce_task") as update:
            result = asyncio.run(self.main.approve_ecommerce_task(task_id, complete))
        self.assertEqual(result["approval"]["status"], "approved")
        self.assertEqual(update.call_args.args[1]["approval"]["output_url"], "/assets/output/result.png")
        self.main.ECOMMERCE_TASKS.pop(task_id, None)

    def test_export_is_blocked_until_approval_and_then_copies_official_file(self):
        task_id = "ecommerce_test_export"
        self.main.ECOMMERCE_TASKS[task_id] = {"id": task_id, "operation": "background_change", "approval": {"status": "pending"}}
        with self.assertRaises(self.main.HTTPException) as error:
            asyncio.run(self.main.export_ecommerce_task(task_id))
        self.assertEqual(error.exception.status_code, 409)

        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "source.png"
            exports = Path(root) / "exports"
            self.make_image(source)
            self.main.ECOMMERCE_TASKS[task_id]["approval"] = {
                "status": "approved",
                "output_url": "/assets/output/source.png",
                "export": None,
            }
            with (
                patch.object(self.main, "OUTPUT_DIR", str(exports)),
                patch.object(self.main, "output_file_from_url", side_effect=lambda url: str(source) if url == "/assets/output/source.png" else None),
                patch.object(self.main, "media_url_from_path", side_effect=lambda path: "/output/" + Path(path).relative_to(exports).as_posix()),
                patch.object(self.main, "update_ecommerce_task") as update,
            ):
                result = asyncio.run(self.main.export_ecommerce_task(task_id))
            self.assertEqual(result["export"]["kind"], "official")
            exported = list(exports.rglob("*.png"))
            self.assertEqual(len(exported), 1)
            self.assertTrue(update.called)
        self.main.ECOMMERCE_TASKS.pop(task_id, None)

    def test_history_mirrors_generated_images_to_configured_directory(self):
        class FakeDatabase:
            def __init__(self):
                self.record = None

            def prepend_history(self, record, limit=5000):
                self.record = record

        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            source = root_path / "generated.png"
            output = root_path / "chosen-output"
            self.make_image(source)
            record = {
                "type": "ecommerce",
                "images": ["/assets/output/generated.png"],
                "timestamp": 1784772000,
            }
            fake = FakeDatabase()
            with (
                patch.object(self.main, "DATABASE", fake),
                patch.object(self.main, "read_app_config", return_value={"close_behavior": "exit", "generated_output_dir": str(output)}),
                patch.object(self.main, "output_file_from_url", return_value=str(source)),
                patch.object(self.main, "publish_entity_changed"),
            ):
                self.main.save_to_history(record)
            self.assertEqual(len(record["saved_images"]), 1)
            saved = Path(record["saved_images"][0]["path"])
            self.assertEqual(saved.parent, output)
            self.assertRegex(saved.name, r"^SHIYIN-000001-\d{8}\.png$")
            self.assertTrue(saved.exists())
            self.assertIs(fake.record, record)

    def test_publish_batch_makes_four_independent_calls_and_uses_semantic_mask(self):
        generated = AsyncMock(return_value=(
            {"type": "url", "value": "/assets/output/upstream.png"},
            {"data": []},
        ))
        saved_urls = iter([f"/assets/output/candidate-{index}.png" for index in range(4)])
        saved = AsyncMock(side_effect=lambda *args, **kwargs: next(saved_urls))
        with (
            patch.object(self.main, "get_api_provider", return_value={"id": "modelscope", "name": "ModelScope", "image_models": ["Qwen/Qwen-Image-Edit-2511"]}),
            patch.object(self.main, "generate_ai_image", generated),
            patch.object(self.main, "save_ai_image_to_output", saved),
            patch.object(self.main, "image_output_meta", side_effect=lambda url, item=None: {"url": url}),
        ):
            batch = asyncio.run(self.main.execute_ai_image_batch(
                prompt="edit",
                provider_id="modelscope",
                model="Qwen/Qwen-Image-Edit-2511",
                size="2048x2048",
                quality="high",
                references=[{"role": "source", "url": "/assets/input/source.png", "kind": "image"}],
                count=4,
                prefix="ecommerce_",
                allow_edit_endpoint_fallback=False,
                semantic_mask=True,
            ))
        self.assertEqual(generated.await_count, 4)
        self.assertEqual(len(batch["images"]), 4)
        self.assertTrue(all(call.kwargs["semantic_mask"] is True for call in generated.await_args_list))
        self.assertTrue(all(call.kwargs["allow_edit_endpoint_fallback"] is False for call in generated.await_args_list))
        self.assertTrue(all(call.kwargs["enterprise_filename"] is True for call in saved.await_args_list))

    def test_task_restore_marks_active_task_interrupted_without_resubmission(self):
        class FakeDatabase:
            def __init__(self):
                self.saved = []

            def load_tasks(self, kind):
                return [{"id": "ecommerce_running", "type": "ecommerce", "status": "running", "created_at": 1}]

            def save_tasks(self, kind, tasks):
                self.saved = list(tasks)

        fake = FakeDatabase()
        self.main.ECOMMERCE_TASKS.clear()
        with (
            patch.object(self.main, "DATABASE", fake),
            patch.object(self.main, "publish_entity_changed"),
        ):
            self.main.load_ecommerce_tasks_from_disk()
        restored = self.main.ECOMMERCE_TASKS["ecommerce_running"]
        self.assertEqual(restored["status"], "interrupted")
        self.assertIn("不会自动补发", restored["error"])
        self.assertEqual(fake.saved[0]["status"], "interrupted")
        self.main.ECOMMERCE_TASKS.clear()

    def test_batch_task_status_returns_lightweight_updates(self):
        self.main.ECOMMERCE_TASKS.clear()
        self.main.ECOMMERCE_TASKS.update({
            "ecommerce_a": {"id": "ecommerce_a", "status": "running", "updated_at": 2, "prompt": "large", "inputs": [{"url": "x"}]},
            "ecommerce_b": {"id": "ecommerce_b", "status": "succeeded", "updated_at": 3, "result": {"images": ["y"]}},
        })
        result = asyncio.run(self.main.ecommerce_task_status(self.main.EcommerceTaskStatusRequest(ids=["ecommerce_a", "ecommerce_b", "missing"])))
        self.assertEqual([item["id"] for item in result["tasks"]], ["ecommerce_a", "ecommerce_b"])
        self.assertEqual(result["missing"], ["missing"])
        self.assertNotIn("prompt", result["tasks"][0])
        self.assertNotIn("result", result["tasks"][1])
        self.main.ECOMMERCE_TASKS.clear()

    def test_delete_ecommerce_task_clears_failed_record_only(self):
        class FakeDatabase:
            def __init__(self):
                self.deleted = []

            def delete_task(self, kind, task_id):
                self.deleted.append((kind, task_id))
                return True

        fake = FakeDatabase()
        self.main.ECOMMERCE_TASKS.clear()
        self.main.ECOMMERCE_TASKS.update({
            "ecommerce_failed": {"id": "ecommerce_failed", "status": "failed", "updated_at": 2},
            "ecommerce_running": {"id": "ecommerce_running", "status": "running", "updated_at": 3},
        })
        with (
            patch.object(self.main, "DATABASE", fake),
            patch.object(self.main, "publish_entity_changed") as publish,
        ):
            result = asyncio.run(self.main.delete_ecommerce_task("ecommerce_failed"))
            self.assertEqual(result, {"task_id": "ecommerce_failed", "deleted": True})
            self.assertNotIn("ecommerce_failed", self.main.ECOMMERCE_TASKS)
            self.assertEqual(fake.deleted, [("ecommerce", "ecommerce_failed")])
            publish.assert_called_once_with("task", "ecommerce")
            with self.assertRaises(self.main.HTTPException) as error:
                asyncio.run(self.main.delete_ecommerce_task("ecommerce_running"))
        self.assertEqual(error.exception.status_code, 409)
        self.assertIn("生成中", error.exception.detail)
        self.assertIn("ecommerce_running", self.main.ECOMMERCE_TASKS)
        self.main.ECOMMERCE_TASKS.clear()

    def test_generation_history_exposes_stable_work_ids_and_favorites(self):
        with tempfile.TemporaryDirectory() as root:
            database = CanvasDatabase(Path(root) / "canvas.db")
            database.initialize()
            database.prepend_history({
                "type": "ecommerce",
                "timestamp": 123.5,
                "images": ["/assets/output/one.png", "/assets/output/two.png"],
                "inputs": [
                    {"role": "source", "url": "/assets/input/source.png"},
                    {"role": "pose", "url": "/assets/input/pose.png"},
                ],
                "image_items": [{"width": 1024, "height": 1280}, {"width": 1024, "height": 1280}],
            })
            records = database.list_history()
            self.assertTrue(records[0]["_history_id"])
            first = self.main.generated_work_items(records, {})
            second = self.main.generated_work_items(records, {first[1]["id"]: {"favorite": True, "updated_at": 456}})
            self.assertEqual([item["id"] for item in first], [item["id"] for item in second])
            self.assertEqual(first[0]["source_url"], "/assets/input/pose.png")
            self.assertEqual((first[0]["width"], first[0]["height"]), (1024, 1280))
            self.assertTrue(second[1]["favorite"])


class EcommerceFrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent.parent
        cls.html = (root / "static" / "ecommerce.html").read_text(encoding="utf-8")
        cls.javascript = (root / "static" / "js" / "ecommerce.js").read_text(encoding="utf-8")
        cls.css = (root / "static" / "css" / "ecommerce.css").read_text(encoding="utf-8")
        cls.asset_manager_html = (root / "static" / "asset-manager.html").read_text(encoding="utf-8")
        cls.asset_manager_javascript = (root / "static" / "js" / "asset-manager.js").read_text(encoding="utf-8")
        cls.asset_manager_css = (root / "static" / "css" / "asset-manager.css").read_text(encoding="utf-8")
        cls.api_javascript = (root / "static" / "js" / "api-settings.js").read_text(encoding="utf-8")
        cls.api_html = (root / "static" / "api-settings.html").read_text(encoding="utf-8")
        cls.index_html = (root / "static" / "index.html").read_text(encoding="utf-8")
        cls.app_settings_html = (root / "static" / "app-settings.html").read_text(encoding="utf-8")
        cls.app_settings_javascript = (root / "static" / "js" / "app-settings.js").read_text(encoding="utf-8")
        cls.common_i18n = (root / "static" / "js" / "i18n" / "common.js").read_text(encoding="utf-8")
        cls.ecommerce_i18n = (root / "static" / "js" / "i18n" / "ecommerce.js").read_text(encoding="utf-8")
        cls.i18n_loader = (root / "static" / "js" / "i18n.js").read_text(encoding="utf-8")
        cls.canvas_javascript = (root / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.canvas_list_javascript = (root / "static" / "js" / "canvas-list.js").read_text(encoding="utf-8")
        cls.smart_canvas_javascript = (root / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
        cls.gpt_chat_html = (root / "static" / "gpt-chat.html").read_text(encoding="utf-8")

    def test_model_panel_contains_generation_parameter_dropdowns(self):
        panel = re.search(r'<section id="advancedSettings".*?</section>', self.html, re.S)
        self.assertIsNotNone(panel)
        panel_html = panel.group(0)
        for control_id in ("ratioSelect", "resolutionSelect", "qualitySelect", "countSelect"):
            self.assertIn(f'id="{control_id}"', panel_html)
        ratio = re.search(r'<select id="ratioSelect">(.*?)</select>', panel_html, re.S)
        self.assertIsNotNone(ratio)
        self.assertIn('<option value="4:5">4:5</option>', ratio.group(1))

    def test_generation_parameters_are_persisted_and_submitted(self):
        for field in ("aspect_ratio:state.aspectRatio", "resolution:state.resolution", "quality:state.quality", "count:state.count"):
            self.assertGreaterEqual(self.javascript.count(field), 2)
        for control_id in ("ratioSelect", "resolutionSelect", "qualitySelect", "countSelect"):
            self.assertRegex(self.javascript, rf"el\.{control_id}\.addEventListener\('change'")

    def test_ecommerce_pending_candidates_match_requested_count(self):
        self.assertIn("function requestedOutputCountForTask(task)", self.javascript)
        self.assertIn("const placeholderCount = requestedOutputCountForTask(task)", self.javascript)
        self.assertIn("return Array.from({length:placeholderCount}", self.javascript)
        self.assertIn("parameters.count ?? task?.count ?? task?.request?.count", self.javascript)
        self.assertIn("data-task-candidate-time", self.javascript)
        self.assertIn("syncCandidateTimer()", self.javascript)
        self.assertIn("const IS_FREE_CREATION = WORKSPACE_VARIANT === 'free-creation'", self.javascript)
        self.assertIn('id="frame-ecommerce" data-src="/static/ecommerce.html?v=2026.08.02.count-pending.1"', self.index_html)
        self.assertIn('id="frame-free-creation" data-src="/static/ecommerce.html?workspace=free-creation&amp;v=2026.08.02.count-pending.1"', self.index_html)
        self.assertIn('/static/js/ecommerce.js?v=2026.08.02.count-pending.1', self.html)
        self.assertIn('/static/css/ecommerce.css?v=2026.08.02.count-pending.1', self.html)

    def test_generation_parameters_wait_for_server_preferences_before_initial_defaults(self):
        self.assertIn("initializing:true", self.javascript)
        self.assertIn("async function waitForPreferenceBootstrap", self.javascript)
        init_body = re.search(r"async function init\(\)\{(.*?)\n    \}", self.javascript, re.S)
        self.assertIsNotNone(init_body)
        self.assertLess(init_body.group(1).index("await waitForPreferenceBootstrap()"), init_body.group(1).index("loadSettings()"))
        populate = re.search(r"function populateModelSelectors\(\)\{(.*?)\n    \}", self.javascript, re.S)
        self.assertIsNotNone(populate)
        self.assertIn("!state.initializing", populate.group(1))

    def test_api_settings_auto_save_without_confirmation_buttons(self):
        self.assertNotIn('api-page-save-btn', self.api_html)
        self.assertNotRegex(self.api_html, r'onclick="save(?:KeyOnly|RhKeyOnly|VolcengineAssetKeys|Providers)')
        self.assertIn('function scheduleProviderAutoSave', self.api_javascript)
        self.assertIn('providerSaveChain = providerSaveChain.then', self.api_javascript)
        self.assertIn("keyInput?.addEventListener('change'", self.api_javascript)
        self.assertIn("settingsContent?.addEventListener('input'", self.api_javascript)
        self.assertIn("saveProviders({render:false, auto:true})", self.api_javascript)

    def test_all_generation_pages_use_enabled_provider_model_lists_without_id_blacklists(self):
        self.assertIn("p.enabled !== false && (p.image_models || []).length", self.canvas_javascript)
        self.assertIn("p.enabled !== false && (p.image_models || []).length", self.smart_canvas_javascript)
        self.assertIn("p.enabled !== false && (p.image_models || []).length", self.gpt_chat_html)
        for source in (self.canvas_javascript, self.smart_canvas_javascript):
            self.assertNotRegex(source, r"p\.id\s*!==\s*'(?:modelscope|volcengine)'.*image_models")
        self.assertEqual(self.canvas_list_javascript.count("api-provider-unification.1"), 2)

    def test_canvas_api_generation_creates_count_pending_outputs_before_task_submit(self):
        run_generator = re.search(r"async function runGenerator\(genId, opts=\{\}\)\{(.*?)\n\}", self.canvas_javascript, re.S)
        self.assertIsNotNone(run_generator)
        body = run_generator.group(1)
        self.assertIn("let pendingIds = out ? Array.from({length:count}, () => uid('p')) : []", body)
        self.assertIn("...pendingIds.map(id => makePendingForRun", body)
        self.assertLess(body.index("...pendingIds.map(id => makePendingForRun"), body.index("createCanvasImageTask(payload"))
        self.assertIn("pending.canvasTaskId = task.task_id", body)

    def test_shell_prompts_for_missing_shiying_api_key_on_first_run(self):
        self.assertIn('id="shiying-api-key-modal"', self.index_html)
        self.assertIn("async function ensureShiyingApiKeyOnboarding", self.index_html)
        self.assertIn("if(shiying?.has_key) return", self.index_html)
        self.assertIn("api_key:key", self.index_html)
        self.assertIn("function broadcastStudioApiChange", self.index_html)
        self.assertIn("broadcastStudioApiChange({type:'providers-changed'", self.index_html)
        self.assertIn("ensureShiyingApiKeyOnboarding()", self.index_html)

    def test_app_settings_supports_first_close_prompt_state(self):
        self.assertIn('id="closeBehaviorNote"', self.app_settings_html)
        self.assertIn("let currentBehavior = 'ask_on_close'", self.app_settings_javascript)
        self.assertIn("['ask_on_close', 'minimize_to_tray', 'exit']", self.app_settings_javascript)
        self.assertIn("appSettings.askOnClosePending", self.app_settings_javascript)
        self.assertIn("appSettings.askOnClosePending", self.common_i18n)

    def test_reference_upload_returns_normalized_image_dimensions(self):
        root = Path(__file__).resolve().parent.parent
        backend = (root / "main.py").read_text(encoding="utf-8")
        self.assertIn("normalize_image_orientation(content)", backend)
        self.assertIn('"orientation_normalized"', backend)

    def test_prompt_only_background_controls_remove_mask_and_manual_composition_switch(self):
        for marker in ("maskToggle", "maskEditor", "maskCanvas", "bindMaskEditor", "uploadMaskIfNeeded", "preserve_source_composition"):
            self.assertNotIn(marker, self.html + self.javascript + self.css)
        self.assertIn("const sourceCompositionLocked = state.operation === 'background_change';", self.javascript)
        incoming = re.search(r"function applyIncomingSettings\(serialized\)\{(.*?)\n    \}", self.javascript, re.S)
        self.assertIsNotNone(incoming)
        for marker in ("syncGenerationParameterControls()", "populateModelSelectors()"):
            self.assertIn(marker, incoming.group(1))

    def test_each_operation_has_an_independent_persistent_workspace(self):
        self.assertIn("workspaces:Object.fromEntries", self.javascript)
        self.assertIn("workspaces:serializableWorkspaces()", self.javascript)
        switch_body = re.search(r"function switchOperation\(operation\)\{(.*?)\n    \}", self.javascript, re.S)
        self.assertIsNotNone(switch_body)
        self.assertIn("captureWorkspace()", switch_body.group(1))
        self.assertIn("restoreWorkspace(operation)", switch_body.group(1))
        self.assertNotIn("state.inputs = {}", switch_body.group(1))

    def test_universal_tab_is_first_and_default_entry(self):
        first_tab = re.search(r'<nav id="operationTabs".*?<button[^>]+data-operation="([^"]+)"[^>]*>\s*<span>01</span>', self.html, re.S)
        self.assertIsNotNone(first_tab)
        self.assertEqual(first_tab.group(1), "universal")
        self.assertIn('const DEFAULT_OPERATION = \'universal\'', self.javascript)
        self.assertIn("operation:DEFAULT_OPERATION", self.javascript)
        self.assertIn("schema_version:SETTINGS_SCHEMA_VERSION", self.javascript)
        self.assertIn("else state.operation = DEFAULT_OPERATION", self.javascript)
        self.assertIn("isTextEditingElement()", self.javascript)
        self.assertIn("shouldIgnoreIncomingSettings()", self.javascript)
        self.assertIn("restoreEditingFocus(control)", self.javascript)
        self.assertIn("const editingControl = isTextEditingElement() ? document.activeElement : null;", self.javascript)
        self.assertIn("[0, 80, 260].forEach", self.javascript)
        self.assertIn("applyIncomingSettings(String(incomingSettings))", self.javascript)

    def test_free_creation_reuses_universal_workspace_with_isolated_raw_prompt_mode(self):
        self.assertIn("switchUI(this, 'free-creation')", self.index_html)
        self.assertRegex(self.index_html, r'id="frame-free-creation"[^>]+workspace=free-creation')
        self.assertIn("'free-creation'", self.index_html)
        self.assertIn('"nav.freeCreation"', self.common_i18n)
        for marker in (
            "const IS_FREE_CREATION = WORKSPACE_VARIANT === 'free-creation'",
            "studio_free_creation_settings_v1",
            "free_creation_current_task",
            "payload.options.prompt_policy = 'free'",
            "function taskMatchesWorkspace(task)",
            "configureWorkspaceVariant()",
            "freeCreation.promptRequired",
        ):
            self.assertIn(marker, self.javascript)
        for key in (
            "freeCreation.title",
            "freeCreation.guideHint",
            "freeCreation.prompt",
            "freeCreation.promptRequired",
            "freeCreation.emptyTitle",
            "freeCreation.emptyHint",
            "freeCreation.sourceRatio",
        ):
            self.assertIn(key, self.ecommerce_i18n)
        self.assertIn("可不上传任何图片", self.ecommerce_i18n)
        self.assertIn("创作素材（可选）", self.ecommerce_i18n)
        self.assertIn("跟随参考图（无图时 1:1）", self.ecommerce_i18n)
        self.assertNotIn("freeCreation.referenceRequired", self.ecommerce_i18n)
        self.assertIn("querySelector('h3 + p')", self.javascript)
        self.assertIn("querySelector('option[value=\"source\"]')", self.javascript)
        self.assertIn("2026.07.29.free-creation-optional-reference.1", self.i18n_loader)
        self.assertIn(".ec-page.is-universal.is-free-creation .ec-operation-controls { order:1; }", self.css)

    def test_universal_tab_supports_ordered_role_aware_references(self):
        self.assertIn('data-operation="universal"', self.html)
        self.assertIn("universal_reference_limit", self.javascript)
        self.assertIn("data-reference-type", self.javascript)
        self.assertIn("dragstart", self.javascript)
        self.assertIn("reference_type:item.reference_type", self.javascript)
        self.assertIn("function universalEntries()", self.javascript)
        self.assertIn(".sort((a,b) => Number(a[1].order || 0) - Number(b[1].order || 0))", self.javascript)
        request_builder = re.search(r"function taskInputsForRequest\(\)\{(.*?)\n    \}", self.javascript, re.S)
        self.assertIsNotNone(request_builder)
        self.assertIn("return universalEntries().map", request_builder.group(1))
        self.assertNotIn("universalInstructionRequired", self.javascript)

    def test_all_tabs_render_clickable_studio_reference_slot(self):
        self.assertIn('id="studioDialog"', self.html)
        self.assertIn('id="studioReferenceGrid"', self.html)
        self.assertIn('id="studioClear"', self.html)
        self.assertIn("const STUDIO_REFERENCE_TYPES", self.javascript)
        self.assertIn("studio_reference:''", self.javascript)
        self.assertIn("studioReferenceCardHtml()", self.javascript)
        self.assertIn("studioReferenceCardHtml('universal')", self.javascript)
        self.assertIn("studioReferenceCardHtml('try_on')", self.javascript)
        self.assertIn("data-open-studio-dialog", self.javascript)
        self.assertIn("function renderStudioDialog()", self.javascript)
        self.assertIn("function selectStudioReference(id)", self.javascript)
        self.assertIn("options:{...currentOptions()}", self.javascript)
        self.assertIn(".ec-studio-reference-card", self.css)
        self.assertIn(".ec-studio-reference-grid", self.css)
        for key in ("ecommerce.studioWhite", "ecommerce.studioGray", "ecommerce.studioBlack", "ecommerce.studioRedGold"):
            self.assertIn(key, self.ecommerce_i18n)

    def test_ecommerce_hints_emphasize_listing_detail_quality(self):
        for phrase in ("电商级提示词", "材质", "Logo", "吊牌文字", "上架氛围"):
            self.assertIn(phrase, self.ecommerce_i18n)

    def test_universal_detail_only_mode_uses_first_uploaded_reference_as_base(self):
        self.assertIn("['model_identity','model_identity','ecommerce.refModelIdentity']", self.javascript)
        self.assertIn("['detail','detail','ecommerce.refDetail']", self.javascript)
        self.assertIn("model_identity:'ecommerce.presetModelIdentity'", self.javascript)
        self.assertIn("detail:'ecommerce.presetDetail'", self.javascript)
        self.assertIn("const baseReferenceKey = IS_FREE_CREATION ? '' : (hasSubject ? '' : (uploadedEntries[0]?.[0] || ''))", self.javascript)
        self.assertIn("ec-base-reference-badge", self.javascript)
        self.assertIn(".ec-universal-reference.is-base-reference", self.css)
        validation = re.search(r"function validateForm\(show=true\)\{(.*?)\n    \}", self.javascript, re.S)
        self.assertIsNotNone(validation)
        self.assertIn("if(!IS_FREE_CREATION && !references.length)", validation.group(1))
        self.assertIn("ecommerce.universalReferenceRequired", validation.group(1))
        self.assertNotIn("freeCreation.referenceRequired", validation.group(1))
        self.assertNotIn("reference_type === 'subject'", validation.group(1))
        comparison = re.search(r"function comparisonReferenceForTask\(task\)\{(.*?)\n    \}", self.javascript, re.S)
        self.assertIsNotNone(comparison)
        self.assertIn("compositionMode === 'base_transfer'", comparison.group(1))
        self.assertIn("base_reference_id", comparison.group(1))
        self.assertIn("['detail','细节图']", self.asset_manager_javascript)

    def test_universal_dock_accepts_multi_image_file_drops_and_creates_frames(self):
        self.assertIn("function bindUniversalDockDrop()", self.javascript)
        self.assertIn("async function handleDroppedUniversalFiles", self.javascript)
        self.assertIn("function droppedFiles(dataTransfer)", self.javascript)
        self.assertIn("function nearestEmptyUniversalRole(clientX, clientY)", self.javascript)
        self.assertIn("nearestEmptyUniversalRole(event.clientX, event.clientY)", self.javascript)
        self.assertIn("item.getAsFile?.()", self.javascript)
        self.assertIn("!type || allowedTypes.has(type)", self.javascript)
        self.assertIn("createUniversalReference", self.javascript)
        self.assertIn("await uploadInputPairs(images.slice(0, accepted).map((file, index) => ({file, role:targets[index]})))", self.javascript)
        self.assertIn("data-reference-type", self.javascript)
        self.assertIn("window.addEventListener('drop', clearDragState, true)", self.javascript)
        self.assertNotIn(".ec-universal-dock.is-file-dragover::after", self.css)
        self.assertIn(".ec-universal-dock.is-file-dragover", self.css)

    def test_header_hides_internal_routing_and_capability_status(self):
        self.assertNotIn('id="routeSummary"', self.html)
        self.assertNotIn('id="capabilityStatus"', self.html)
        self.assertIn('id="historyToggle"', self.html)

    def test_comparison_uses_selected_generated_image_for_both_backdrops(self):
        self.assertIn("function setComparisonBackdrops(url)", self.javascript)
        self.assertIn("[el.beforeBackdrop, el.afterBackdrop]", self.javascript)
        self.assertIn("setComparisonForeground(el.beforeImage, reference?.url || '')", self.javascript)
        self.assertIn("setComparisonBackdrops(displayedUrl)", self.javascript)
        self.assertNotRegex(
            self.css,
            r"html\.studio-theme-dark\s+\.ec-before-image[^{]*\{[^}]*background\s*:\s*var\(--ec-bg\)",
        )
        backdrop_rule = re.search(r"\.ec-compare-backdrop\s*\{([^}]+)\}", self.css)
        self.assertIsNotNone(backdrop_rule)
        brightness = re.search(r"brightness\(([\d.]+)\)", backdrop_rule.group(1))
        blur = re.search(r"blur\(([\d.]+)px\)", backdrop_rule.group(1))
        self.assertIsNotNone(brightness)
        self.assertIsNotNone(blur)
        self.assertGreaterEqual(float(brightness.group(1)), 0.72)
        self.assertLessEqual(float(blur.group(1)), 22)

    def test_compare_handle_and_add_reference_icon_are_centered(self):
        def last_rule(selector):
            matches = list(re.finditer(rf"{re.escape(selector)}\s*\{{([^}}]+)\}}", self.css, re.S))
            self.assertTrue(matches, selector)
            return matches[-1].group(1)

        handle_rule = last_rule(".ec-compare-handle")
        self.assertIn("display:flex", handle_rule)
        self.assertIn("align-items:center", handle_rule)
        self.assertIn("justify-content:center", handle_rule)
        self.assertIn("overflow:visible", handle_rule)

        handle_text_rule = last_rule(".ec-compare-handle span")
        self.assertIn("flex:0 0 auto", handle_text_rule)
        self.assertIn("margin:0", handle_text_rule)
        self.assertIn("line-height:1", handle_text_rule)

        add_reference_rule = last_rule(".ec-universal-dock .ec-add-reference-action")
        self.assertIn("display:flex", add_reference_rule)
        self.assertIn("align-items:center", add_reference_rule)
        self.assertIn("justify-content:center", add_reference_rule)

    def test_universal_tab_uses_six_presets_and_a_bottom_action_dock(self):
        self.assertIn("const UNIVERSAL_PRESET_ROLES = ['subject','full_garment','detail','detail','pose','scene']", self.javascript)
        self.assertIn('id="universalDock"', self.html)
        self.assertIn('id="universalDockInputs"', self.html)
        self.assertIn('id="universalDockActions"', self.html)
        self.assertNotIn('id="universalPrimarySummary"', self.html)
        self.assertNotIn('id="universalPrimarySlot"', self.html)
        self.assertIn('id="addUniversalReference"', self.html)
        self.assertIn("syncUniversalLayout()", self.javascript)
        self.assertIn("inputTarget.appendChild(el.inputModule)", self.javascript)
        self.assertIn("actionTarget.appendChild(el.generateActions)", self.javascript)
        self.assertIn(".ec-universal-dock { position:fixed", self.css)
        self.assertIn("grid-template-columns:repeat(6,minmax(0,1fr))", self.css)
        self.assertIn(".ec-universal-dock.has-many-references", self.css)
        self.assertIn("ec-add-reference-action", self.css)
        self.assertIn("transform:translateX(-50%)", self.css)
        self.assertIn("seedUniversalPresetsIfEmpty", self.javascript)
        self.assertNotIn("renderUniversalPrimarySummary", self.javascript)
        self.assertNotIn("bindInputSlots(el.universalPrimarySlot)", self.javascript)
        self.assertIn("bindComposingInput(input", self.javascript)
        self.assertIn("data-reference-drag-handle", self.javascript)
        self.assertNotIn('[data-reference-key][draggable="true"]', self.javascript)
        for marker in ("ecommerce.presetModel", "ecommerce.presetGarment", "ecommerce.presetDetail", "ecommerce.presetPose", "ecommerce.presetScene"):
            self.assertIn(marker, self.javascript)

    def test_regular_operation_generate_action_stays_in_the_control_panel(self):
        selector = ".ec-page:not(.is-universal):not(.is-try-on) .ec-generate-actions"
        matches = list(re.finditer(rf"{re.escape(selector)}\s*\{{([^}}]+)\}}", self.css, re.S))
        self.assertTrue(matches, selector)
        rule = matches[-1].group(1)
        self.assertIn("position:sticky", rule)
        self.assertIn("bottom:0", rule)
        self.assertIn("left:auto", rule)
        self.assertIn("width:auto", rule)

    def test_try_on_uses_dedicated_atelier_layout(self):
        self.assertIn("function renderTryOnInputs()", self.javascript)
        self.assertIn("state.operation === 'try_on'", self.javascript)
        self.assertIn("el.ecommercePage?.classList.toggle('is-try-on', tryOn)", self.javascript)
        self.assertIn("renderTryOnInputs();", self.javascript)
        for marker in ("ec-tryon-studio", "ec-tryon-stepbar", "ec-tryon-materials", "ec-tryon-reference-grid", "ec-tryon-closet-grid", "ec-tryon-dialogue-card", "ec-tryon-message-box", "ec-tryon-look-stage", "ec-tryon-dressup-board", "ec-tryon-model-panel", "ec-tryon-look-rail", "ec-tryon-body-anchor"):
            self.assertIn(marker, self.javascript + self.css)
        self.assertNotIn('data-option-button="garment_category"', self.javascript)
        self.assertNotIn("tryOnCategoryLabel", self.javascript)
        self.assertNotIn("TRY-ON ATELIER", self.javascript)
        self.assertNotIn("ec-tryon-compose-card", self.javascript + self.css)
        self.assertIn(".ec-page.is-try-on .ec-workspace", self.css)
        self.assertIn(".ec-page.is-try-on .ec-control-panel", self.css)
        self.assertIn("grid-template-rows:minmax(0,1fr) auto", self.css)
        self.assertIn("scrollbar-gutter:stable", self.css)
        self.assertIn(".ec-page.is-try-on .ec-model-panel", self.css)
        self.assertIn("display:none !important", self.css)
        self.assertIn(".ec-page.is-try-on .ec-generate-actions", self.css)
        self.assertIn("tryOnMessageActionSlot", self.javascript)
        self.assertIn("data-tryon-cutout-src", self.javascript)
        self.assertIn("function cutoutTryOnPreviewImage", self.javascript)
        self.assertIn("function tryOnPreviewItemHtml", self.javascript)
        self.assertNotIn("function tryOnLayerHtml", self.javascript)
        self.assertIn("TRY_ON_WARDROBE_ROLES", self.javascript)
        self.assertIn("TRY_ON_POSE_ROLE", self.javascript)
        self.assertIn("TRY_ON_REQUEST_ROLES", self.javascript)
        for role in ("upper_garment", "lower_garment", "full_garment", "shoes", "accessory", "pose"):
            self.assertIn(role, self.javascript)
        for role in ("model_identity", "detail"):
            self.assertIn(role, self.javascript)
        self.assertIn("--ec-tryon-shadow-soft", self.css)
        self.assertIn("--ec-tryon-shadow-card", self.css)
        for key in ("ecommerce.tryOnPreviewTitle", "ecommerce.tryOnWardrobe", "ecommerce.tryOnLookRail", "ecommerce.tryOnPreviewBoardHint", "ecommerce.tryOnPoseStage", "ecommerce.tryOnDialogTitle", "ecommerce.tryOnDialogHint", "ecommerce.tryOnOutfitRequired"):
            self.assertIn(key, self.javascript)
        self.assertIn("const outfitCount = tryOnOutfitCount();", self.javascript)
        self.assertIn("Number(sourceReady) + outfitCount + Number(Boolean(state.inputs.pose?.url))", self.javascript)
        self.assertIn("TRY_ON_REQUEST_ROLES.includes(role)", self.javascript)
        self.assertIn("ec-tryon-reference-grid ec-tryon-closet-grid", self.javascript)
        self.assertIn("grid-template-columns:repeat(4,minmax(0,1fr));", self.css)
        self.assertIn(".ec-tryon-slot-card.is-model,\n.ec-tryon-slot-card.is-outfit", self.css)
        self.assertNotIn("grid-template-columns:minmax(250px,.9fr) minmax(0,1.1fr)", self.css)

    def test_try_on_reference_slots_support_stacked_candidates(self):
        self.assertIn('id="fileInput" type="file" accept="image/png,image/jpeg,image/webp" multiple hidden', self.html)
        self.assertIn("const TRY_ON_MULTI_REFERENCE_ROLES = ['source', ...TRY_ON_REQUEST_ROLES]", self.javascript)
        for marker in (
            "alternates:candidates",
            "selected_index:safeIndex",
            "function setTryOnInputCandidate(role, candidate)",
            "function selectTryOnReference(role, index, direction=0)",
            "function shiftTryOnReference(role, step)",
            "function tryOnSwitchMeta(direction, fromItem)",
            "async function handleSelectedFiles(files, role)",
            "await uploadInputPairs(images.map(file => ({file,role})))",
            "function uploadInputPairs(pairs)",
            "return Promise.all(pairs.map(pair => uploadReferenceFile(pair.file)))",
            "function uploadedImageDimensions(uploaded)",
            "data-tryon-stack-step",
            "ec-tryon-transition-card",
            "slot.addEventListener('wheel'",
            "event.key !== 'ArrowLeft' && event.key !== 'ArrowRight'",
            "setTryOnInputCandidate(pair.role, previewInput)",
            "function referenceDisplayUrl(item)",
            "function stripUploadPreviewFields(value)",
            "function applyPreviewInput(pair)",
            "preview_url:previewUrl",
            "upload_token:token",
            "renderInputs();\n        validateForm(false);\n        try {",
            "setTryOnInputCandidate(state.activeUploadRole, nextInput)",
            "syncTryOnCurrentCandidate(preview.key)",
            "return tryOnInputEntriesForRequest().filter",
            "url:item.url,",
        ):
            self.assertIn(marker, self.javascript)
        self.assertNotIn("MAX_PARALLEL_REFERENCE_UPLOADS", self.javascript)
        self.assertNotIn("try { await imageDimensions(previewUrl); }", self.javascript)
        self.assertIn("inputs:serializableInputs(workspace.inputs || {})", self.javascript)
        for marker in (
            ".ec-page.is-try-on .ec-upload-slot.has-reference-stack",
            ".ec-tryon-card-shadow",
            ".ec-page.is-try-on .ec-tryon-transition-card",
            "@keyframes ec-tryon-card-next-in",
            "@keyframes ec-tryon-card-next-out",
            "@keyframes ec-tryon-card-prev-in",
            "@keyframes ec-tryon-card-prev-out",
            ".ec-tryon-look-thumb em",
        ):
            self.assertIn(marker, self.css)
        self.assertNotIn("data-tryon-select-index", self.javascript)
        self.assertNotIn("ec-tryon-stack-strip", self.javascript)
        self.assertNotIn(".ec-tryon-stack-strip", self.css)

    def test_try_on_reference_slot_types_drag_sort_and_panel_generation_order(self):
        for marker in (
            "referenceSlotTypes:[]",
            "reference_slot_types",
            "assetReferenceTypeSelect",
            "slot_order:[]",
            "const TRY_ON_SELECTABLE_REFERENCE_ROLES",
            "function referenceSlotTypesForContext(context='universal', fallbackRole='')",
            "function applySlotTypeToInput(item, slotTypeId, fallbackRole='prop')",
            "custom_type_label",
            "function editReferenceTypeName(item, fallbackRole='prop', value='')",
            "function referenceTypeComboHtml",
            "function beginReferenceTypeInlineEdit(select, item, fallbackRole='prop', onCommit=()=>{})",
            "function bindReferenceTypeInlineControls(select, itemGetter, fallbackRoleGetter, onCommit)",
            "function requestReferenceLabel(item, fallback='')",
            "function tryOnSlotOrder()",
            "function orderedTryOnWardrobeRoles()",
            "function tryOnInputEntriesForRequest()",
            "function tryOnRequestRoleForSlot(slotRole, item={})",
            "function tryOnSlotDisplayLabel(input, item=state.inputs[input?.role] || {})",
            "const displayLabel = tryOnStack ? tryOnSlotDisplayLabel(input, asset) : t(input.labelKey)",
            "const visibleSlotLabel = tryOnStack ? '' : `<b>${escapeHtml(displayLabel)}</b>`",
            "const label = tryOnSlotDisplayLabel(item, asset)",
            "function tryOnReorderedPreviewOrder(draggedRole, targetRole)",
            "function updateTryOnDragPreview(draggedRole, targetRole)",
            "clearTryOnDragPreview()",
            "orderedTryOnWardrobeRoles().map(tryOnWardrobeCard)",
            "orderedWardrobe.forEach(item => entries.push([item.role, state.inputs[item.role]]))",
            "data-tryon-reference-type",
            "data-reference-type-inline",
            "data-reference-type-button",
            "data-tryon-drag-handle",
            "currentOptions().slot_order = order",
            "tryOnInputEntriesForRequest().filter",
            "tryOnRequestRoleForSlot(slotRole, item)",
            "reference_id:item.reference_id || `${slotRole}_${index + 1}`",
            "el.assetReferenceTypeSelect?.addEventListener('change', renderAssetGrid)",
        ):
            self.assertIn(marker, self.javascript)
        self.assertIn("'model_identity'", self.javascript)
        self.assertIn("'detail'", self.javascript)
        self.assertIn("TRY_ON_REQUEST_ROLES = ['model_identity', ...TRY_ON_PREVIEW_LAYER_ORDER, 'detail', 'pose']", self.javascript)
        self.assertIn('id="assetReferenceTypeSelect"', self.html)
        for marker in (
            ".ec-dialog-toolbar.has-reference-type",
            ".ec-page.is-try-on .ec-input-module > .ec-section-head",
            "display:none;",
            ".ec-page.is-try-on .ec-floating-upload-actions",
            ".ec-page.is-try-on .ec-tryon-type-row",
            ".ec-reference-type-combo",
            ".ec-reference-type-button",
            ".ec-reference-type-inline-input",
            ".ec-tryon-drag-handle",
            ".ec-tryon-closet-grid.is-reordering",
            ".ec-tryon-slot-card.is-drag-preview",
        ):
            self.assertIn(marker, self.css)
        self.assertNotIn("data-tryon-reference-type-name", self.javascript)
        self.assertNotIn("data-reference-type-name", self.javascript)
        self.assertNotIn("window.prompt", self.javascript)
        floating_rule = re.search(r"\.ec-page\.is-try-on \.ec-floating-upload-actions\s*\{([^}]+)\}", self.css, re.S)
        self.assertIsNotNone(floating_rule)
        self.assertIn("right:12px;", floating_rule.group(1))
        self.assertIn("bottom:12px;", floating_rule.group(1))
        self.assertNotIn("top:", floating_rule.group(1))
        self.assertNotIn("left:", floating_rule.group(1))

    def test_asset_manager_exposes_global_reference_type_manager(self):
        self.assertIn('data-tab="reference-types"', self.asset_manager_html)
        for marker in (
            "let referenceSlotTypes = []",
            "let selectedReferenceTypeId = ''",
            "const REFERENCE_TYPE_ROLE_OPTIONS",
            "apiJson('/api/reference-slot-types')",
            "function renderReferenceTypesManager()",
            "function saveReferenceSlotTypesFromDom()",
            "function addReferenceSlotType()",
            "function moveReferenceSlotType(id, direction)",
            "function deleteReferenceSlotType(id)",
            "data-reference-type-select",
            "data-reference-type-save",
            "referenceTypePreviewSelect",
        ):
            self.assertIn(marker, self.asset_manager_javascript)
        self.assertIn("['model_identity','模特形象']", self.asset_manager_javascript)
        for marker in (
            ".reference-type-editor",
            ".reference-type-row",
            ".reference-type-grid",
            ".reference-type-enabled",
        ):
            self.assertIn(marker, self.asset_manager_css)

    def test_result_preview_backgrounds_follow_theme(self):
        root = re.search(r":root\s*\{(.*?)\n\}", self.css, re.S)
        dark = re.search(r"html\.studio-theme-dark\s*\{(.*?)\n\}", self.css, re.S)
        self.assertIsNotNone(root)
        self.assertIsNotNone(dark)
        for marker in (
            "--ec-result-panel-bg:#f7f1e6",
            "--ec-result-raised-bg:#fffaf4",
            "--ec-result-soft-bg:#efe2d2",
            "--ec-result-frame-bg:#faf2e7",
            "--ec-result-stage-bg:#f1e5d7",
        ):
            self.assertIn(marker, root.group(1))
        self.assertNotIn("50%,#000", root.group(1))
        for marker in (
            "--ec-result-panel-bg:var(--ec-panel)",
            "--ec-result-raised-bg:var(--ec-panel-raised)",
            "--ec-result-soft-bg:var(--ec-panel-soft)",
            "--ec-result-frame-bg:var(--ec-panel)",
            "--ec-result-stage-bg:var(--ec-bg)",
        ):
            self.assertIn(marker, dark.group(1))
        self.assertNotIn("50%,#000", dark.group(1))
        for marker in (
            ".ec-result-panel { background:var(--ec-result-panel-bg); }",
            "background:var(--ec-result-frame-bg)",
            "background:var(--ec-result-stage-bg)",
        ):
            self.assertIn(marker, self.css)

    def test_spatial_theme_uses_sidebar_pearl_and_neutral_graphite_tokens(self):
        self.assertIn("--ec-bg:#f6eee4", self.css)
        self.assertIn("--ec-panel:#faf2e7", self.css)
        self.assertIn("--ec-accent:#9a6636", self.css)
        self.assertIn("--ec-accent-contrast:#fff9f0", self.css)
        dark = re.search(r"html\.studio-theme-dark\s*\{(.*?)\n\}", self.css, re.S)
        self.assertIsNotNone(dark)
        self.assertIn("--ec-bg:#1a1a1a", dark.group(1))
        self.assertIn("--ec-panel:#1e1e1e", dark.group(1))
        self.assertIn("--ec-accent:#3a3a39", dark.group(1))
        for retired_token in ("#08090c", "#111722", "#171d29", "#202838", "#d8dee9"):
            self.assertNotIn(retired_token, dark.group(1))

    def test_universal_presets_are_seeded_once_and_can_be_deleted_to_one(self):
        seed_body = re.search(r"function seedUniversalPresetsIfEmpty\(\)\{(.*?)\n    \}", self.javascript, re.S)
        self.assertIsNotNone(seed_body)
        self.assertIn("if(universalEntries().length) return", seed_body.group(1))
        self.assertIn("if(entries.length <= 1)", self.javascript)
        remove_handler = re.search(r"querySelectorAll\('\[data-remove-reference\]'\).*?\n        \}\)\);", self.javascript, re.S)
        self.assertIsNotNone(remove_handler)
        self.assertNotIn("seedUniversalPresetsIfEmpty()", remove_handler.group(0))

    def test_universal_auto_composition_help_is_removed(self):
        self.assertNotIn("ec-universal-prompt-help", self.html + self.javascript)

    def test_result_footer_only_keeps_candidate_rail(self):
        footer = re.search(r'<div class="ec-result-footer">(.*?)</div>\s*</div>', self.html, re.S)
        self.assertIsNotNone(footer)
        self.assertIn('id="candidateList"', footer.group(1))
        for control_id in ("downloadPreview", "qualityReview", "exportFinal", "saveAsset"):
            self.assertNotIn(f'id="{control_id}"', self.html)
        self.assertNotIn("ec-result-actions", self.html + self.css)

    def test_no_compatible_model_error_renders_inside_result_preview(self):
        self.assertIn('id="emptyResultNotice"', self.html)
        self.assertIn('id="resultErrorOverlay"', self.html)
        self.assertIn("function showResultPreviewError", self.javascript)
        self.assertIn("showResultPreviewError(t('ecommerce.noCompatibleModel'))", self.javascript)
        self.assertIn("isCompatibleModelError(error.message)", self.javascript)
        self.assertIn(".ec-empty-result.has-error", self.css)
        self.assertIn(".ec-result-error-overlay", self.css)

    def test_failed_tasks_have_clear_controls(self):
        self.assertIn('id="resultErrorClear"', self.html)
        self.assertIn("async function clearTask", self.javascript)
        self.assertIn("data-clear-task", self.javascript)
        self.assertIn("method:'DELETE'", self.javascript)
        self.assertIn(".ec-candidate-clear", self.css)

    def test_reference_preview_crop_and_history_are_persisted(self):
        for control_id in ("referencePreview", "referencePreviewImage", "referenceCropStage", "referenceCropBox", "applyReferenceCrop"):
            self.assertIn(f'id="{control_id}"', self.html)
        for marker in ("crop_history", "original_url", "data-preview-reference", "canvas.toBlob", "'/api/ai/upload'"):
            self.assertIn(marker, self.javascript)
        for ratio in ("1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "9:16", "16:9"):
            self.assertIn(f'data-crop-ratio="{ratio}"', self.html)

    def test_pose_reference_is_used_as_the_comparison_base(self):
        self.assertIn('id="compareBeforeLabel"', self.html)
        self.assertIn("function taskPoseReference(task)", self.javascript)
        self.assertIn("function comparisonReferenceForTask(task)", self.javascript)
        self.assertIn("ecommerce.poseReference", self.javascript)
        comparison = re.search(r"function comparisonReferenceForTask\(task\)\{(.*?)\n    \}", self.javascript, re.S)
        self.assertIsNotNone(comparison)
        self.assertLess(comparison.group(1).index("taskPoseReference(task)"), comparison.group(1).index("sourceReferenceForTask(task)"))

    def test_ecommerce_preferences_are_written_in_order(self):
        self.assertIn("preferenceWriteChain:Promise.resolve()", self.javascript)
        self.assertIn("state.preferenceWriteChain = state.preferenceWriteChain.then(write, write)", self.javascript)

    def test_api_settings_has_builtin_grsai_contract(self):
        self.assertIn("GRSAI_DEFAULT_BASE_URL", self.api_javascript)
        self.assertIn("GRSAI_DEFAULT_IMAGE_MODELS", self.api_javascript)
        self.assertIn("'grsai'", self.api_javascript)

    def test_universal_result_uses_wide_fitted_frame_with_blurred_image_backdrops(self):
        self.assertIn('class="ec-result-frame"', self.html)
        self.assertLess(self.html.index('id="resultMeta"'), self.html.index('id="compareStage"'))
        self.assertLess(self.html.index('id="compareStage"'), self.html.index('id="candidateList"'))
        self.assertIn('id="beforeBackdrop"', self.html)
        self.assertIn('id="afterBackdrop"', self.html)
        self.assertLess(self.html.index('id="beforeBackdrop"'), self.html.index('id="beforeImage"'))
        self.assertLess(self.html.index('id="afterBackdrop"'), self.html.index('id="afterImage"'))
        self.assertIn(".ec-page.is-universal .ec-result-frame", self.css)
        self.assertIn("aspect-ratio:16/9", self.css)
        self.assertIn(".ec-compare-backdrop", self.css)
        self.assertIn("filter:blur(", self.css)
        self.assertIn("grid-template-rows:52px minmax(0,1fr) 96px", self.css)
        self.assertIn("function setComparisonForeground", self.javascript)
        self.assertIn("function setComparisonBackdrops", self.javascript)

    def test_frontend_tracks_multiple_tasks_without_disabling_generation(self):
        self.assertIn("tasksById:new Map()", self.javascript)
        self.assertIn("activeTaskIds:new Set()", self.javascript)
        self.assertIn("/api/ecommerce/tasks/status", self.javascript)
        self.assertIn("scheduleTaskPolling(100)", self.javascript)
        self.assertIn("display_index:++completedOrder", self.javascript)
        self.assertIn("data-candidate-sequence", self.javascript)
        self.assertIn("function navigateCompletedResult(step)", self.javascript)
        self.assertIn("const steps = {ArrowLeft:-1,ArrowUp:-1,ArrowRight:1,ArrowDown:1}", self.javascript)
        self.assertIn("document.addEventListener('keydown', handleResultNavigationKeydown)", self.javascript)
        self.assertIn("ecommerce.generatedSequence", self.ecommerce_i18n)
        create_body = re.search(r"async function createTask\(parentTaskId=''\)\{(.*?)\n    \}", self.javascript, re.S)
        self.assertIsNotNone(create_body)
        self.assertNotIn("generateButton.disabled", create_body.group(1))
        self.assertNotIn("keepVisibleResult", create_body.group(1))
        self.assertIn("renderTaskResult(stored)", create_body.group(1))

    def test_api_settings_exposes_builtin_visual_model_and_url_completion(self):
        self.assertIn("LOCAL_VISION_DEFAULT_MODEL", self.api_javascript)
        self.assertIn("normalizeOpenAiCompatibleBaseUrl", self.api_javascript)
        self.assertIn("show-local-vision", self.api_javascript)
        self.assertIn('id="chatModelsTitle"', self.api_html)


if __name__ == "__main__":
    unittest.main()
