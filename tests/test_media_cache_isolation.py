import subprocess
from pathlib import Path


def test_service_worker_account_isolation_and_logout():
    subprocess.run(['node','tests/support/media_cache_isolation.cjs'],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True,text=True)
