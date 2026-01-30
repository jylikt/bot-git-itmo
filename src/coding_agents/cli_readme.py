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

    from coding_agents.git_ops import parse_github_url

    repo_path_arg = getattr(args, "repo_path", None)
    workspace = None

    if repo_path_arg is not None:
        repo_path_str = str(repo_path_arg)
        if repo_path_str.startswith("http://") or repo_path_str.startswith("https://") or repo_path_str.startswith("git@"):
            parsed = parse_github_url(repo_path_str)
            if parsed:
                owner, repo_name = parsed
                base_url = "https://github.com" if "github.com" in repo_path_str else os.environ.get("GITHUB_SERVER_URL", "https://github.com")
                workspace = ensure_cached_clone(
                    owner,
                    repo_name,
                    cfg.github_token,
                    base_url=base_url,
                )
                print(f"Cloned from URL to {workspace}", file=sys.stderr)
            else:
                print("Could not parse GitHub URL. Use https://github.com/owner/repo or https://github.com/owner/repo.git", file=sys.stderr)
                sys.exit(1)
        else:
            workspace = Path(repo_path_arg).resolve()
            if not workspace.exists():
                print(f"Path does not exist: {workspace}", file=sys.stderr)
                sys.exit(1)

    if workspace is None:
        workspace = cfg.workspace_path or Path.cwd()
        workspace = Path(workspace).resolve()

    if workspace is None or not workspace.exists():
        workspace = Path.cwd().resolve()

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
                "Not a Git repository. Set GITHUB_REPOSITORY, pass --repo-path as path or URL (e.g. https://github.com/owner/repo.git).",
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
        try:
            origin_url = Repo(workspace).remotes.origin.url
            parsed = parse_github_url(origin_url)
            repo_name = parsed[1] if parsed else workspace.name
        except Exception:
            repo_name = workspace.name
        output_dir = Path.cwd() / "generate-readme" / repo_name
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "README.md"
    else:
        output_path = Path(out)
        if not output_path.is_absolute():
            output_path = (Path.cwd() / output_path).resolve()
        else:
            output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

    if getattr(args, "dry_run", False):
        print(content)
        return

    output_path.write_text(content, encoding="utf-8")
    print(f"Written to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate README.md from project structure and config")
    parser.add_argument("--repo-path", default=None, help="Project root: local path or GitHub URL (e.g. https://github.com/owner/repo.git)")
    parser.add_argument("--output", type=Path, default=None, help="Output path (default: <repo>/README.md)")
    parser.add_argument("--dry-run", action="store_true", help="Print README to stdout, do not write file")
    args = parser.parse_args()
    run_readme(args)


if __name__ == "__main__":
    main()
