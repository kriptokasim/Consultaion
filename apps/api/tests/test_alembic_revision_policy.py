"""Tests for Alembic revision policy compliance."""

import os
import subprocess
import sys


def test_alembic_revision_policy():
    """Run the audit script and verify it exits successfully."""
    script = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "scripts", "audit_alembic_revisions.py"
    )
    script = os.path.abspath(script)
    if not os.path.exists(script):
        import pytest
        pytest.skip(f"Audit script not found at {script}")

    result = subprocess.run(
        [sys.executable, script, "--ci"],
        capture_output=True,
        text=True,
        cwd=os.path.join(os.path.dirname(__file__), "..", "..", ".."),
    )

    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    assert result.returncode == 0, (
        f"Alembic revision policy audit failed with return code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


def test_single_migration_head():
    """Verify exactly one migration head exists."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    api_dir = os.path.join(os.path.dirname(__file__), "..")
    alembic_cfg = Config(os.path.join(api_dir, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(api_dir, "alembic"))
    script = ScriptDirectory.from_config(alembic_cfg)
    heads = script.get_heads()

    assert len(heads) == 1, (
        f"Expected exactly one migration head, found {len(heads)}: {heads}"
    )


def test_all_down_revisions_resolve():
    """Verify every down_revision points to an existing revision."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    api_dir = os.path.join(os.path.dirname(__file__), "..")
    alembic_cfg = Config(os.path.join(api_dir, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(api_dir, "alembic"))
    script = ScriptDirectory.from_config(alembic_cfg)

    revisions = {r.revision: r for r in script.walk_revisions() if r.revision and r.revision != "heads"}
    for rev_id, rev in revisions.items():
        if rev.down_revision:
            assert rev.down_revision in revisions or rev.down_revision is None, (
                f"down_revision {rev.down_revision} of {rev_id} not found"
            )
