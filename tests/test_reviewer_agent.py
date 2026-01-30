from unittest.mock import MagicMock

import pytest

from coding_agents.reviewer_agent import ReviewerAgent


@pytest.fixture
def llm_mock():
    return MagicMock()


@pytest.fixture
def github_mock():
    return MagicMock()


@pytest.fixture
def reviewer(llm_mock, github_mock):
    return ReviewerAgent(llm_mock, github_mock)


def test_review_returns_llm_response(reviewer):
    reviewer._llm.chat.return_value = "VERDICT: APPROVED"
    out = reviewer.review(
        issue_body="Fix layout",
        issue_title="Issue 1",
        pr_diff="diff --git a/index.html",
        pr_files=[{"filename": "index.html", "patch": "+<div>"}],
        ci_summary="OK",
    )
    assert out == "VERDICT: APPROVED"
    assert reviewer._llm.chat.called


def test_post_review_to_pr_adds_comment(reviewer):
    reviewer.post_review_to_pr(1, "Review text")
    reviewer._github.add_pr_comment.assert_called_once_with(1, "Review text")


def test_post_review_to_pr_adds_label_on_changes_requested(reviewer):
    reviewer.post_review_to_pr(1, "VERDICT: CHANGES_REQUESTED\nFix X")
    reviewer._github.add_pr_comment.assert_called_once()
    reviewer._github.add_pr_label.assert_called_once_with(1, "agent-fix-requested")
