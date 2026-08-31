import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class DesktopBootstrapTests(unittest.TestCase):
    def test_bootstrap_is_loopback_only_and_idempotent_for_desktop_navigation(self):
        code = r'''
from fastapi.testclient import TestClient
import main

url = "/api/auth/bootstrap"
with TestClient(main.app, client=("127.0.0.1", 50000)) as client:
    first = client.get(url, follow_redirects=False)
    assert first.status_code == 303, first.text
    assert first.headers["location"] == "/", first.headers
    assert first.headers["cache-control"] == "no-store", first.headers
    assert first.headers["referrer-policy"] == "no-referrer", first.headers

    cookie_retry = client.get(url, follow_redirects=False)
    assert cookie_retry.status_code == 303, cookie_retry.text

for retry_index in range(64):
    with TestClient(main.app, client=("127.0.0.1", 50001 + retry_index)) as retry_client:
        no_cookie_retry = retry_client.get(url, follow_redirects=False)
        assert no_cookie_retry.status_code == 303, no_cookie_retry.text

with TestClient(main.app, client=("127.0.0.1", 50080)) as exhausted_client:
    desktop_retry = exhausted_client.get(url, follow_redirects=False)
    assert desktop_retry.status_code == 303, desktop_retry.text

with TestClient(main.app, client=("127.0.0.1", 50002)) as wrong_client:
    wrong = wrong_client.get("/api/auth/bootstrap?token=wrong", follow_redirects=False)
    assert wrong.status_code == 303, wrong.text
    assert wrong.headers["cache-control"] == "no-store", wrong.headers
    assert wrong.headers["referrer-policy"] == "no-referrer", wrong.headers

with TestClient(main.app, client=("192.168.1.8", 50003)) as lan_client:
    denied = lan_client.get(url, follow_redirects=False)
    assert denied.status_code == 403, denied.text
    assert denied.headers["cache-control"] == "no-store", denied.headers
    assert denied.headers["referrer-policy"] == "no-referrer", denied.headers
'''
        with tempfile.TemporaryDirectory() as work:
            environment = dict(os.environ)
            environment.update(
                {
                    "CANVAS_DATA_DIR": str(Path(work) / "data"),
                    "CANVAS_DESKTOP_TOKEN": "desktop-test-token",
                    "CANVAS_RUNTIME_MODE": "desktop",
                    "CANVAS_PORT": "3000",
                }
            )
            completed = subprocess.run(
                [sys.executable, "-c", code],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
