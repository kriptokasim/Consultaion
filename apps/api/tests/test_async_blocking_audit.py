"""Tests for the async blocking audit script."""

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parent.parent.parent.parent / "scripts" / "audit_async_blocking.py"


@pytest.mark.skipif(not SCRIPT_PATH.exists(), reason="Audit script not found")
class TestAsyncBlockingAudit:
    def test_script_runs_without_error(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "apps/api"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode in (0, 1)

    def test_detects_blocking_call_in_async(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_async.py"
            test_file.write_text("import time\n\nasync def bad():\n    time.sleep(1)\n")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), tmpdir],
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert "time.sleep" in result.stdout
            assert result.returncode == 1

    def test_ignores_blocking_call_in_sync(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_sync.py"
            test_file.write_text("import time\n\ndef good():\n    time.sleep(1)\n")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), tmpdir],
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert "time.sleep" not in result.stdout
            assert result.returncode == 0

    def test_respects_noasync_comment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_justified.py"
            test_file.write_text("import time\n\nasync def justified():\n    time.sleep(1)  # noasync: justified\n")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), tmpdir],
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert "time.sleep" not in result.stdout
            assert result.returncode == 0

    def test_script_excludes_alembic(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "apps/api"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert "alembic/" not in result.stdout

    def test_script_handles_missing_directory(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "nonexistent_dir"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 1
