"""Tests for the async blocking audit script."""

import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "audit_async_blocking.py"


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

    def test_script_outputs_findings_format(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "apps/api"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 1:
            assert "Total:" in result.stdout or "L" in result.stdout

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
