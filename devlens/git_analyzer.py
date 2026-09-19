"""Safe, read-only inspection of Git repository metadata.

DevLens NEVER executes git hooks, NEVER runs `git` commands that could
trigger arbitrary code (e.g. custom diff/merge drivers), and only ever
invokes a small, fixed allowlist of read-only, argument-locked
subprocess calls. If `git` is unavailable, DevLens falls back to
inspecting the .git directory structure directly.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional

# Fixed allowlist of read-only git subcommands. No user input is ever
# interpolated into these argument lists.
_SAFE_LOG_ARGS = ["git", "log", "-1", "--format=%H|%an|%ad", "--date=short"]
_SAFE_BRANCH_ARGS = ["git", "branch", "--show-current"]
_SAFE_COUNT_ARGS = ["git", "rev-list", "--count", "HEAD"]


def analyze_git(root: Path) -> Optional[Dict[str, str]]:
    git_dir = root / ".git"
    if not git_dir.exists():
        return None

    info: Dict[str, str] = {"has_git": "true"}

    if shutil.which("git") is None:
        info["note"] = "git executable not found; only directory presence detected"
        return info

    info.update(_run_safe(root, _SAFE_BRANCH_ARGS, "current_branch"))
    info.update(_run_safe(root, _SAFE_LOG_ARGS, "last_commit"))
    info.update(_run_safe(root, _SAFE_COUNT_ARGS, "commit_count"))

    return info


def _run_safe(root: Path, args: list, key: str) -> Dict[str, str]:
    try:
        result = subprocess.run(
            args,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            return {key: result.stdout.strip()}
        return {key: ""}
    except (OSError, subprocess.SubprocessError):
        return {key: ""}
