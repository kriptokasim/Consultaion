"""Read-only evidence tools for claim verification.

These are the Phase-1 tool surface from the evidence-layer plan. They are
deliberately the real implementation rather than eval scaffolding: the verifier
that ships later should start here, already measured.

Everything is read-only and commit-pinned. Nothing mutates the working tree,
nothing executes repository code, nothing writes. A claim about a repository at
a particular commit must be checkable without trusting that repository, which is
the property that lets this run against a stranger's code later.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Evidence:
    """What a tool found. `found` False means the tool ran and saw nothing."""

    found: bool
    excerpt: str = ""
    source: str = ""
    tool: str = ""
    error: str | None = None
    raw_lines: list[str] = field(default_factory=list)


class RepoTools:
    """Read-only access to one repository, optionally pinned to a commit.

    When `commit` is set, files are read through `git show <commit>:<path>` rather
    than from disk. Cases about historical state (a bug that has since been fixed)
    then stay reproducible instead of silently re-scoring against HEAD.
    """

    def __init__(self, repo_root: str | Path, commit: str | None = None, timeout: int = 30):
        self.root = Path(repo_root).resolve()
        self.commit = commit
        self.timeout = timeout

    # --- internals ---------------------------------------------------------

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )

    def _read(self, path: str) -> tuple[str | None, str | None]:
        """Return (content, error)."""
        if self.commit:
            proc = self._git("show", f"{self.commit}:{path}")
            if proc.returncode != 0:
                return None, proc.stderr.strip() or f"not found at {self.commit}"
            return proc.stdout, None
        target = self.root / path
        if not target.is_file():
            return None, "file not found"
        try:
            return target.read_text(errors="replace"), None
        except OSError as exc:
            return None, str(exc)

    def _ref(self, path: str) -> str:
        return f"{path}@{self.commit[:7]}" if self.commit else path

    # --- tools -------------------------------------------------------------

    def read_file(self, path: str, pattern: str | None = None) -> Evidence:
        """Read a file; optionally return only the lines matching `pattern`."""
        content, error = self._read(path)
        if content is None:
            return Evidence(found=False, tool="read_file", source=self._ref(path), error=error)

        if pattern is None:
            return Evidence(
                found=True, excerpt=content[:2000], source=self._ref(path), tool="read_file"
            )

        rx = re.compile(pattern)
        hits = [
            f"{path}:{i}: {line.strip()}"
            for i, line in enumerate(content.splitlines(), 1)
            if rx.search(line)
        ]
        return Evidence(
            found=bool(hits),
            excerpt="\n".join(hits[:20]),
            source=self._ref(path),
            tool="read_file",
            raw_lines=hits,
        )

    def grep(self, pattern: str, glob: str = "*") -> Evidence:
        """Search tracked files. Uses git grep so it honours the pinned commit."""
        args = ["grep", "-n", "-E", pattern]
        if self.commit:
            args.append(self.commit)
        args += ["--", glob]
        proc = self._git(*args)

        # git grep exits 1 on "no matches", which is an answer, not a failure.
        if proc.returncode not in (0, 1):
            return Evidence(
                found=False, tool="grep", source=glob, error=proc.stderr.strip() or "grep failed"
            )

        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        return Evidence(
            found=bool(lines),
            excerpt="\n".join(lines[:20]),
            source=f"grep {pattern!r} in {glob}",
            tool="grep",
            raw_lines=lines,
        )

    def git_log_search(self, needle: str, path: str | None = None) -> Evidence:
        """Find commits that added or removed `needle` (git log -S).

        This is the tool that settles "was this already fixed?", which neither
        reading HEAD nor reading the old commit can answer on its own.
        """
        args = ["log", "--oneline", "-S", needle]
        if path:
            args += ["--", path]
        proc = self._git(*args)
        if proc.returncode != 0:
            return Evidence(
                found=False, tool="git_log_search", source=path or "", error=proc.stderr.strip()
            )
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        return Evidence(
            found=bool(lines),
            excerpt="\n".join(lines[:10]),
            source=f"git log -S {needle!r}" + (f" -- {path}" if path else ""),
            tool="git_log_search",
            raw_lines=lines,
        )

    def list_dir(self, path: str = ".") -> Evidence:
        args = ["ls-tree", "--name-only", f"{self.commit or 'HEAD'}:{path}"]
        proc = self._git(*args)
        if proc.returncode != 0:
            return Evidence(
                found=False, tool="list_dir", source=path, error=proc.stderr.strip()
            )
        names = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        return Evidence(
            found=bool(names),
            excerpt="\n".join(names[:50]),
            source=self._ref(path),
            tool="list_dir",
            raw_lines=names,
        )


TOOLS = ("read_file", "grep", "git_log_search", "list_dir")
