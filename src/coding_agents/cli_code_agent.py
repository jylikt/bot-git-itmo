import argparse
import os
import sys
from pathlib import Path

from git import Repo
from git.exc import InvalidGitRepositoryError

from coding_agents.code_agent import CodeAgent
from coding_agents.config import Config
from coding_agents.github_client import GitHubClient
from coding_agents.git_ops import commit_and_push, ensure_branch, ensure_cached_clone
from coding_agents.llm.factory import create_llm_client


def run_code_agent(args: argparse.Namespace) -> None:
    cfg = Config.from_env()
    if not cfg.github_token:
        print("Set GITHUB_TOKEN", file=sys.stderr)
        sys.exit(1)
    try:
        llm = create_llm_client(cfg)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    base_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    workspace = getattr(args, "repo_path", None)
    temp_workspace = None
    if workspace is not None:
        try:
            Repo(workspace)
        except InvalidGitRepositoryError:
            print(f"Not a Git repository: {workspace}", file=sys.stderr)
            sys.exit(1)
    elif cfg.repo_owner and cfg.repo_name:
        if getattr(args, "no_cache", False):
            from coding_agents.git_ops import clone_to_temp
            workspace = clone_to_temp(
                cfg.repo_owner,
                cfg.repo_name,
                cfg.github_token,
                base_url=base_url,
            )
            temp_workspace = workspace
            print(f"Cloned repo to {workspace}", file=sys.stderr)
        else:
            workspace = ensure_cached_clone(
                cfg.repo_owner,
                cfg.repo_name,
                cfg.github_token,
                base_url=base_url,
            )
            print(f"Using cached clone at {workspace} (updated from origin)", file=sys.stderr)
    else:
        workspace = cfg.workspace_path
        try:
            Repo(workspace)
        except InvalidGitRepositoryError:
            print(
                "Not a Git repository and GITHUB_REPOSITORY not set. "
                "Set GITHUB_REPOSITORY=owner/repo or run from a repo clone.",
                file=sys.stderr,
            )
            sys.exit(1)
    gh = GitHubClient(cfg.github_token, cfg.repo_owner, cfg.repo_name)
    agent = CodeAgent(llm, gh, workspace, config=cfg)

    issue_body = gh.get_issue_body(args.issue)
    issue_title = gh.get_issue_title(args.issue)
    if not issue_body and not issue_title:
        print("Issue not found or empty", file=sys.stderr)
        sys.exit(1)
    if getattr(args, "verbose", False):
        print(f"Repo: {cfg.repo_owner}/{cfg.repo_name}", file=sys.stderr)
        print(f"Issue #{args.issue} title: {issue_title!r}", file=sys.stderr)
        print(f"Issue #{args.issue} body:\n{issue_body}", file=sys.stderr)

    if args.pr:
        pr = gh.get_pr_by_number(args.pr)
        branch_name = pr.head.ref
    else:
        branch_name = f"agent-issue-{args.issue}"

    if args.pr:
        pr = gh.get_pr_by_number(args.pr)
        diff = gh.get_pr_diff(args.pr)
        comments = gh.get_pr_review_comments(args.pr) + gh.get_pr_comments(args.pr)
        plan = agent.plan_fixes(issue_body, issue_title, diff, comments)
    else:
        plan = agent.plan_changes(issue_body, issue_title)

    if not plan:
        print(
            "No changes planned (LLM returned empty or invalid plan). "
            "Check that the issue has a clear task and that the model supports JSON output.",
            file=sys.stderr,
        )
        sys.exit(0)

    ensure_branch(workspace, branch_name, from_current_head=bool(args.pr))
    agent.apply_plan(plan)
    commit_msg = f"Agent: address issue #{args.issue}"
    remote_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repo_slug = f"{cfg.repo_owner}/{cfg.repo_name}"
    push_url = f"{remote_url}/{repo_slug}.git"
    if cfg.github_token:
        from urllib.parse import urlparse
        parsed = urlparse(push_url)
        push_url = f"{parsed.scheme}://x-access-token:{cfg.github_token}@{parsed.netloc}{parsed.path}"
    commit_and_push(workspace, branch_name, commit_msg, push_url)

    existing = gh.get_pr_for_issue(args.issue)
    if not existing:
        body = f"Closes #{args.issue}\n\nAutomated PR by Code Agent."
        gh.create_pr(
            title=f"[Agent] {issue_title[:72]}",
            body=body,
            head=branch_name,
        )
    print("Done")
    if temp_workspace:
        print(f"Temp clone at {temp_workspace} (remove manually if not needed)", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Code Agent: issue -> code -> PR")
    parser.add_argument("--issue", type=int, required=True, help="Issue number")
    parser.add_argument("--pr", type=int, default=None, help="Existing PR (re-run)")
    parser.add_argument("--repo-path", type=Path, default=None, help="Repo path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print issue title/body sent to agent")
    parser.add_argument("--no-cache", action="store_true", help="Clone to temp dir instead of cache")
    args = parser.parse_args()
    run_code_agent(args)


if __name__ == "__main__":
    main()
