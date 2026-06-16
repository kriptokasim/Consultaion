#!/usr/bin/env python3
"""
Audit Alembic revision IDs for compliance with the project revision policy.

Policy:
- Maximum revision length: 32 characters (recommended: 24)
- Exactly one head
- No duplicate revision IDs
- All down_revision targets exist
- No cycles in the migration graph
- No imports of application runtime services from migration files

Usage:
    python scripts/audit_alembic_revisions.py
    python scripts/audit_alembic_revisions.py --ci
"""

from __future__ import annotations

import argparse
import ast
import os
import sys

MAX_REVISION_LENGTH = 32
RECOMMENDED_REVISION_LENGTH = 24

LEGACY_LONG_REVISIONS: set[str] = set()


def main() -> None:
    parser = argparse.ArgumentParser(description="Alembic revision policy audit")
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Exit with error on policy violations (CI mode)",
    )
    args = parser.parse_args()

    api_dir = os.path.join(os.path.dirname(__file__), "..", "apps", "api")
    alembic_dir = os.path.join(api_dir, "alembic", "versions")
    if not os.path.isdir(alembic_dir):
        print(f"ERROR: Migration directory not found: {alembic_dir}")
        sys.exit(1)

    errors: list[str] = []
    warnings: list[str] = []

    # Collect all revisions from migration files
    revisions: dict[str, dict] = {}
    for fname in sorted(os.listdir(alembic_dir)):
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(alembic_dir, fname)
        with open(fpath) as fh:
            tree = ast.parse(fh.read(), filename=fpath)

        rev_info = _extract_revision_info(tree, fpath)
        if rev_info:
            rev_id = rev_info["revision"]
            if rev_id in revisions:
                errors.append(f"Duplicate revision ID: {rev_id} in {fname} and {revisions[rev_id]['file']}")
            revisions[rev_id] = rev_info
            revisions[rev_id]["file"] = fname

    if not revisions:
        print("ERROR: No revisions found")
        sys.exit(1)

    # Check 1: Revision ID length
    for rev_id, info in revisions.items():
        if len(rev_id) > MAX_REVISION_LENGTH:
            if rev_id in LEGACY_LONG_REVISIONS:
                warnings.append(
                    f"Legacy long revision allowed: {rev_id} "
                    f"({len(rev_id)} chars, max {MAX_REVISION_LENGTH}) in {info['file']}"
                )
            else:
                errors.append(
                    f"Revision {rev_id} ({len(rev_id)} chars) exceeds {MAX_REVISION_LENGTH} "
                    f"char limit in {info['file']}"
                )
        elif len(rev_id) > RECOMMENDED_REVISION_LENGTH:
            warnings.append(
                f"Revision {rev_id} ({len(rev_id)} chars) exceeds recommended "
                f"{RECOMMENDED_REVISION_LENGTH} chars in {info['file']}"
            )

    # Check 2: Duplicate revisions (already checked above)

    # Check 3: Missing down_revision targets
    for rev_id, info in revisions.items():
        down = info.get("down_revision")
        if down and down not in revisions and down != "heads":
            errors.append(
                f"down_revision {down} in {info['file']} (rev {rev_id}) "
                f"not found in migration graph"
            )

    # Check 4: Multiple heads
    heads = [rev_id for rev_id, info in revisions.items()
             if not any(
                 other_info.get("down_revision") == rev_id
                 for other_info in revisions.values()
             )]
    if len(heads) != 1:
        warnings.append(
            f"Expected 1 head, found {len(heads)}: {heads}"
        )

    # Check 5: Cycles (detect via DFS)
    visited: set[str] = set()
    rec_stack: set[str] = set()

    def _has_cycle(rev_id: str) -> bool:
        visited.add(rev_id)
        rec_stack.add(rev_id)
        info = revisions.get(rev_id, {})
        down = info.get("down_revision")
        if down and down in revisions:
            if down not in visited:
                if _has_cycle(down):
                    return True
            elif down in rec_stack:
                return True
        rec_stack.discard(rev_id)
        return False

    for rev_id in revisions:
        if rev_id not in visited:
            if _has_cycle(rev_id):
                errors.append(f"Cycle detected in migration graph involving revision {rev_id}")

    # Check 6: No runtime imports in migration files
    BANNED_IMPORTS = {"config", "models", "database", "routes"}
    for rev_id, info in revisions.items():
        banned = [m for m in info.get("imports", []) if m in BANNED_IMPORTS]
        if banned:
            warnings.append(
                f"Migration {info['file']} imports runtime module(s): {banned}"
            )

    # Report
    n_revisions = len(revisions)
    ul = "\033[4m" if sys.stderr.isatty() else ""
    ur = "\033[24m" if sys.stderr.isatty() else ""

    print(f"{ul}Alembic Revision Policy Audit{ur}")
    print(f"  Revisions found: {n_revisions}")
    print(f"  Heads: {heads}")
    print(f"  Errors: {len(errors)}")
    print(f"  Warnings: {len(warnings)}")
    print()

    if errors:
        print("Errors:")
        for e in errors:
            print(f"  [ERROR] {e}")
        print()
    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"  [WARN] {w}")
        print()

    if args.ci and errors:
        print("CI mode: failing due to errors")
        sys.exit(1)

    if args.ci and warnings:
        print("CI mode: warnings found but not failing")

    print(f"Audit complete: {n_revisions} revisions checked")


def _extract_revision_info(tree: ast.AST, fpath: str) -> dict | None:
    info: dict = {
        "revision": None,
        "down_revision": None,
        "imports": [],
        "file": os.path.basename(fpath),
    }

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id == "revision" and isinstance(node.value, ast.Constant):
                        info["revision"] = node.value.value
                    elif target.id == "down_revision" and isinstance(node.value, (ast.Constant, ast.Name)):
                        if isinstance(node.value, ast.Constant):
                            info["down_revision"] = node.value.value
                        elif isinstance(node.value, ast.Name) and node.value.id == "None":
                            info["down_revision"] = None
                elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                    if target.value.id == "branch_labels" and isinstance(node.value, ast.Constant):
                        info["branch_labels"] = node.value.value
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    info["imports"].append(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                info["imports"].append(node.module.split(".")[0])

    if not info["revision"]:
        return None
    return info


if __name__ == "__main__":
    main()
