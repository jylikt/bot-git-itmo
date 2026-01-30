from github import Github
from github.PullRequest import PullRequest
from github.Repository import Repository


class GitHubClient:
    def __init__(self, token: str, owner: str, repo_name: str):
        self._gh = Github(token)
        self._owner = owner
        self._repo_name = repo_name
        self._repo: Repository | None = None

    @property
    def repo(self) -> Repository:
        if self._repo is None:
            self._repo = self._gh.get_repo(f"{self._owner}/{self._repo_name}")
        return self._repo

    def get_issue_body(self, issue_number: int) -> str:
        issue = self.repo.get_issue(issue_number)
        return issue.body or ""

    def get_issue_title(self, issue_number: int) -> str:
        issue = self.repo.get_issue(issue_number)
        return issue.title or ""

    def get_pr_by_number(self, pr_number: int) -> PullRequest:
        return self.repo.get_pull(pr_number)

    def get_pr_for_issue(self, issue_number: int) -> PullRequest | None:
        pulls = self.repo.get_pulls(state="open", head=f"{self._owner}:agent-issue-{issue_number}")
        for pr in pulls:
            return pr
        return None

    def get_pr_diff(self, pr_number: int) -> str:
        pr = self.get_pr_by_number(pr_number)
        files = pr.get_files()
        parts = []
        for f in files:
            if f.patch:
                parts.append(f"--- a/{f.filename}\n+++ b/{f.filename}\n{f.patch}")
        return "\n".join(parts)

    def get_pr_files(self, pr_number: int) -> list[dict]:
        pr = self.get_pr_by_number(pr_number)
        return [{"filename": f.filename, "patch": f.patch or ""} for f in pr.get_files()]

    def get_pr_review_comments(self, pr_number: int) -> list[dict]:
        pr = self.get_pr_by_number(pr_number)
        return [
            {"body": c.body, "path": c.path, "line": c.line}
            for c in pr.get_review_comments()
        ]

    def get_pr_comments(self, pr_number: int) -> list[dict]:
        pr = self.get_pr_by_number(pr_number)
        return [{"body": c.body, "user": c.user.login} for c in pr.get_issue_comments()]

    def create_pr(
        self,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> PullRequest:
        return self.repo.create_pull(title=title, body=body, head=head, base=base)

    def add_pr_comment(self, pr_number: int, body: str) -> None:
        pr = self.get_pr_by_number(pr_number)
        pr.create_issue_comment(body)

    def add_pr_label(self, pr_number: int, label: str) -> None:
        pr = self.get_pr_by_number(pr_number)
        pr.add_to_labels(label)

    def create_review(
        self,
        pr_number: int,
        body: str,
        event: str = "COMMENT",
    ) -> None:
        pr = self.get_pr_by_number(pr_number)
        pr.create_review(body=body, event=event)
