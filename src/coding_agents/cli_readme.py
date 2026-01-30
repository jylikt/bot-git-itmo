import argparse
import os
import sys
from pathlib import Path

from git import Repo
from git.exc import InvalidGitRepositoryError

from coding_agents.config import Config
from coding_agents.llm.factory import create_llm_client
from coding_agents.readme_generator import ReadmeGenerator
from coding_agents.git_ops import ensure_cached_clone


def run_readme(args: argparse.Namespace) -> None:
    cfg = Config.from_env()
    try:
        llm = create_llm_client(cfg)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    workspace = getattr(args, "repo_path", None) or cfg.workspace_path
    if not workspace:
        workspace = Path.cwd()
    workspace = Path(workspace).resolve()

    try:
        Repo(workspace)
    except InvalidGitRepositoryError:
        if cfg.repo_owner and cfg.repo_name:
            base_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
            workspace = ensure_cached_clone(
                cfg.repo_owner,
                cfg.repo_name,
                cfg.github_token,
                base_url=base_url,
            )
            print(f"Using cached clone at {workspace}", file=sys.stderr)
        else:
            print(
                "Not a Git repository. Set GITHUB_REPOSITORY or run from repo / pass --repo-path.",
                file=sys.stderr,
            )
            sys.exit(1)

    generator = ReadmeGenerator(llm, workspace)
    content = generator.generate()
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    out = getattr(args, "output", None)
    if out is None:
        output_path = workspace / "README.md"
    else:
        output_path = Path(out)
        if not output_path.is_absolute():
            output_path = (workspace / output_path).resolve()
        else:
            output_path = output_path.resolve()

    if getattr(args, "dry_run", False):
        print(content)
        return

    output_path.write_text(content, encoding="utf-8")
    print(f"Written to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate README.md from project structure and config")
    parser.add_argument("--repo-path", type=Path, default=None, help="Project root (default: current dir or clone)")
    parser.add_argument("--output", type=Path, default=None, help="Output path (default: <repo>/README.md)")
    parser.add_argument("--dry-run", action="store_true", help="Print README to stdout, do not write file")
    args = parser.parse_args()
    run_readme(args)


if __name__ == "__main__":
    main()
