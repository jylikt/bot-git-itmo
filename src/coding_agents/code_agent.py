import json
import re
from pathlib import Path

from coding_agents.github_client import GitHubClient
from coding_agents.llm.base import LLMClientProtocol


PLAN_SYSTEM = """You are a coding agent. You receive:
1) The exact text of a GitHub Issue (title and body) — this is the task to implement.
2) Optionally "Current repo files" — existing file paths and their content. You MUST use this to modify existing files correctly; output the full updated content for any file you change.

Your task: implement what the issue asks for. If the issue describes changes to existing files, include those files in your output with the full new content. Do not leave out files that need to be updated.

Output a single JSON object only, no markdown: {"files": [{"path": "relative/path/to/file", "content": "full file content"}]}
- "files": non-empty array. "path" relative to repo root, "content" = complete file content (full file, not a patch).
- Code/HTML/CSS/JS: valid and complete. Output ONLY the JSON."""

FIX_SYSTEM = """You are a coding agent. Given an issue description, current PR diff, and reviewer feedback,
you produce a JSON plan of code changes to address the feedback.
Output ONLY valid JSON: {"files": [{"path": "relative/path", "content": "full file content"}]}
Paths relative to repo root. Provide full file content for each changed file. No comments, PEP 8."""


class CodeAgent:
    def __init__(
        self,
        llm: LLMClientProtocol,
        github: GitHubClient,
        workspace: Path,
    ):
        self._llm = llm
        self._github = github
        self._workspace = workspace

    def _repo_context(self, max_file_bytes: int = 50000) -> str:
        lines = ["Current repo files (path -> content):"]
        for fp in sorted(self._workspace.rglob("*")):
            if not fp.is_file() or ".git" in fp.parts:
                continue
            try:
                rel = fp.relative_to(self._workspace)
            except ValueError:
                continue
            try:
                content = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if len(content.encode("utf-8")) > max_file_bytes:
                content = content[:2000] + "\n... (truncated)"
            lines.append(f"\n--- {rel} ---\n{content}")
        return "\n".join(lines) if len(lines) > 1 else ""

    def plan_changes(self, issue_body: str, issue_title: str) -> list[dict]:
        user = f"Issue title: {issue_title}\n\nIssue body:\n{issue_body}"
        repo_ctx = self._repo_context()
        if repo_ctx:
            user += f"\n\n{repo_ctx}"
        out = self._llm.chat(
            [{"role": "system", "content": PLAN_SYSTEM}, {"role": "user", "content": user}]
        )
        return self._parse_plan(out)

    def plan_fixes(
        self,
        issue_body: str,
        issue_title: str,
        diff: str,
        review_comments: list[dict],
    ) -> list[dict]:
        feedback = "\n".join(
            f"- {c.get('body', c.get('path', ''))}" for c in review_comments
        )
        user = f"""Issue: {issue_title}\n{issue_body}\n\nPR diff:\n{diff}\n\nReviewer feedback:\n{feedback}\n\nProduce JSON plan of file changes to fix the feedback."""
        out = self._llm.chat(
            [
                {"role": "system", "content": FIX_SYSTEM},
                {"role": "user", "content": user},
            ]
        )
        return self._parse_plan(out)

    def _extract_json_object(self, raw: str) -> str:
        start = raw.find("{")
        if start == -1:
            return ""
        depth = 0
        in_string = False
        escape = False
        quote = None
        for i, c in enumerate(raw[start:], start=start):
            if escape:
                escape = False
                continue
            if c == "\\" and in_string:
                escape = True
                continue
            if not in_string:
                if c in ('"', "'"):
                    in_string = True
                    quote = c
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        return raw[start : i + 1]
            else:
                if c == quote:
                    in_string = False
        return ""

    def _parse_plan(self, raw: str) -> list[dict]:
        raw = raw.strip()
        if not raw:
            return []
        if raw.startswith("```"):
            raw = re.sub(r"^```\w*\n?", "", raw)
            raw = re.sub(r"\n?```\s*$", "", raw)
        raw = raw.strip()
        json_str = self._extract_json_object(raw)
        if not json_str:
            json_str = raw
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return []
        files = data.get("files", [])
        if not isinstance(files, list):
            return []
        return [f for f in files if isinstance(f, dict) and f.get("path") and "content" in f]

    def apply_plan(self, plan: list[dict]) -> None:
        for item in plan:
            path = item.get("path")
            content = item.get("content")
            if not path or content is None:
                continue
            fp = self._workspace / path
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content, encoding="utf-8")
