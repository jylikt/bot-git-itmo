import os
from pathlib import Path

import pytest

from coding_agents.config import Config


def test_config_from_env_parses_github_repository(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tk")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo-name")
    monkeypatch.setenv("OPENROUTER_API_KEY", "key")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    cfg = Config.from_env()
    assert cfg.repo_owner == "owner"
    assert cfg.repo_name == "repo-name"
    assert cfg.llm_provider == "openrouter"
    assert cfg.llm_api_key == "key"


def test_config_from_env_defaults_workspace(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tk")
    monkeypatch.setenv("GITHUB_REPOSITORY", "a/b")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.delenv("GITHUB_WORKSPACE", raising=False)
    cfg = Config.from_env()
    assert cfg.workspace_path == Path(".")


def test_config_from_env_yandexgpt_uses_yc_keys(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tk")
    monkeypatch.setenv("GITHUB_REPOSITORY", "a/b")
    monkeypatch.setenv("LLM_PROVIDER", "yandexgpt")
    monkeypatch.setenv("YC_FOLDER_ID", "folder1")
    monkeypatch.setenv("YC_API_KEY", "yc-key")
    cfg = Config.from_env()
    assert cfg.llm_provider == "yandexgpt"
    assert cfg.yc_folder_id == "folder1"
    assert cfg.llm_api_key == "yc-key"
