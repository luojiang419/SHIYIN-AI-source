from __future__ import annotations

import json
import io
import os
import sys
import tempfile
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def require_status(response, expected: int, label: str) -> None:
    if response.status_code != expected:
        raise AssertionError(
            f"{label} returned {response.status_code}, expected {expected}: {response.text[:300]}"
        )


def main() -> int:
    smoke_temp_root = PROJECT_ROOT / ".build"
    smoke_temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="canvas-api-smoke-", dir=smoke_temp_root) as data_dir:
        os.environ.update(
            CANVAS_DATA_DIR=data_dir,
            CANVAS_DESKTOP_TOKEN="api-smoke-desktop-token",
            CANVAS_HOST="127.0.0.1",
            CANVAS_PORT="3999",
            CANVAS_RUNTIME_MODE="desktop",
            CANVAS_DWPOSE_AUTO_DOWNLOAD="0",
        )
        from fastapi.testclient import TestClient
        import main as canvas_main

        anonymous = TestClient(canvas_main.app, client=("192.168.1.80", 50000))
        local_admin = TestClient(canvas_main.app, client=("127.0.0.1", 50001))
        remote_admin = TestClient(canvas_main.app, client=("192.168.1.81", 50002))
        user_one = TestClient(canvas_main.app, client=("192.168.1.82", 50003))
        user_two = TestClient(canvas_main.app, client=("192.168.1.83", 50004))

        operations = [
            (method, route.path)
            for route in canvas_main.app.routes
            if getattr(route, "methods", None)
            for method in sorted(route.methods - {"HEAD", "OPTIONS"})
        ]
        if len(operations) < 150:
            raise AssertionError(f"Expected at least 150 HTTP operations, found {len(operations)}")
        if len(operations) != len(set(operations)):
            raise AssertionError("Duplicate HTTP method/path operation detected")

        require_status(anonymous.get("/api/health"), 200, "Health endpoint")
        root = anonymous.get("/", follow_redirects=False)
        require_status(root, 303, "Anonymous root")
        if root.headers.get("location") != "/login":
            raise AssertionError("Anonymous browser was not redirected to /login")
        require_status(anonymous.get("/api/account/me"), 401, "Anonymous API")
        require_status(anonymous.get("/static/index.html"), 401, "Anonymous static page")

        require_status(
            remote_admin.post("/api/account/login", json={"account": "jiang", "password": "jiang"}),
            403,
            "Remote admin login",
        )
        require_status(
            local_admin.post("/api/account/login", json={"account": "jiang", "password": "jiang"}),
            200,
            "Local admin login",
        )
        admin_me = local_admin.get("/api/account/me").json().get("account") or {}
        if not admin_me.get("is_admin"):
            raise AssertionError(f"Local admin identity is incorrect: {admin_me}")

        custom_provider_id = "smoke-custom"
        custom_model = "future-image-v9"
        custom_key = "smoke-custom-secret"
        saved = local_admin.put(
            "/api/providers",
            json=[{
                "id": custom_provider_id,
                "name": "Smoke Custom",
                "base_url": "https://api.smoke.invalid",
                "protocol": "openai",
                "enabled": True,
                "image_models": [custom_model],
                "chat_models": [],
                "video_models": [],
                "api_key": custom_key,
            }],
        )
        require_status(saved, 200, "Admin provider save")
        if custom_key in saved.text:
            raise AssertionError("Provider API exposed a complete credential")

        require_status(
            user_one.post(
                "/api/account/register",
                json={"account": "测试User001", "password": "任意 Password !@#"},
            ),
            201,
            "First account registration",
        )
        require_status(
            user_two.post("/api/account/register", json={"account": "同事B002", "password": "B-密码_2"}),
            201,
            "Second account registration",
        )
        require_status(
            anonymous.post("/api/account/register", json={"account": "JIANG", "password": "任意密码"}),
            400,
            "Reserved administrator account registration",
        )
        user_one_identity = user_one.get("/api/account/me").json().get("account") or {}
        user_two_identity = user_two.get("/api/account/me").json().get("account") or {}

        dwpose_status = local_admin.get("/api/admin/dwpose/status")
        require_status(dwpose_status, 200, "Local admin DWPose status")
        require_status(user_one.get("/api/admin/dwpose/status"), 403, "Regular user DWPose status")
        dwpose_input = io.BytesIO()
        Image.new("RGB", (32, 48), "white").save(dwpose_input, "PNG")
        require_status(
            user_one.post(
                "/api/dwpose/detect",
                files={"file": ("person.png", dwpose_input.getvalue(), "image/png")},
            ),
            503,
            "Regular user DWPose model pending",
        )

        for client, label in ((user_one, "user one"), (user_two, "user two")):
            me = client.get("/api/account/me")
            require_status(me, 200, f"{label} identity")
            if (me.json().get("account") or {}).get("is_admin"):
                raise AssertionError(f"{label} unexpectedly received administrator privileges")
            for path in (
                "/api/config",
                "/api/providers",
                "/api/config/token",
                "/api/app-settings",
                "/api/runtime/info",
                "/static/api-settings.html",
                "/static/app-settings.html",
                "/static/admin.html",
                "/admin",
            ):
                require_status(client.get(path), 403, f"{label} protected config {path}")

        runtime_catalog = user_one.get("/api/runtime/config")
        require_status(runtime_catalog, 200, "User runtime model catalog")
        runtime_text = runtime_catalog.text
        if custom_provider_id not in runtime_text or custom_model not in runtime_text:
            raise AssertionError("Saved administrator model did not reach the user runtime catalog")
        for secret_field in ("base_url", "key_preview", "key_env", "has_key"):
            if secret_field in runtime_text:
                raise AssertionError(f"Runtime catalog exposed API configuration field: {secret_field}")

        allowed_preferences = user_one.put(
            "/api/preferences",
            json={"values": {"theme": "dark", "language": "zh-CN"}},
        )
        require_status(allowed_preferences, 200, "User theme/language update")
        denied_preferences = user_one.put(
            "/api/preferences",
            json={"values": {"ui_scale": "compact"}},
        )
        require_status(denied_preferences, 403, "User restricted preference update")
        require_status(
            user_two.put("/api/preferences", json={"values": {"theme": "light", "language": "en"}}),
            200,
            "Second user preferences",
        )
        if user_one.get("/api/preferences").json().get("values", {}).get("theme") != "dark":
            raise AssertionError("First user's preferences were mixed with another account")
        if user_two.get("/api/preferences").json().get("values", {}).get("theme") != "light":
            raise AssertionError("Second user's preferences were mixed with another account")

        created = user_one.post("/api/projects", json={"name": "001-only"})
        require_status(created, 200, "First user project creation")
        project_id = (created.json().get("project") or {}).get("id")
        user_two_projects = user_two.get("/api/projects")
        require_status(user_two_projects, 200, "Second user project list")
        if any(item.get("id") == project_id for item in user_two_projects.json().get("projects") or []):
            raise AssertionError("Project data leaked between accounts")

        first_layout = canvas_main.ACCOUNT_STORAGE.layout_for(user_one_identity["account_id"])
        generated_file = first_layout.media_generated / "admin-preview.txt"
        generated_file.write_text("account-one-resource", encoding="utf-8")
        admin_accounts = local_admin.get("/api/admin/accounts")
        require_status(admin_accounts, 200, "Admin account list")
        require_status(local_admin.get("/admin"), 200, "Local administrator page")
        listed_accounts = admin_accounts.json().get("accounts") or []
        first_admin_record = next(
            (item for item in listed_accounts if item.get("id") == user_one_identity["account_id"]),
            {},
        )
        if first_admin_record.get("password") != "任意 Password !@#":
            raise AssertionError("Administrator could not view the user's original password")
        admin_resources = local_admin.get(
            f"/api/admin/accounts/{user_one_identity['account_id']}/resources"
        )
        require_status(admin_resources, 200, "Admin user resource list")
        resource_item = next(
            (item for item in admin_resources.json().get("files") or [] if item.get("name") == generated_file.name),
            {},
        )
        if not resource_item:
            raise AssertionError("Administrator resource page did not index the user's generated file")
        require_status(local_admin.get(resource_item["url"]), 200, "Admin resource preview")
        require_status(
            user_two.get(f"/api/admin/accounts/{user_one_identity['account_id']}/resources"),
            403,
            "Regular user admin resource access",
        )

        with user_one.websocket_connect("/ws/events?client_id=user-one") as socket:
            first_messages = [socket.receive_json(), socket.receive_json()]
            ready = next((item for item in first_messages if item.get("type") == "connection.ready"), {})
            if (ready.get("account") or {}).get("account") != "测试User001":
                raise AssertionError(f"Account WebSocket handshake is incorrect: {first_messages}")
            socket.send_text("ping")
            if socket.receive_json().get("type") != "pong":
                raise AssertionError("Account WebSocket ping failed")

        password_reset = local_admin.put(
            f"/api/admin/accounts/{user_one_identity['account_id']}",
            json={"account": "新User001", "password": "重置 密码-9090!", "disabled": False},
        )
        require_status(password_reset, 200, "Admin account/password update")
        if (password_reset.json().get("account") or {}).get("password") != "重置 密码-9090!":
            raise AssertionError("Administrator password reset did not return the updated original password")
        require_status(user_one.get("/api/account/me"), 401, "Reset user session invalidation")
        require_status(
            user_one.post(
                "/api/account/login",
                json={"account": "新user001", "password": "重置 密码-9090!"},
            ),
            200,
            "Reset user login",
        )

        account_root = Path(data_dir) / "accounts"
        account_dirs = [path for path in account_root.iterdir() if path.is_dir()]
        if len(account_dirs) != 2 or not all((path / "database" / "canvas.db").is_file() for path in account_dirs):
            raise AssertionError(f"Dedicated account data directories are incomplete: {account_dirs}")

        page_count = 0
        for page in canvas_main.APP_PATHS.web_root.rglob("*.html"):
            relative = page.relative_to(canvas_main.APP_PATHS.web_root).as_posix()
            response = local_admin.get(f"/static/{relative}")
            require_status(response, 200, f"Admin static page {relative}")
            page_count += 1

        result = {
            "http_operations": len(operations),
            "account_authentication": True,
            "local_admin_only": True,
            "api_configuration_hidden_from_users": True,
            "account_data_isolation": True,
            "account_websocket_isolation": True,
            "administrator_account_management": True,
            "administrator_resource_browser": True,
            "dwpose_access_control": True,
            "static_pages": page_count,
            "openapi_paths": len(canvas_main.app.openapi().get("paths", {})),
            "status": "ok",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
