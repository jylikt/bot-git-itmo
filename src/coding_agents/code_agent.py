import base64
import json
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel

from coding_agents.github_client import GitHubClient
from coding_agents.llm.base import LLMClientProtocol

if TYPE_CHECKING:
    from coding_agents.config import Config


class FileEdit(BaseModel):
    path: str
    content: str


class Plan(BaseModel):
    files: list[FileEdit]


PLAN_SYSTEM = """You are a coding agent. You receive:
1) The exact text of a GitHub Issue (title and body) — this is the task to implement.
2) Optionally "Current repo files" — existing file paths and their content. You MUST use this to modify existing files correctly; output the full updated content for any file you change.

Your task: implement what the issue asks for. If the issue describes changes to existing files, include those files in your output with the full new content. Do not leave out files that need to be updated.

Output a single JSON object only, no markdown. Encode file content in base64 so the JSON stays valid:
{"files": [{"path": "relative/path/to/file", "content_base64": "<base64 only>"}]}
- "content_base64": MUST contain ONLY base64 characters (A-Z, a-z, 0-9, +, /, =). No spaces, no newlines, no quotes, no other text. One continuous string. Encode the ENTIRE file (UTF-8) as base64.
- "path": relative to repo root. Output ONLY this JSON, no markdown."""

FIX_SYSTEM = """You are a coding agent. Given an issue description, current PR diff, and reviewer feedback,
you produce a JSON plan of code changes to address the feedback.
Output ONLY valid JSON. Encode file content in base64 to avoid escaping issues:
{"files": [{"path": "relative/path", "content_base64": "<base64-encoded UTF-8 content>"}]}
Paths relative to repo root. No "content" field — use content_base64 only. No comments, PEP 8."""

PLAN_SYSTEM_INSTRUCTOR = """You are a coding agent. You receive a GitHub Issue (title and body) and optionally current repo files. Implement what the issue asks. For each file you change, output its path (relative to repo root) and the full new file content. Provide complete file content, not a patch."""

FIX_SYSTEM_INSTRUCTOR = """You are a coding agent. Given an issue, PR diff, and reviewer feedback, produce file changes to address the feedback. For each changed file output path (relative to repo root) and full new file content. Complete content only, PEP 8 for Python."""


class CodeAgent:
    def __init__(
        self,
        llm: LLMClientProtocol,
        github: GitHubClient,
        workspace: Path,
        config: Optional["Config"] = None,
    ):
        self._llm = llm
        self._github = github
        self._workspace = workspace
        self._config = config

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

    def _plan_via_instructor(
        self, system: str, user: str
    ) -> Optional[list[dict]]:
        if not self._config or self._config.llm_provider != "openrouter":
            return None
        try:
            import instructor
        except ImportError:
            return None
        if not self._config.llm_api_key:
            return None
        try:
            client = instructor.from_provider(
                self._config.llm_model,
                base_url="https://openrouter.ai/api/v1",
                api_key=self._config.llm_api_key,
                async_client=False,
            )
            plan = client.create(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_model=Plan,
            )
            if not plan or not plan.files:
                return None
            return [
                {"path": f.path, "content": f.content}
                for f in plan.files
                if f.path and f.content is not None
            ]
        except Exception:
            return None

    def plan_changes(self, issue_body: str, issue_title: str) -> list[dict]:
        user = f"Issue title: {issue_title}\n\nIssue body:\n{issue_body}"
        repo_ctx = self._repo_context()
        if repo_ctx:
            user += f"\n\n{repo_ctx}"
        plan = self._plan_via_instructor(PLAN_SYSTEM_INSTRUCTOR, user)
        if plan:
            return plan
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
        user = f"""Issue: {issue_title}\n{issue_body}\n\nPR diff:\n{diff}\n\nReviewer feedback:\n{feedback}\n\nProduce file changes to fix the feedback."""
        plan = self._plan_via_instructor(FIX_SYSTEM_INSTRUCTOR, user)
        if plan:
            return plan
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

    def _repair_content_base64_fragments(self, raw: str) -> str:
        while re.search(
            r'"content_base64"\s*:\s*"[A-Za-z0-9+/=]+"\s*:\s*"', raw
        ):
            raw = re.sub(
                r'"content_base64"\s*:\s*"([A-Za-z0-9+/=]+)"\s*:\s*"([A-Za-z0-9+/=]+)"',
                r'"content_base64":"\1\2"',
                raw,
                count=1,
            )
        return raw

    def _repair_newlines_in_base64_value(self, raw: str) -> str:
        match = re.search(
            r'"content_base64"\s*:\s*"(.*?)"\s*[\}\],]',
            raw,
            re.DOTALL,
        )
        if not match:
            return raw
        value = match.group(1).replace("\n", "").replace("\r", "")
        start, end = match.start(1), match.end(1)
        return raw[:start] + value + raw[end:]

    def _repair_content_base64_extract_pure_b64(self, raw: str) -> str:
        needle = '"content_base64"'
        pos = raw.find(needle)
        if pos == -1:
            return raw
        value_start = raw.find('"', pos + len(needle)) + 1
        if value_start <= pos:
            return raw
        b64_match = re.match(r"[A-Za-z0-9+/=]+", raw[value_start:])
        if not b64_match:
            return raw
        b64 = b64_match.group(0)
        end_match = re.search(r'"\s*[\}\],]', raw[value_start:])
        if not end_match:
            value_end = len(raw)
        else:
            value_end = value_start + end_match.start()
        return raw[:value_start] + b64 + raw[value_end:]

    def _parse_plan(self, raw: str) -> list[dict]:
        raw = raw.strip()
        if not raw:
            print("LLM raw response (empty):", repr(raw), file=sys.stderr)
            return []
        if raw.startswith("```"):
            raw = re.sub(r"^```\w*\n?", "", raw)
            raw = re.sub(r"\n?```\s*$", "", raw)
        raw = raw.strip()
        raw = re.sub(r"\\\r?\n", "", raw)
        raw = self._repair_content_base64_fragments(raw)
        raw = self._repair_newlines_in_base64_value(raw)
        json_str = self._extract_json_object(raw)
        if not json_str:
            json_str = raw
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            json_str = self._repair_content_base64_extract_pure_b64(json_str or raw)
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                print("LLM raw response (JSON decode error):", e, file=sys.stderr)
                print("First 2500 chars:", (json_str or raw)[:2500], file=sys.stderr)
                return []
        files = data.get("files", [])
        if not isinstance(files, list):
            print("LLM raw response (files not a list):", raw[:2500], file=sys.stderr)
            return []
        result = []
        for f in files:
            if not isinstance(f, dict) or not f.get("path"):
                continue
            content = None
            if "content_base64" in f:
                b64 = (f["content_base64"] or "").strip()
                content = None
                for extra in ("", "=", "==", "==="):
                    try:
                        content = base64.b64decode(b64 + extra).decode("utf-8")
                        break
                    except Exception:
                        continue
                if content is None:
                    print(
                        "content_base64 decode failed (tried with 0,1,2 padding) | first 80 chars:",
                        repr(b64[:80]),
                        file=sys.stderr,
                    )
                    continue
            elif "content" in f:
                content = f["content"]
            if content is not None:
                result.append({"path": f["path"], "content": content})
        if not result:
            print("LLM raw response (no valid file entries):", raw[:2500], file=sys.stderr)
            return []
        return result

    def apply_plan(self, plan: list[dict]) -> None:
        for item in plan:
            path = item.get("path")
            content = item.get("content")
            if not path or content is None:
                continue
            fp = self._workspace / path
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content, encoding="utf-8")
