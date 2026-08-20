import ast
import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from canvas_core.kling_cli import (
    KlingCliEnvironment,
    KlingCliError,
    KlingCliService,
    parse_kling_capabilities,
)


def completed(payload, *, exit_code=0, stderr=""):
    return subprocess.CompletedProcess(
        args=[],
        returncode=exit_code,
        stdout=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        stderr=stderr.encode("utf-8"),
    )


class KlingCliTests(unittest.TestCase):
    def test_default_process_runner_builds_one_safe_command_array(self):
        service = KlingCliService(
            environment=KlingCliEnvironment(
                node_path="node.exe",
                npm_path="npm.cmd",
                kling_path="kling.cmd",
                entrypoint_path="cli.js",
                version="0.1.3",
            )
        )
        with patch(
            "canvas_core.kling_cli.subprocess.run",
            return_value=completed({"ok": True, "body": {"availableModels": {}}}),
        ) as run:
            service.capabilities()

        command = run.call_args.args[0]
        self.assertEqual(
            command,
            ["node.exe", "cli.js", "who_am_i", "--quiet"],
        )
        self.assertFalse(run.call_args.kwargs["shell"])

    def test_windows_default_runner_never_opens_a_console_window(self):
        with (
            patch("canvas_core.kling_cli.os.name", "nt"),
            patch(
                "canvas_core.kling_cli.subprocess.run",
                return_value=completed({"ok": True}),
            ) as run,
        ):
            from canvas_core.kling_cli import default_kling_process_runner

            default_kling_process_runner("node.exe", ["cli.js", "who_am_i"])

        self.assertEqual(
            run.call_args.kwargs["creationflags"] & 0x08000000,
            0x08000000,
        )

    def test_all_blocking_kling_processes_share_the_hidden_runner(self):
        import canvas_core.kling_cli as kling_cli

        tree = ast.parse(Path(kling_cli.__file__).read_text(encoding="utf-8"))
        direct_runs = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
            and node.func.attr == "run"
        ]

        self.assertEqual(
            len(direct_runs),
            1,
            "所有同步可灵 CLI 调用必须统一经过 default_kling_process_runner，避免遗漏 Windows 隐藏窗口参数。",
        )

    def test_capabilities_keep_separate_text_and_image_video_schemas(self):
        payload = {
            "ok": True,
            "body": {
                "availableModels": {
                    "text_to_video": {
                        "models": [
                            {
                                "model": "kling-text",
                                "alias": "文生视频",
                                "arguments": [
                                    {
                                        "name": "aspect_ratio",
                                        "required": False,
                                        "default": "16:9",
                                        "allowedValues": ["16:9", "9:16"],
                                    }
                                ],
                                "inputs": [],
                            }
                        ]
                    },
                    "image_to_video": {
                        "models": [
                            {
                                "model": "kling-image",
                                "alias": "图生视频",
                                "arguments": [
                                    {
                                        "name": "duration",
                                        "required": False,
                                        "default": "5",
                                        "allowed_values": ["5", "10"],
                                    }
                                ],
                                "inputs": [{"name": "first_image", "required": True}],
                            }
                        ]
                    },
                }
            },
        }

        capabilities = parse_kling_capabilities(payload)

        self.assertEqual(capabilities["text_to_video"][0]["model"], "kling-text")
        self.assertEqual(
            capabilities["image_to_video"][0]["arguments"][0]["allowed_values"],
            ["5", "10"],
        )
        self.assertTrue(capabilities["image_to_video"][0]["inputs"][0]["required"])

    def test_capabilities_surface_video_element_schema_without_claiming_cli_support(self):
        payload = {
            "ok": True,
            "body": {
                "tool_list": [
                    {
                        "name": "element_create",
                        "description": "创建视频元素",
                        "constraints": {"duration": "3-60s", "short_side": ">=700"},
                    }
                ]
            },
        }
        capabilities = parse_kling_capabilities(payload)
        self.assertEqual(capabilities["video_elements"][0]["name"], "element_create")
        self.assertFalse(capabilities["video_reference_supported"])
        self.assertIn("升级可灵 CLI", capabilities["video_reference_message"])

    def test_windows_environment_uses_node_entrypoint_instead_of_cmd_wrapper(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            node = root / "node.exe"
            npm = root / "npm.cmd"
            wrapper = root / "kling.cmd"
            entry = root / "node_modules" / "@klingai" / "cli-cn" / "dist" / "cli.js"
            entry.parent.mkdir(parents=True)
            for path in (node, npm, wrapper, entry):
                path.write_text("placeholder", encoding="utf-8")
            environment = KlingCliEnvironment(
                node_path=str(node),
                npm_path=str(npm),
                kling_path=str(wrapper),
                entrypoint_path=str(entry),
                version="0.1.3",
            )

            self.assertEqual(environment.executable, str(node))
            self.assertEqual(environment.argument_prefix, [str(entry)])
            self.assertFalse(environment.use_shell)

    def test_generation_uses_dynamic_parameter_whitelist_and_submits_once(self):
        calls = []
        responses = [
            completed(
                {
                    "ok": True,
                    "body": {
                        "generationId": "generation-1",
                        "creditsConsumed": 12,
                    },
                }
            ),
            completed(
                {
                    "ok": True,
                    "body": {
                        "status": "RUNNING",
                        "works": [],
                    },
                }
            ),
            completed(
                {
                    "ok": True,
                    "body": {
                        "status": "COMPLETED",
                        "works": [{"url": "https://cdn.example/video.mp4"}],
                    },
                }
            ),
        ]

        def runner(executable, arguments, **kwargs):
            calls.append((executable, list(arguments), kwargs))
            return responses.pop(0)

        service = KlingCliService(
            environment=KlingCliEnvironment(
                node_path="node.exe",
                npm_path="npm.cmd",
                kling_path="kling.cmd",
                entrypoint_path="cli.js",
                version="0.1.3",
            ),
            runner=runner,
            sleeper=lambda _: None,
        )
        model = {
            "model": "kling-video-v3",
            "arguments": [
                {"name": "duration", "allowed_values": ["5", "10"]},
                {"name": "enable_audio", "allowed_values": ["true", "false"]},
            ],
        }

        result = service.generate(
            command="image_to_video",
            model=model,
            prompt="让画面动起来",
            images=["G:/assets/first.png"],
            parameters={
                "duration": "10",
                "enable_audio": True,
                "private_field": "must-not-leak",
            },
            timeout_seconds=30,
        )

        submit_arguments = calls[0][1]
        self.assertEqual(sum("image_to_video" in call[1] for call in calls), 1)
        self.assertIn("--duration", submit_arguments)
        self.assertIn("10", submit_arguments)
        self.assertIn("--enable_audio", submit_arguments)
        self.assertIn("true", submit_arguments)
        self.assertNotIn("--private_field", submit_arguments)
        self.assertEqual(submit_arguments[-1], "让画面动起来")
        self.assertEqual(result["generation_id"], "generation-1")
        self.assertEqual(result["credits_consumed"], 12)
        self.assertEqual(result["url"], "https://cdn.example/video.mp4")

    def test_submission_and_query_can_be_persisted_between_processes(self):
        calls = []
        responses = [
            completed(
                {
                    "ok": True,
                    "body": {
                        "generationId": "generation-resume-1",
                        "creditsConsumed": 8,
                    },
                }
            ),
            completed(
                {
                    "ok": True,
                    "body": {
                        "status": "COMPLETED",
                        "works": [{"url": "https://cdn.example/resumed.mp4"}],
                    },
                }
            ),
        ]

        def runner(executable, arguments, **kwargs):
            calls.append(list(arguments))
            return responses.pop(0)

        service = KlingCliService(
            environment=KlingCliEnvironment(
                node_path="node.exe",
                npm_path="npm.cmd",
                kling_path="kling.cmd",
                entrypoint_path="cli.js",
                version="0.1.3",
            ),
            runner=runner,
        )
        model = {
            "model": "kling-video-v3",
            "arguments": [{"name": "duration", "allowed_values": ["5", "10"]}],
        }

        submitted = service.submit(
            command="text_to_video",
            model=model,
            prompt="可恢复任务",
            images=[],
            parameters={"duration": "5"},
        )
        queried = service.query(submitted["generation_id"])

        self.assertEqual(submitted["generation_id"], "generation-resume-1")
        self.assertEqual(submitted["credits_consumed"], 8)
        self.assertEqual(queried["status"], "completed")
        self.assertEqual(queried["url"], "https://cdn.example/resumed.mp4")
        self.assertEqual(calls[1][-2:], ["--quiet", "generation-resume-1"])

    def test_query_prefers_v3_url_without_watermark_fields(self):
        responses = [
            completed(
                {
                    "ok": True,
                    "body": {
                        "generationId": "generation-v3-camel",
                        "status": "COMPLETED",
                        "works": [
                            {
                                "contentType": "video",
                                "urlWithoutWatermark": "https://cdn.example/v3-camel.mp4",
                            }
                        ],
                    },
                }
            ),
            completed(
                {
                    "ok": True,
                    "body": {
                        "generation_id": "generation-v3-snake",
                        "status": "COMPLETED",
                        "works": [
                            {
                                "content_type": "video",
                                "url_without_watermark": "https://cdn.example/v3-snake.mp4",
                            }
                        ],
                    },
                }
            ),
        ]

        service = KlingCliService(
            environment=KlingCliEnvironment(
                node_path="node.exe",
                npm_path="npm.cmd",
                kling_path="kling.cmd",
                entrypoint_path="cli.js",
                version="0.1.3",
            ),
            runner=lambda *args, **kwargs: responses.pop(0),
        )

        camel = service.query("generation-v3-camel")
        snake = service.query("generation-v3-snake")

        self.assertEqual(camel["url"], "https://cdn.example/v3-camel.mp4")
        self.assertEqual(snake["url"], "https://cdn.example/v3-snake.mp4")

    def test_generation_rejects_value_outside_dynamic_schema_before_submission(self):
        service = KlingCliService(
            environment=KlingCliEnvironment(
                node_path="node.exe",
                npm_path="npm.cmd",
                kling_path="kling.cmd",
                entrypoint_path="cli.js",
                version="0.1.3",
            ),
            runner=lambda *args, **kwargs: self.fail("参数校验失败时不应调用 CLI"),
        )

        with self.assertRaisesRegex(KlingCliError, "duration"):
            service.generate(
                command="text_to_video",
                model={
                    "model": "kling-video",
                    "arguments": [
                        {"name": "duration", "allowed_values": ["5", "10"]}
                    ],
                },
                prompt="测试",
                images=[],
                parameters={"duration": "8"},
            )

    def test_skillhub_video_reference_uses_public_url_and_parses_text_output(self):
        calls = []
        responses = [
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="Task ID / 任务 ID: skill-task-1\nQuery / 查询: node kling.mjs video --task_id skill-task-1\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="Task ID / 任务 ID: skill-task-1\nStatus / 状态: succeed\nVideo URL / 视频链接: https://cdn.example/skill.mp4\n",
                stderr="",
            ),
        ]

        def runner(executable, arguments, **kwargs):
            calls.append((executable, list(arguments)))
            return responses.pop(0)

        service = KlingCliService(
            environment=KlingCliEnvironment(
                node_path="node.exe",
                kling_path="kling.cmd",
                entrypoint_path="legacy.js",
                skill_entrypoint_path="C:/skills/kling.mjs",
                version="0.1.3",
            ),
            runner=runner,
            sleeper=lambda _: None,
        )
        result = service.generate(
            command="text_to_video",
            model={"model": "kling-video-v3_0_omni", "arguments": []},
            prompt="参考视频动作",
            images=[],
            videos=["http://64.90.17.178:18080/clip/a/c/c.mp4"],
            parameters={"duration": "5", "video_refer_type": "feature"},
            timeout_seconds=30,
        )

        self.assertEqual(result["generation_id"], "skill-task-1")
        self.assertEqual(result["url"], "https://cdn.example/skill.mp4")
        self.assertEqual(calls[0][0], "node.exe")
        self.assertEqual(calls[0][1][:3], ["C:/skills/kling.mjs", "video", "--no-wait"])
        self.assertIn("kling-v3-omni", calls[0][1])
        self.assertIn("--video_refer_type", calls[0][1])
        self.assertIn("feature", calls[0][1])


if __name__ == "__main__":
    unittest.main()
