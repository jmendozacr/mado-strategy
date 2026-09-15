"""Git operations for baseline verification.

Tests use temporary git repos, never real discovery data."""

import subprocess

import pytest


def _git_init(tmp_path):
    """Initialize a minimal git repo with one commit."""
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmp_path), check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path), check=True, capture_output=True,
    )
    (tmp_path / "file.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=str(tmp_path), check=True, capture_output=True,
    )
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(tmp_path), check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def test_verify_commit_exists(tmp_path):
    from runner.git_ops import verify_commit_exists

    commit = _git_init(tmp_path)
    verify_commit_exists(commit, str(tmp_path))


def test_verify_commit_not_exists(tmp_path):
    from runner.git_ops import verify_commit_exists

    _git_init(tmp_path)
    with pytest.raises(Exception):
        verify_commit_exists("0" * 40, str(tmp_path))


def test_verify_ancestor(tmp_path):
    from runner.git_ops import verify_is_ancestor

    base = _git_init(tmp_path)
    (tmp_path / "file2.txt").write_text("second")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "second"],
        cwd=str(tmp_path), check=True, capture_output=True,
    )
    verify_is_ancestor(base, str(tmp_path))


def test_verify_not_ancestor(tmp_path):
    from runner.git_ops import verify_is_ancestor

    initial = _git_init(tmp_path)
    subprocess.run(
        ["git", "checkout", "--orphan", "orphan"],
        cwd=str(tmp_path), check=True, capture_output=True,
    )
    (tmp_path / "orphan.txt").write_text("orphan")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "orphan"],
        cwd=str(tmp_path), check=True, capture_output=True,
    )
    with pytest.raises(Exception):
        verify_is_ancestor(initial, str(tmp_path))


def test_verify_no_committed_diff(tmp_path):
    from runner.git_ops import verify_no_diff

    base = _git_init(tmp_path)
    verify_no_diff(base, ["file.txt"], str(tmp_path))


def test_committed_diff_detected(tmp_path):
    from runner.git_ops import verify_no_diff

    base = _git_init(tmp_path)
    (tmp_path / "file.txt").write_text("modified")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "modify"],
        cwd=str(tmp_path), check=True, capture_output=True,
    )
    with pytest.raises(Exception, match="file.txt"):
        verify_no_diff(base, ["file.txt"], str(tmp_path))


def test_staged_diff_detected(tmp_path):
    from runner.git_ops import verify_no_staged_diff

    base = _git_init(tmp_path)
    (tmp_path / "file.txt").write_text("staged")
    subprocess.run(["git", "add", "file.txt"], cwd=str(tmp_path), check=True, capture_output=True)
    with pytest.raises(Exception, match="staged"):
        verify_no_staged_diff(base, ["file.txt"], str(tmp_path))


def test_untracked_file_detected(tmp_path):
    from runner.git_ops import verify_no_untracked

    _git_init(tmp_path)
    (tmp_path / "new_untracked.txt").write_text("untracked")
    with pytest.raises(Exception, match="untracked"):
        verify_no_untracked(["./"], str(tmp_path))


def test_get_head_commit(tmp_path):
    from runner.git_ops import get_head_commit

    expected = _git_init(tmp_path)
    actual = get_head_commit(str(tmp_path))
    assert actual == expected
