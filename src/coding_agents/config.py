import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    github_token: str
    repo_owner: str
    repo_name: str
    llm_provider: str
    llm_model: str
    llm_api_key: str
    yc_folder_id: str
    yc_iam_token: str
    max_iterations: int
    workspace_path: Path

    @classmethod
    def from_env(cls) -> "Config":
        token = os.environ.get("GITHUB_TOKEN", "")
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        if "/" in repo:
            owner, name = repo.split("/", 1)
        else:
            owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
            name = repo or os.environ.get("REPO_NAME", "")
        provider = os.environ.get("LLM_PROVIDER", "openrouter").lower()
        if provider not in ("openrouter", "yandexgpt"):
            provider = "openrouter"
        api_key = os.environ.get("OPENROUTER_API_KEY", "") or os.environ.get(
            "OPENAI_API_KEY", ""
        )
        if provider == "yandexgpt":
            api_key = os.environ.get("YC_API_KEY", "")
        return cls(
            github_token=token,
            repo_owner=owner,
            repo_name=name,
            llm_provider=provider,
            llm_model=os.environ.get("LLM_MODEL", "openai/gpt-4o-mini"),
            llm_api_key=api_key,
            yc_folder_id=os.environ.get("YC_FOLDER_ID", ""),
            yc_iam_token=os.environ.get("YC_IAM_TOKEN", ""),
            max_iterations=int(os.environ.get("MAX_ITERATIONS", "5")),
            workspace_path=Path(os.environ.get("GITHUB_WORKSPACE", ".")),
        )
