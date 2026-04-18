"""
NEXUS OS v5 — Git Evolution Tracker
====================================
Tracks evolution changes with git: commit history, branch per improvement,
diff tracking, and version rollback.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─── Config ────────────────────────────────────────────────────────────────────

DEFAULT_REPO = Path.home() / "NEXUS_OS"
GIT_USER = "NEXUS-OS-Evolver"
GIT_EMAIL = "nexus@evolution.local"


# ─── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class GitDiff:
    file: str
    additions: int
    deletions: int
    status: str  # added, modified, deleted
    patch: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvolutionCommit:
    cycle: int
    commit_hash: str
    message: str
    type: str  # evolve_skill, upgrade_code, crawl_learn, etc
    target: str
    files_changed: List[str] = field(default_factory=list)
    diffs: List[GitDiff] = field(default_factory=list)
    score_before: float = 0.0
    score_after: float = 0.0
    timestamp: float = field(default_factory=time.time)

    @property
    def delta(self) -> float:
        return self.score_after - self.score_before

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "diffs": [d.to_dict() for d in self.diffs],
            "delta": self.delta,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
        }


# ─── Git Evolution ─────────────────────────────────────────────────────────────

class GitEvolution:
    """
    Tracks NEXUS OS evolution with git.
    
    Each evolution cycle creates a commit with:
    - The files changed
    - A structured commit message with cycle info
    - Diff tracking
    - Branch per major evolution type
    
    Can roll back, compare, and replay evolution history.
    """

    def __init__(self, repo_path: Path = None):
        self.repo = repo_path or DEFAULT_REPO
        self.repo = self.repo.resolve()
        self._git_env = {
            "GIT_AUTHOR_NAME": GIT_USER,
            "GIT_AUTHOR_EMAIL": GIT_EMAIL,
            "GIT_COMMITTER_NAME": GIT_USER,
            "GIT_COMMITTER_EMAIL": GIT_EMAIL,
            "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        }

    # ─── Low-level git helpers ───────────────────────────────────────────────

    def _run(self, *args, check: bool = True, capture: bool = True,
             timeout: int = 30) -> subprocess.CompletedProcess:
        cmd = ["git", "-C", str(self.repo)] + list(args)
        kwargs = {
            "capture_output": capture,
            "text": True,
            "timeout": timeout,
            "env": {**subprocess.os.environ.copy(), **self._git_env},
        }
        if not capture:
            kwargs.pop("capture_output")
            kwargs.pop("text")
        result = subprocess.run(cmd, **kwargs)
        if check and result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
        return result

    def is_repo(self) -> bool:
        """Check if repo_path is a git repository."""
        try:
            result = self._run("rev-parse", "--is-inside-work-tree", check=False)
            return result.stdout.strip() == "true"
        except Exception:
            return False

    def init(self) -> bool:
        """Initialize git repo if not already."""
        if self.is_repo():
            return False
        self._run("init", "--initial-branch=main")
        self._run("config", "user.name", GIT_USER)
        self._run("config", "user.email", GIT_EMAIL)
        return True

    def get_status(self) -> List[GitDiff]:
        """Get current working tree status."""
        result = self._run("diff", "--numstat", capture=True)
        diffs = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                add, delete, file = parts[0], parts[1], parts[2]
                diffs.append(GitDiff(
                    file=file,
                    additions=int(add) if add != "-" else 0,
                    deletions=int(delete) if delete != "-" else 0,
                    status="modified",
                ))

        # Also get untracked files
        result = self._run("ls-files", "--others", "--exclude-standard", capture=True)
        for f in result.stdout.strip().splitlines():
            if f:
                diffs.append(GitDiff(file=f, additions=0, deletions=0, status="added"))

        return diffs

    def get_staged_diff(self) -> List[GitDiff]:
        """Get diff of staged changes."""
        result = self._run("diff", "--cached", "--numstat", capture=True)
        diffs = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                add, delete, file = parts[0], parts[1], parts[2]
                diffs.append(GitDiff(
                    file=file,
                    additions=int(add) if add != "-" else 0,
                    deletions=int(delete) if delete != "-" else 0,
                    status="modified",
                ))
        return diffs

    def get_current_branch(self) -> str:
        result = self._run("branch", "--show-current")
        return result.stdout.strip()

    def get_commits(self, count: int = 20) -> List[Dict[str, str]]:
        """Get recent commits."""
        result = self._run("log", f"--oneline", f"-{count}", capture=True)
        commits = []
        for line in result.stdout.strip().splitlines():
            if " " in line:
                hash_, *msg_parts = line.split(" ")
                msg = " ".join(msg_parts)
                commits.append({"hash": hash_, "message": msg})
        return commits

    def get_commit_details(self, ref: str) -> Dict[str, Any]:
        """Get details of a specific commit."""
        result = self._run("show", "--stat", "--format=%H%n%an%n%ae%n%at%n%s%n%b", ref, capture=True)
        lines = result.stdout.strip().splitlines()
        if len(lines) < 6:
            return {}
        return {
            "hash": lines[0],
            "author": lines[1],
            "email": lines[2],
            "timestamp": float(lines[3]),
            "subject": lines[4],
            "body": "\n".join(lines[6:]) if len(lines) > 6 else "",
        }

    def diff_files(self, ref1: str, ref2: str = None) -> List[GitDiff]:
        """Get diff between two refs or ref vs working tree."""
        cmd = ["diff", "--numstat"]
        if ref2:
            cmd.append(ref2)
        result = self._run(*cmd, capture=True)
        diffs = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                add, delete, file = parts[0], parts[1], parts[2]
                diffs.append(GitDiff(
                    file=file,
                    additions=int(add) if add != "-" else 0,
                    deletions=int(delete) if delete != "-" else 0,
                    status="modified",
                ))
        return diffs

    # ─── Evolution commits ───────────────────────────────────────────────────

    def commit_evolution(self, cycle: int, evo_type: str, target: str,
                         score_before: float, score_after: float,
                         files: List[str] = None) -> EvolutionCommit:
        """
        Stage, commit evolution changes, and return commit info.
        
        Creates a structured commit message with evolution metadata.
        """
        # Ensure tracked
        if not files:
            return None

        # Stage files
        for f in files:
            fpath = self.repo / f
            if fpath.exists():
                self._run("add", f)
            elif f.startswith("~/"):
                # Expand ~ path
                expanded = Path(f).expanduser()
                if expanded.exists():
                    self._run("add", str(expanded))

        # Create structured commit message
        delta = score_after - score_before
        emoji = "🧬" if delta > 0 else "🔄" if delta == 0 else "⚠️"
        message = (
            f"{emoji} Evolution [{cycle}] {evo_type}: {target}\n\n"
            f"Cycle: {cycle}\n"
            f"Type: {evo_type}\n"
            f"Target: {target}\n"
            f"Score: {score_before:.3f} → {score_after:.3f} ({delta:+.3f})\n"
            f"Files: {', '.join(files)}\n"
            f"Generated by: NEXUS-OS-v5-Evolution"
        )

        # Commit
        try:
            result = self._run("commit", "-m", message, capture=True)
            commit_hash = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
            if "nothing to commit" in result.stdout:
                commit_hash = self._run("rev-parse", "HEAD", capture=True).stdout.strip()[:8]
        except Exception as e:
            commit_hash = self._run("rev-parse", "HEAD", capture=True).stdout.strip()[:8]

        # Get staged diffs for the commit
        staged_diffs = self.get_staged_diff() or self.diff_files("HEAD")

        return EvolutionCommit(
            cycle=cycle,
            commit_hash=commit_hash[:8],
            message=message,
            type=evo_type,
            target=target,
            files_changed=files,
            diffs=staged_diffs,
            score_before=score_before,
            score_after=score_after,
        )

    def get_evolution_history(self, count: int = 30) -> List[EvolutionCommit]:
        """Parse evolution commits from git log."""
        result = self._run(
            "log", f"--format=%H%n%s%n%b", f"-{count}", capture=True
        )
        commits_text = result.stdout.strip()

        commits = []
        # Parse commit blocks (hash, subject, body)
        blocks = commits_text.split("\n\n")
        i = 0
        while i < len(blocks) - 2:
            commit_hash = blocks[i].strip()
            subject = blocks[i + 1].strip() if i + 1 < len(blocks) else ""
            body = blocks[i + 2].strip() if i + 2 < len(blocks) else ""

            # Parse body for metadata
            cycle = 0
            evo_type = ""
            target = ""
            score_before = 0.0
            score_after = 0.0

            for line in body.splitlines():
                if line.startswith("Cycle:"):
                    try:
                        cycle = int(line.split(":")[1].strip())
                    except (ValueError, IndexError):
                        pass
                elif line.startswith("Type:"):
                    evo_type = line.split(":")[1].strip()
                elif line.startswith("Target:"):
                    target = line.split(":")[1].strip()
                elif line.startswith("Score:"):
                    try:
                        score_str = line.split(":")[1].strip()
                        before, after = score_str.split("→")
                        score_before = float(before.strip())
                        score_after = float(after.strip().split()[0])
                    except (ValueError, IndexError):
                        pass

            if cycle > 0:  # Only evolution commits
                commits.append(EvolutionCommit(
                    cycle=cycle,
                    commit_hash=commit_hash[:8],
                    message=subject,
                    type=evo_type,
                    target=target,
                    score_before=score_before,
                    score_after=score_after,
                ))

            i += 3

        return commits

    # ─── Branches ─────────────────────────────────────────────────────────────

    def create_branch(self, name: str) -> str:
        """Create a new branch for evolution tracking."""
        result = self._run("checkout", "-b", name, check=False, capture=True)
        return result.stdout.strip() or result.stderr.strip()

    def switch_branch(self, name: str) -> bool:
        """Switch to existing branch."""
        try:
            self._run("checkout", name)
            return True
        except Exception:
            return False

    def list_branches(self) -> List[str]:
        result = self._run("branch", "--format=%(refname:short)", capture=True)
        return [b.strip() for b in result.stdout.strip().splitlines() if b.strip()]

    # ─── Rollback ─────────────────────────────────────────────────────────────

    def rollback(self, commit_ref: str, force: bool = False) -> bool:
        """
        Rollback to a specific evolution commit.
        Creates a new rollback commit.
        """
        try:
            if force:
                self._run("revert", "--no-commit", commit_ref)
                self._run("commit", "-m", f"🔙 Rollback to {commit_ref[:8]}")
            else:
                self._run("checkout", commit_ref, "--", ".")
            return True
        except Exception as e:
            return False

    # ─── Analysis ─────────────────────────────────────────────────────────────

    def get_evolution_stats(self) -> Dict[str, Any]:
        """Get statistics about evolution history."""
        history = self.get_evolution_history(count=100)

        if not history:
            return {"total_cycles": 0, "total_commits": 0}

        total_delta = sum(c.delta for c in history)
        avg_delta = total_delta / len(history) if history else 0
        positive = sum(1 for c in history if c.delta > 0)
        negative = sum(1 for c in history if c.delta < 0)

        by_type: Dict[str, List[float]] = {}
        for c in history:
            by_type.setdefault(c.type, []).append(c.delta)

        return {
            "total_cycles": len(history),
            "total_commits": len(self.get_commits(100)),
            "total_delta": total_delta,
            "avg_delta_per_cycle": avg_delta,
            "positive_cycles": positive,
            "negative_cycles": negative,
            "by_type": {t: sum(v) / len(v) for t, v in by_type.items()},
            "best_cycle": max(history, key=lambda c: c.delta).cycle if history else 0,
            "worst_cycle": min(history, key=lambda c: c.delta).cycle if history else 0,
        }


# ─── Test ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== NEXUS Git Evolution Test ===\n")

    ge = GitEvolution()

    if not ge.is_repo():
        print("Not a git repo. Initializing...")
        ge.init()
        print(f"Initialized at: {ge.repo}")
    else:
        print(f"Git repo: {ge.repo}")
        print(f"Branch: {ge.get_current_branch()}")
        print(f"Status: {len(ge.get_status())} files changed")

    print(f"Recent commits: {len(ge.get_commits(5))}")
    for c in ge.get_commits(3):
        print(f"  {c['hash'][:8]} {c['message'][:60]}")

    print(f"\nEvolution stats: {ge.get_evolution_stats()}")

    print("\n=== Git test complete ===")
