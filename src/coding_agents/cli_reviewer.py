import argparse
import os
import sys

from coding_agents.config import Config
from coding_agents.github_client import GitHubClient
from coding_agents.llm.factory import create_llm_client
from coding_agents.reviewer_agent import ReviewerAgent


def run_reviewer(args: argparse.Namespace) -> None:
    cfg = Config.from_env()
    if not cfg.github_token:
        print("Set GITHUB_TOKEN", file=sys.stderr)
        sys.exit(1)
    try:
        llm = create_llm_client(cfg)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    ci_summary = args.ci_summary or os.environ.get("CI_SUMMARY", "No CI data provided.")

    gh = GitHubClient(cfg.github_token, cfg.repo_owner, cfg.repo_name)
    reviewer = ReviewerAgent(llm, gh)

    issue_body = gh.get_issue_body(args.issue)
    issue_title = gh.get_issue_title(args.issue)
    pr_diff = gh.get_pr_diff(args.pr)
    pr_files = gh.get_pr_files(args.pr)

    review_text = reviewer.review(
        issue_body, issue_title, pr_diff, pr_files, ci_summary
    )
    reviewer.post_review_to_pr(args.pr, review_text)
    print("Review posted")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Reviewer Agent: review PR and post comment")
    parser.add_argument("--pr", type=int, required=True, help="Pull request number")
    parser.add_argument("--issue", type=int, required=True, help="Issue number (for requirements)")
    parser.add_argument("--ci-summary", type=str, default="", help="CI jobs summary (e.g. from GHA)")
    args = parser.parse_args()
    run_reviewer(args)


if __name__ == "__main__":
    main()
