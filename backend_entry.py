"""PyInstaller/Tauri sidecar entry point."""

import os
import sys

ENTRY_DIR = os.path.dirname(os.path.abspath(__file__))
if ENTRY_DIR not in sys.path:
    sys.path.insert(0, ENTRY_DIR)

def main():
    # 冻结后的 sys.executable 是 sidecar，不是 Python；仅分派已打包的固定技能。
    if len(sys.argv) == 4 and sys.argv[1] == "--linkfox-video-skill":
        import runpy
        import contextlib
        import io
        import json
        from canvas_core.linkfox_video import _skill_path
        from pathlib import Path
        kind = sys.argv[2]
        if kind not in {"single", "multi"}:
            raise SystemExit("Invalid LinkFox skill kind")
        script = _skill_path(Path(ENTRY_DIR), kind)
        sys.argv = [str(script), sys.argv[3]]
        result_file = os.environ.get("LINKFOX_SKILL_RESULT_FILE")
        if result_file:
            # windowed PyInstaller 的 stdout/stderr 可能是 None，用文件传回脚本结果。
            stdout, stderr = io.StringIO(), io.StringIO()
            try:
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    runpy.run_path(str(script), run_name="__main__")
            finally:
                Path(result_file).write_text(json.dumps({"stdout": stdout.getvalue(), "stderr": stderr.getvalue()}), encoding="utf-8")
        else:
            runpy.run_path(str(script), run_name="__main__")
        return
    from canvas_core.runtime import run_uvicorn
    from main import app
    run_uvicorn(app)


if __name__ == "__main__":
    main()
