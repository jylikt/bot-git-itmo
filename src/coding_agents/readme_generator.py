import re
from pathlib import Path

from coding_agents.llm.base import LLMClientProtocol


README_SYSTEM = """You generate a README.md for a software project based on its files and structure.

Rules:
1. Determine project type: application (needs run/deploy) or library (clone and use in code). Use file presence: Dockerfile, docker-compose, package.json scripts, pyproject.toml [project.scripts], main/app entry points → application; package-only, no run instructions → library.
2. Write in Markdown. Language: same as the project (if config/comments are in Russian, write README in Russian; else English).
3. Structure:
   - Short title and 1–2 sentence description.
   - For applications: "How to run" with steps starting from git clone, then install dependencies, then run (exact commands). If Docker/docker-compose exists, include docker commands. Mention required env vars or .env if present.
   - For libraries: "Install" (e.g. pip install / npm install from repo or package name) and "Usage" with minimal code example if you can infer the API from the code.
   - Optional: requirements (Python/Node version, etc.), project structure, license if visible.
4. Use only the information from the provided project context. Do not invent dependencies or commands that are not in the files. If something is unclear, write a short placeholder or "see source".
5. For git clone: use ONLY the "Repository clone URL" given in the context. It must be an HTTPS URL (e.g. https://github.com/owner/repo.git). Never use local paths, absolute paths, or file:// URLs in README.
6. Output only the README body, no surrounding explanation."""


def _origin_to_https(workspace: Path) -> str | None:
    try:
        from git import Repo
        repo = Repo(workspace)
        origin = repo.remotes.origin.url
    except Exception:
        return None
    url = origin.strip()
    if "@" in url and "://" in url:
        url = url.split("@", 1)[-1]
        url = "https://" + url
    if url.startswith("https://"):
        if ".git" not in url.split("/")[-1]:
            url = f"{url.rstrip('/')}.git"
        return url
    if url.startswith("git@"):
        m = re.match(r"git@[^:]+:([^/]+)/([^/]+?)(\.git)?$", url)
        if m:
            return f"https://github.com/{m.group(1)}/{m.group(2)}.git"
    return None


class ReadmeGenerator:
    def __init__(self, llm: LLMClientProtocol, workspace: Path):
        self._llm = llm
        self._workspace = workspace

    def _collect_context(self, max_file_bytes: int = 15000) -> str:
        repo_url = _origin_to_https(self._workspace)
        lines = []
        if repo_url:
            lines.append(f"Repository clone URL (use exactly this in README for git clone): {repo_url}")
            lines.append("")
        lines.append("File tree:")
        key_files = [
            "README.md", "pyproject.toml", "setup.py", "requirements.txt",
            "package.json", "Dockerfile", "docker-compose.yml", ".env.example",
        ]
        seen = set()
        for path in sorted(self._workspace.rglob("*")):
            if not path.is_file() or ".git" in path.parts:
                continue
            try:
                rel = path.relative_to(self._workspace)
            except ValueError:
                continue
            if rel.name in key_files or rel.suffix in (".toml", ".json", ".yaml", ".yml"):
                seen.add(rel)
        file_tree = []
        for path in sorted(self._workspace.rglob("*")):
            if not path.is_file() or ".git" in path.parts:
                continue
            try:
                rel = path.relative_to(self._workspace)
            except ValueError:
                continue
            file_tree.append(str(rel))
        lines.append("\n".join(file_tree[:200]))
        lines.append("")
        for name in key_files:
            p = self._workspace / name
            if p.is_file():
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                if len(content.encode("utf-8")) > max_file_bytes:
                    content = content[:max_file_bytes] + "\n... (truncated)"
                lines.append(f"--- {name} ---\n{content}\n")
        for path in sorted(self._workspace.rglob("*.toml")) + sorted(self._workspace.rglob("*.json")):
            try:
                rel = path.relative_to(self._workspace)
            except ValueError:
                continue
            if str(rel) in seen or rel.name in key_files:
                continue
            if path.stat().st_size > max_file_bytes:
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            lines.append(f"--- {rel} ---\n{content}\n")
            seen.add(str(rel))
        return "\n".join(lines)

    def generate(self) -> str:
        context = self._collect_context()
        user = f"Generate README.md for this project.\n\n{context}"
        return self._llm.chat(
            [{"role": "system", "content": README_SYSTEM}, {"role": "user", "content": user}]
        )
