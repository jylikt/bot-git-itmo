import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from coding_agents.git_ops import clone_to_temp, commit_and_push, ensure_branch


def test_clone_to_temp_creates_dir_and_clones():
    with patch("coding_agents.git_ops.Repo") as repo_mock:
        path = clone_to_temp("owner", "repo", "token")
        assert path.exists()
        assert path.is_dir()
        repo_mock.clone_from.assert_called_once()
        url = repo_mock.clone_from.call_args[0][0]
        assert "owner" in url or "repo" in url
        assert repo_mock.clone_from.call_args[1]["branch"] == "main"


def test_ensure_branch_from_current_head(tmp_path):
    with patch("coding_agents.git_ops.Repo") as repo_mock:
        repo = MagicMock()
        repo_mock.return_value = repo
        ensure_branch(tmp_path, "feature-x", from_current_head=True)
        repo.git.checkout.assert_called_once_with("-B", "feature-x")


def test_commit_and_push(tmp_path):
    (tmp_path / "foo.txt").write_text("hi")
    with patch("coding_agents.git_ops.Repo") as repo_mock:
        repo = MagicMock()
        repo.is_dirty.return_value = True
        repo.untracked_files = []
        repo_mock.return_value = repo
        commit_and_push(tmp_path, "main", "msg", "https://x@github.com/o/r.git")
        repo.index.commit.assert_called_once_with("msg")
        repo.remotes.origin.push.assert_called_once()
