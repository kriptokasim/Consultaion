#!/usr/bin/env python3
"""AST-based audit for synchronous I/O blocking in async functions.

Scans Python source files for calls that may block the event loop when
used inside ``async def`` functions. Supports allowlist annotations
via ``# noasync: <reason>`` comments.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import NamedTuple

BLOCKED_CALLS = {
    "requests.get",
    "requests.post",
    "requests.put",
    "requests.delete",
    "requests.patch",
    "requests.head",
    "requests.request",
    "requests.Session.get",
    "requests.Session.post",
    "requests.Session.put",
    "requests.Session.delete",
    "requests.Session.patch",
    "requests.Session.head",
    "requests.Session.request",
    "time.sleep",
    "os.system",
    "subprocess.run",
    "subprocess.check_output",
    "subprocess.check_call",
    "subprocess.call",
    "pathlib.Path.read_text",
    "pathlib.Path.write_text",
    "pathlib.Path.read_bytes",
    "pathlib.Path.write_bytes",
    "open",
    "json.load",
    "json.loads",
}

SYNC_DB_CALLS = {
    "session.exec",
    "session.add",
    "session.delete",
    "session.merge",
    "session.commit",
    "session.flush",
    "session.refresh",
    "session.close",
    "session.begin",
    "session_scope",
    "get_session",
}

PROVIDER_SDK_SYNC = {
    "anthropic.Anthropic",
    "openai.OpenAI",
    "together.Together",
    "groq.Groq",
    "cohere.Client",
}

class Finding(NamedTuple):
    file: str
    line: int
    col: int
    name: str
    category: str
    reason: str


def _node_name(node: ast.expr) -> str:
    """Extract dotted name from an AST node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _node_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _is_async_context(node: ast.AST) -> bool:
    """Check if a node is an async function def."""
    return isinstance(node, (ast.AsyncFunctionDef, ast.AsyncFor, ast.AsyncWith))


def _has_noasync_comment(node: ast.AST, source_lines: list[str]) -> bool:
    """Check for ``# noasync: <reason>`` on the same line."""
    if hasattr(node, "lineno") and node.lineno <= len(source_lines):
        line = source_lines[node.lineno - 1]
        return "# noasync" in line
    return False


def _find_enclosing_async(tree: ast.Module) -> dict[int, bool]:
    """Map each line number to whether it's inside an async function."""
    in_async: dict[int, bool] = {}
    async_stack: list[bool] = []

    def _visit(node: ast.AST, in_async_ctx: bool = False) -> None:
        is_async = _is_async_context(node)
        async_stack.append(is_async)
        current_in_async = in_async_ctx or is_async

        if hasattr(node, "lineno"):
            in_async[node.lineno] = current_in_async

        for child in ast.iter_child_nodes(node):
            _visit(child, current_in_async)

        async_stack.pop()

    _visit(tree)
    return in_async


def audit_file(filepath: Path) -> list[Finding]:
    """Audit a single Python file for blocking calls in async context."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError) as exc:
        print(f"  SKIP {filepath}: {exc}", file=sys.stderr)
        return []

    source_lines = source.splitlines()
    findings: list[Finding] = []

    async_context = _find_enclosing_async(tree)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _has_noasync_comment(node, source_lines):
            continue

        line = getattr(node, "lineno", 0)
        if not async_context.get(line, False):
            continue

        name = _node_name(node.func)

        if name in BLOCKED_CALLS:
            findings.append(Finding(
                file=str(filepath), line=line, col=node.col_offset,
                name=name, category="blocking_io",
                reason="sync I/O call inside async function"
            ))
        elif name in SYNC_DB_CALLS:
            findings.append(Finding(
                file=str(filepath), line=line, col=node.col_offset,
                name=name, category="sync_db",
                reason="synchronous DB call inside async function"
            ))
        elif name in PROVIDER_SDK_SYNC:
            findings.append(Finding(
                file=str(filepath), line=line, col=node.col_offset,
                name=name, category="sync_provider",
                reason="synchronous provider SDK inside async function"
            ))

    return findings


def audit_directory(directory: Path, exclude_dirs: list[str] | None = None) -> list[Finding]:
    """Audit all Python files in a directory tree."""
    exclude = set(exclude_dirs or ["__pycache__", ".git", "node_modules", ".venv", "alembic"])
    findings: list[Finding] = []

    for pyfile in sorted(directory.rglob("*.py")):
        if any(part in exclude for part in pyfile.parts):
            continue
        findings.extend(audit_file(pyfile))

    return findings


def main() -> int:
    """Run the async blocking audit."""
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("apps/api")

    if not target.exists():
        print(f"Target not found: {target}", file=sys.stderr)
        return 1

    findings = audit_directory(target)

    if not findings:
        print("No async blocking issues found.")
        return 0

    current_file = ""
    for f in findings:
        if f.file != current_file:
            current_file = f.file
            print(f"\n{current_file}")
        print(f"  L{f.line}:{f.col}  {f.name}  ({f.category})  {f.reason}")

    print(f"\nTotal: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
