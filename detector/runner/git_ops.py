"""Subprocess-based local git operations for baseline verification.

The ONLY module in runner/ that calls subprocess. All commands use explicit
argument lists, check=True, and explicit cwd. No shell=True."""

import subprocess

from runner.errors import AuthorizationError

_ALLOWED_SUBCOMMANDS = frozenset({
    "rev-parse", "merge-base", "diff", "status", "log",
})


def _run_git(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    if args[0] not in _ALLOWED_SUBCOMMANDS:
        raise AuthorizationError(f"git subcommand {args[0]!r} not in allowlist")
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def get_head_commit(cwd: str) -> str:
    result = _run_git(["rev-parse", "HEAD"], cwd)
    return result.stdout.strip()


def verify_commit_exists(commit: str, cwd: str) -> None:
    """Verify a commit name resolves to a Git commit."""
    try:
        _run_git(["rev-parse", "--verify", f"{commit}^{{commit}}"], cwd)
    except subprocess.CalledProcessError as e:
        raise AuthorizationError(
            f"commit {commit!r} is not a resolvable git commit"
        ) from e


def verify_is_ancestor(commit: str, cwd: str, descendant: str = "HEAD") -> None:
    """Verify one commit is an ancestor of another commit or HEAD."""
    try:
        _run_git(["merge-base", "--is-ancestor", commit, descendant], cwd)
    except subprocess.CalledProcessError as e:
        raise AuthorizationError(
            f"commit {commit!r} is not an ancestor of {descendant!r}"
        ) from e


def verify_no_diff(baseline: str, protected_paths: list[str], cwd: str) -> None:
    """Check 5: committed state matches baseline for protected paths."""
    result = subprocess.run(
        ["git", "diff", baseline, "HEAD", "--"] + protected_paths,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        raise AuthorizationError(
            f"committed diff detected against baseline {baseline!r} "
            f"in protected paths: {result.stdout[:200]}"
        )


def verify_no_working_tree_diff(baseline: str, protected_paths: list[str], cwd: str) -> None:
    """Check 6: working tree matches baseline for protected paths."""
    result = subprocess.run(
        ["git", "diff", baseline, "--"] + protected_paths,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        raise AuthorizationError(
            f"working tree diff detected against baseline {baseline!r} "
            f"in protected paths: {result.stdout[:200]}"
        )


def verify_no_staged_diff(baseline: str, protected_paths: list[str], cwd: str) -> None:
    """Check 7: no staged-but-uncommitted edits in protected paths."""
    result = subprocess.run(
        ["git", "diff", "--cached", baseline, "--"] + protected_paths,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        raise AuthorizationError(
            f"staged diff detected against baseline {baseline!r} "
            f"in protected paths: {result.stdout[:200]}"
        )


def verify_no_untracked(protected_paths: list[str], cwd: str) -> None:
    """Check 8: no untracked files under protected paths."""
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all", "--"] + protected_paths,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    untracked = [
        line for line in result.stdout.strip().splitlines()
        if line.startswith("??")
    ]
    if untracked:
        raise AuthorizationError(
            f"untracked files detected under protected paths: {untracked}"
        )
