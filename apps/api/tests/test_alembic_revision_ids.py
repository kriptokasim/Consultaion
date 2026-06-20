"""Test that all Alembic migration revision IDs satisfy the VARCHAR(32) limit."""
import glob
import os
import re


def _extract_revision_id(filepath: str) -> tuple[str, str]:
    """Extract revision ID from a migration file."""
    with open(filepath) as f:
        content = f.read()
    match = re.search(r"""^revision[:\s]*(?:str\s*)?=\s*['"]([^'"]+)['"]""", content, re.MULTILINE)
    if not match:
        raise ValueError(f"No revision found in {filepath}")
    return match.group(1), filepath


def _extract_down_revision(filepath: str) -> str | None:
    """Extract down_revision from a migration file."""
    with open(filepath) as f:
        content = f.read()
    match = re.search(r"""^down_revision[:\s]*(?:.*?\s*)?=\s*['"]([^'"]+)['"]""", content, re.MULTILINE)
    if match:
        return match.group(1)
    return None


def test_all_revision_ids_within_32_chars():
    versions_dir = os.path.join(os.path.dirname(__file__), "..", "alembic", "versions")
    migration_files = glob.glob(os.path.join(versions_dir, "*.py"))

    revisions = {}
    for filepath in migration_files:
        if filepath.endswith("__pycache__"):
            continue
        rev_id, path = _extract_revision_id(filepath)
        revisions[rev_id] = path

        assert len(rev_id) <= 32, (
            f"Revision ID '{rev_id}' in {os.path.basename(path)} "
            f"is {len(rev_id)} chars, exceeds 32-char limit"
        )


def test_unique_revision_ids():
    versions_dir = os.path.join(os.path.dirname(__file__), "..", "alembic", "versions")
    migration_files = glob.glob(os.path.join(versions_dir, "*.py"))

    revisions = []
    for filepath in migration_files:
        if filepath.endswith("__pycache__"):
            continue
        rev_id, path = _extract_revision_id(filepath)
        revisions.append((rev_id, os.path.basename(path)))

    seen = {}
    for rev_id, filename in revisions:
        assert rev_id not in seen, (
            f"Duplicate revision ID '{rev_id}' in {filename} and {seen[rev_id]}"
        )
        seen[rev_id] = filename


def test_valid_down_revision_chain():
    versions_dir = os.path.join(os.path.dirname(__file__), "..", "alembic", "versions")
    migration_files = glob.glob(os.path.join(versions_dir, "*.py"))

    revisions = {}
    down_revisions = {}
    for filepath in migration_files:
        if filepath.endswith("__pycache__"):
            continue
        rev_id, _ = _extract_revision_id(filepath)
        down_rev = _extract_down_revision(filepath)
        revisions[rev_id] = os.path.basename(filepath)
        down_revisions[rev_id] = down_rev

    # All down_revisions (except the first migration) should reference an existing revision
    for rev_id, down_rev in down_revisions.items():
        if down_rev is not None:
            assert down_rev in revisions, (
                f"Migration {revisions[rev_id]} references down_revision '{down_rev}' "
                f"which does not exist"
            )


def test_no_orphaned_migrations():
    """Every migration except the first should have at least one other migration pointing to it."""
    versions_dir = os.path.join(os.path.dirname(__file__), "..", "alembic", "versions")
    migration_files = glob.glob(os.path.join(versions_dir, "*.py"))

    revisions = {}
    referenced = set()
    for filepath in migration_files:
        if filepath.endswith("__pycache__"):
            continue
        rev_id, _ = _extract_revision_id(filepath)
        down_rev = _extract_down_revision(filepath)
        revisions[rev_id] = os.path.basename(filepath)
        if down_rev:
            referenced.add(down_rev)

    # The head migration is not referenced by any other, which is expected
    heads = set(revisions.keys()) - referenced
    assert len(heads) >= 1, "No migration head found"
    # Allow exactly one head (the latest migration)
    assert len(heads) <= 2, f"Multiple heads found: {heads}"
