import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from canvas_core.topaz_video import (
    TopazInstallation,
    TopazSignature,
    TopazUpscaleSettings,
    TopazVideoError,
    available_topaz_models,
    build_topaz_upscale_command,
    candidate_topaz_install_dirs,
    parse_ffmpeg_progress,
    parse_ffprobe_video,
    preferred_topaz_model,
    inspect_authenticode,
    resolve_target_dimensions,
    resolve_topaz_installation,
    topaz_child_environment,
    topaz_filter_available,
    topaz_filter_expression,
)


class TopazVideoTests(unittest.TestCase):
    def ready_installation(self, root: Path) -> TopazInstallation:
        model_dir = root / "definitions"
        model_data_dir = root / "model-data"
        model_dir.mkdir()
        model_data_dir.mkdir()
        (model_dir / "tvai.tz").write_bytes(b"definition")
        ffmpeg = root / "ffmpeg.exe"
        ffprobe = root / "ffprobe.exe"
        ffmpeg.write_bytes(b"exe")
        ffprobe.write_bytes(b"exe")
        return TopazInstallation(
            install_dir=root,
            ffmpeg_path=ffmpeg,
            ffprobe_path=ffprobe,
            model_dir=model_dir,
            model_data_dir=model_data_dir,
            signature=TopazSignature("Valid", "CN=Topaz Labs LLC", "7.0.0"),
            filter_available=True,
        )

    def test_discovers_configured_installation_and_rejects_invalid_signature(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ffmpeg.exe").write_bytes(b"ffmpeg")
            (root / "ffprobe.exe").write_bytes(b"ffprobe")
            model_dir = root / "models"
            model_dir.mkdir()
            (model_dir / "tvai.tz").write_bytes(b"model")
            with (
                patch("canvas_core.topaz_video.candidate_topaz_model_dirs", return_value=[model_dir]),
                patch("canvas_core.topaz_video.candidate_topaz_model_data_dirs", return_value=[model_dir]),
            ):
                invalid = resolve_topaz_installation(
                    str(root),
                    signature_inspector=lambda _path: TopazSignature("HashMismatch", "CN=Topaz Labs LLC", "7.0.0"),
                    filter_probe=lambda _path: True,
                )
                valid = resolve_topaz_installation(
                    str(root),
                    signature_inspector=lambda _path: TopazSignature("Valid", "CN=Topaz Labs LLC", "7.0.0"),
                    filter_probe=lambda _path: True,
                )
        self.assertFalse(invalid.ready)
        self.assertIn("签名", invalid.error)
        self.assertTrue(valid.ready)

    def test_candidate_path_accepts_executable_or_directory(self):
        with patch.dict(os.environ, {"TOPAZ_VIDEO_AI_DIR": "D:/Topaz/ffmpeg.exe"}, clear=False):
            candidates = candidate_topaz_install_dirs()
        self.assertEqual(candidates[0], Path("D:/Topaz"))

    def test_filter_probe_uses_argument_array_without_shell(self):
        def runner(args, **kwargs):
            self.assertEqual(args[-2:], ["-hide_banner", "-filters"])
            self.assertNotIn("shell", kwargs)
            return subprocess.CompletedProcess(args, 0, " T. tvai_up V->V", "")

        self.assertTrue(topaz_filter_available(Path("D:/Topaz/ffmpeg.exe"), runner=runner))

    def test_signature_inspection_passes_path_through_child_environment(self):
        payload = json.dumps({"Status": "Valid", "Signer": "CN=Topaz Labs LLC", "Version": "7.0.0"})
        completed = subprocess.CompletedProcess([], 0, payload, "")
        with (
            patch("canvas_core.topaz_video.os.name", "nt"),
            patch("canvas_core.topaz_video.shutil.which", return_value="powershell.exe"),
            patch("canvas_core.topaz_video.subprocess.run", return_value=completed) as run,
        ):
            signature = inspect_authenticode(Path("D:/Topaz/ffmpeg.exe"))
        self.assertTrue(signature.valid)
        self.assertEqual(
            os.path.normcase(run.call_args.kwargs["env"]["SHIYIN_TOPAZ_SIGNATURE_TARGET"]),
            os.path.normcase(str(Path("D:/Topaz/ffmpeg.exe"))),
        )

    def test_available_models_filters_non_upscale_definitions_and_prefers_proteus(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for name in ("prob-4.json", "amq-13.json", "apo-8.json", "video-encoders.json"):
                (root / name).write_text("{}", encoding="utf-8")
            models = available_topaz_models(root)
        self.assertEqual({item["id"] for item in models}, {"prob-4", "amq-13"})
        self.assertEqual(preferred_topaz_model(models), "prob-4")

    def test_resolves_landscape_vertical_and_scaled_targets(self):
        self.assertEqual(resolve_target_dimensions(1280, 720, "2x"), (2560, 1440))
        self.assertEqual(resolve_target_dimensions(1920, 1080, "2160p"), (3840, 2160))
        self.assertEqual(resolve_target_dimensions(1080, 1920, "1440p"), (1440, 2560))

    def test_advanced_filter_contains_validated_topaz_parameters(self):
        settings = TopazUpscaleSettings(
            model="prob-4",
            target="2160p",
            output_width=3840,
            output_height=2160,
            noise=0.25,
            details=0.1,
            pre_noise=0.02,
            device="0",
            vram=0.8,
        )
        expression = topaz_filter_expression(settings)
        self.assertIn("tvai_up=model=prob-4:scale=0:w=3840:h=2160", expression)
        self.assertIn(":noise=0.25:details=0.1:", expression)
        self.assertIn(":prenoise=0.02:", expression)
        self.assertIn(":kcolor=1", expression)
        self.assertIn(":device=0:vram=0.8:", expression)

    def test_invalid_advanced_values_are_rejected(self):
        with self.assertRaises(TopazVideoError):
            TopazUpscaleSettings(noise=2).validated()
        with self.assertRaises(TopazVideoError):
            TopazUpscaleSettings(device="0;calc.exe").validated()
        with self.assertRaises(TopazVideoError):
            TopazUpscaleSettings(encoder="custom").validated()
        with self.assertRaises(TopazVideoError):
            TopazUpscaleSettings(encoder="libx264").validated()

    def test_builds_safe_command_with_audio_and_progress(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            installation = self.ready_installation(root)
            source = root / "input clip.mp4"
            source.write_bytes(b"video")
            output = root / "output clip.mp4"
            settings = TopazUpscaleSettings(model="prob-4", target="2x", quality="high")
            command = build_topaz_upscale_command(
                installation,
                source,
                output,
                settings,
                available_models=["prob-4"],
            )
        self.assertEqual(command[0], str(installation.ffmpeg_path))
        self.assertIn(str(source), command)
        filter_argument = command[command.index("-vf") + 1]
        self.assertIn("tvai_up=model=prob-4:scale=2", filter_argument)
        self.assertIn("-progress", command)
        self.assertIn("-c:a", command)
        self.assertNotIn("shell", command)

    def test_child_environment_does_not_mutate_process_environment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            installation = self.ready_installation(Path(temp_dir))
            before = os.environ.get("TVAI_MODEL_DIR")
            child = topaz_child_environment(installation)
        self.assertEqual(child["TVAI_MODEL_DIR"], str(installation.model_dir))
        self.assertEqual(os.environ.get("TVAI_MODEL_DIR"), before)

    def test_parses_ffprobe_and_ffmpeg_progress(self):
        metadata = parse_ffprobe_video(
            json.dumps(
                {
                    "streams": [{"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080}],
                    "format": {"duration": "10.0"},
                }
            )
        )
        progress = parse_ffmpeg_progress(
            ["frame=150", "fps=30", "out_time_us=5000000", "speed=0.5x", "progress=continue"],
            metadata["duration"],
        )
        self.assertEqual(metadata["width"], 1920)
        self.assertEqual(progress["progress"], 0.5)
        self.assertEqual(progress["frame"], 150)


if __name__ == "__main__":
    unittest.main()
