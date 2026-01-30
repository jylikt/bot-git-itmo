from coding_agents.github_client import GitHubClient
from coding_agents.llm.base import LLMClientProtocol


REVIEW_SYSTEM = """You are an AI code reviewer. Given:
1) The original issue description
2) The PR diff and changed files
3) CI/CD job results (if any)

Produce a structured review:
- Summary: brief verdict (APPROVED / CHANGES_REQUESTED)
- Compliance: does the implementation match the issue requirements?
- Code quality: style, potential bugs. Use standards that match the file types in the PR: for Python mention PEP 8 if relevant; for HTML/CSS/JS mention markup, semantics, accessibility, or common front-end practices; do not mention PEP 8 for non-Python files.
- CI: any failing jobs or concerns

If CHANGES_REQUESTED, list specific file/line or file and what to fix. Be concise.
Output in markdown. End with a line: VERDICT: APPROVED or VERDICT: CHANGES_REQUESTED
Always answer in Russian."""


class ReviewerAgent:
    def __init__(self, llm: LLMClientProtocol, github: GitHubClient):
        self._llm = llm
        self._github = github

    def review(
        self,
        issue_body: str,
        issue_title: str,
        pr_diff: str,
        pr_files: list[dict],
        ci_summary: str,
    ) -> str:
        files_text = "\n".join(
            f"### {f.get('filename', '')}\n```\n{f.get('patch', '')}\n```"
            for f in pr_files
        )
        user = f"""Issue: {issue_title}\n{issue_body}\n\n---\nPR diff:\n{pr_diff}\n\n---\nFiles:\n{files_text}\n\n---\nCI summary:\n{ci_summary}"""
        return self._llm.chat(
            [
                {"role": "system", "content": REVIEW_SYSTEM},
                {"role": "user", "content": user},
            ]
        )

    def post_review_to_pr(self, pr_number: int, review_body: str) -> None:
        self._github.add_pr_comment(pr_number, review_body)
        if "CHANGES_REQUESTED" in review_body.upper():
            try:
                self._github.add_pr_label(pr_number, "agent-fix-requested")
            except Exception:
                pass
