import re
import shutil
import tempfile
from pathlib import Path

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError


def get_cache_root() -> Path:
    import os
    p = os.environ.get("AGENT_CACHE_DIR")
    if p:
        return Path(p).resolve()
    return Path.cwd() / ".agent_cache"


def _cache_key(owner: str, repo_name: str) -> str:
    key = f"{owner}_{repo_name}"
    key = re.sub(r"[^\w\-.]", "_", key)
    return key.strip("_") or "repo"


def _clone_into(url: str, path: Path, branch: str) -> None:
    Repo.clone_from(url, path, branch=branch)


def clone_to_temp(
    owner: str,
    repo_name: str,
    token: str,
    base_url: str = "https://github.com",
    base_branch: str = "main",
) -> Path:
    path = Path(tempfile.mkdtemp(prefix="coding_agent_"))
    url = _build_clone_url(owner, repo_name, token, base_url)
    _clone_into(url, path, base_branch)
    return path


def parse_github_url(url: str) -> tuple[str, str] | None:
    url = url.strip().rstrip("/")
    if url.startswith("git@"):
        m = re.match(r"git@[^:]+:([^/]+)/([^/]+?)(\.git)?$", url)
        if m:
            return (m.group(1), m.group(2).removesuffix(".git"))
        return None
    if "github.com" in url:
        m = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(\.git)?/?$", url)
        if m:
            return (m.group(1), m.group(2).removesuffix(".git"))
    return None


def _build_clone_url(
    owner: str,
    repo_name: str,
    token: str,
    base_url: str = "https://github.com",
) -> str:
    url = f"{base_url.rstrip('/')}/{owner}/{repo_name}.git"
    if token:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        url = f"{parsed.scheme}://x-access-token:{token}@{parsed.netloc}{parsed.path}"
    return url


def ensure_cached_clone(
    owner: str,
    repo_name: str,
    token: str,
    base_url: str = "https://github.com",
    base_branch: str = "main",
    cache_root: Path | None = None,
) -> Path:
    root = cache_root or get_cache_root()
    root.mkdir(parents=True, exist_ok=True)
    cache_dir = root / _cache_key(owner, repo_name)
    url = _build_clone_url(owner, repo_name, token, base_url)

    if cache_dir.exists():
        try:
            repo = Repo(cache_dir)
            repo.remotes.origin.fetch()
            for branch in (base_branch, "master"):
                try:
                    repo.git.checkout(branch)
                    repo.git.reset("--hard", f"origin/{branch}")
                    break
                except GitCommandError:
                    continue
        except (InvalidGitRepositoryError, GitCommandError):
            shutil.rmtree(cache_dir, ignore_errors=True)
            _clone_into(url, cache_dir, base_branch)
    else:
        _clone_into(url, cache_dir, base_branch)

    return cache_dir


def ensure_branch(
    repo_path: Path,
    branch_name: str,
    base: str = "main",
    from_current_head: bool = False,
) -> Repo:
    repo = Repo(repo_path)
    if from_current_head:
        repo.git.checkout("-B", branch_name)
        return repo
    try:
        repo.remotes.origin.fetch()
    except GitCommandError:
        pass
    if branch_name in [b.name for b in repo.branches]:
        repo.git.checkout(branch_name)
        try:
            repo.git.pull("origin", branch_name)
        except GitCommandError:
            pass
    else:
        try:
            repo.git.checkout("-b", branch_name, f"origin/{branch_name}")
        except GitCommandError:
            try:
                repo.git.checkout("-b", branch_name, f"origin/{base}")
            except GitCommandError:
                repo.git.checkout("-b", branch_name)
    return repo


def commit_and_push(
    repo_path: Path,
    branch_name: str,
    message: str,
    remote_url: str | None = None,
) -> None:
    repo = Repo(repo_path)
    repo.git.add(A=True)
    if repo.is_dirty() or repo.untracked_files:
        repo.index.commit(message)
    origin = repo.remotes.origin
    if remote_url:
        origin.set_url(remote_url)
    origin.push(branch_name, force=True)
