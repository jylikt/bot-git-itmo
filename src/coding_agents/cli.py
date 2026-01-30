import argparse
from pathlib import Path

from coding_agents.cli_code_agent import run_code_agent
from coding_agents.cli_readme import run_readme
from coding_agents.cli_reviewer import run_reviewer


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="gaj",
        description="Coding Agents: code (issue -> PR), reviewer (PR review)",
    )
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    code_parser = subparsers.add_parser("code", help="Code Agent: take Issue, create/update PR")
    code_parser.add_argument("--issue", type=int, required=True, help="Issue number")
    code_parser.add_argument("--pr", type=int, default=None, help="Existing PR (re-run)")
    code_parser.add_argument("--repo-path", type=Path, default=None, help="Repo path")
    code_parser.add_argument("--verbose", "-v", action="store_true", help="Print issue title/body")
    code_parser.add_argument("--no-cache", action="store_true", help="Clone to temp dir instead of cache")

    reviewer_parser = subparsers.add_parser("reviewer", help="Reviewer Agent: review PR and post comment")
    reviewer_parser.add_argument("--pr", type=int, required=True, help="Pull request number")
    reviewer_parser.add_argument("--issue", type=int, required=True, help="Issue number (for requirements)")
    reviewer_parser.add_argument("--ci-summary", type=str, default="", help="CI jobs summary")

    readme_parser = subparsers.add_parser("readme", help="Generate README.md from project structure")
    readme_parser.add_argument("--repo-path", type=Path, default=None, help="Project root (default: cwd or clone)")
    readme_parser.add_argument("--output", type=Path, default=None, help="Output file (default: <repo>/README.md)")
    readme_parser.add_argument("--dry-run", action="store_true", help="Print README to stdout")

    args = parser.parse_args()
    if args.cmd == "code":
        run_code_agent(args)
    elif args.cmd == "reviewer":
        run_reviewer(args)
    elif args.cmd == "readme":
        run_readme(args)


if __name__ == "__main__":
    main()
