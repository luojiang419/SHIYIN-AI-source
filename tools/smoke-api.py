from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def concrete_path(template: str) -> str:
    return re.sub(r"\{[^}]+\}", "smoke", template)


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
        )
        from fastapi.testclient import TestClient
        import main as canvas_main

        client = TestClient(canvas_main.app)
        http_routes = [route for route in canvas_main.app.routes if getattr(route, "methods", None)]
        operations: list[tuple[str, str]] = []
        for route in http_routes:
            for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                operations.append((method, route.path))
        if len(operations) < 150:
            raise AssertionError(f"Expected at least 150 HTTP operations, found {len(operations)}")
        if len(operations) != len(set(operations)):
            raise AssertionError("Duplicate HTTP method/path operation detected")

        protected_checked = 0
        for method, template in operations:
            if not template.startswith("/api/") or template in canvas_main.PUBLIC_HTTP_PATHS:
                continue
            response = client.request(method, concrete_path(template), content=b"{}", follow_redirects=False)
            if response.status_code != 401:
                raise AssertionError(f"Unauthenticated {method} {template} returned {response.status_code}, expected 401")
            protected_checked += 1

        health = client.get("/api/health")
        if health.status_code != 200 or health.json().get("status") != "ok":
            raise AssertionError("Health endpoint failed")
        bootstrap = client.get(
            "/api/auth/bootstrap?token=api-smoke-desktop-token",
            follow_redirects=False,
        )
        if bootstrap.status_code != 303 or not bootstrap.cookies:
            raise AssertionError("Desktop bootstrap did not establish a session")
        client.cookies.update(bootstrap.cookies)

        safe_gets = (
            "/",
            "/devices",
            "/api/app-info",
            "/api/runtime/info",
            "/api/config",
            "/api/providers",
            "/api/projects",
            "/api/canvases",
            "/api/asset-library",
            "/api/ecommerce/capabilities",
            "/api/history",
            "/api/preferences",
            "/api/config/token",
        )
        for path in safe_gets:
            response = client.get(path, follow_redirects=False)
            if response.status_code >= 400:
                raise AssertionError(f"Authenticated GET {path} returned {response.status_code}: {response.text[:200]}")

        custom_provider_id = "smoke-custom"
        custom_model = "future-image-v9"
        custom_key = "smoke-custom-secret"
        saved = client.put(
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
        if saved.status_code != 200:
            raise AssertionError(f"Custom provider save returned {saved.status_code}: {saved.text[:200]}")
        providers_after_save = client.get("/api/providers").json().get("providers") or []
        config_after_save = client.get("/api/config").json().get("api_providers") or []
        capabilities_after_save = client.get("/api/ecommerce/capabilities").json()
        if not any(item.get("id") == custom_provider_id for item in providers_after_save):
            raise AssertionError("Custom provider did not persist after save")
        if not any(item.get("id") == custom_provider_id for item in config_after_save):
            raise AssertionError("Custom provider did not reach the shared page configuration")
        if not any(
            item.get("provider_id") == custom_provider_id and item.get("model") == custom_model
            for item in capabilities_after_save.get("models") or []
        ):
            raise AssertionError("Custom image model did not reach Free Creation capabilities")
        if custom_key in saved.text or custom_key in json.dumps(providers_after_save):
            raise AssertionError("Provider API exposed a complete credential")

        page_count = 0
        for page in canvas_main.APP_PATHS.web_root.rglob("*.html"):
            relative = page.relative_to(canvas_main.APP_PATHS.web_root).as_posix()
            response = client.get(f"/static/{relative}")
            if response.status_code != 200:
                raise AssertionError(f"Static page {relative} returned {response.status_code}")
            page_count += 1

        token_response = client.get("/api/config/token")
        token_text = token_response.text
        if "api-smoke-desktop-token" in token_text or "access_token" in token_response.json():
            raise AssertionError("Token endpoint exposed a complete credential")
        update_check = client.get("/api/check-update")
        if not update_check.json().get("disabled"):
            raise AssertionError("Desktop runtime did not disable the source updater")
        update_attempt = client.post("/api/update-from-github", json={})
        if update_attempt.status_code != 409:
            raise AssertionError(f"Desktop source update returned {update_attempt.status_code}, expected 409")

        result = {
            "http_operations": len(operations),
            "protected_operations_checked": protected_checked,
            "authenticated_gets": len(safe_gets),
            "static_pages": page_count,
            "openapi_paths": len(canvas_main.app.openapi().get("paths", {})),
            "desktop_source_updater_disabled": True,
            "custom_provider_shared_across_pages": True,
            "status": "ok",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
