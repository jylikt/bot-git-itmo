import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from coding_agents.code_agent import CodeAgent


@pytest.fixture
def llm_mock():
    return MagicMock()


@pytest.fixture
def github_mock():
    return MagicMock()


@pytest.fixture
def workspace(tmp_path):
    return tmp_path


@pytest.fixture
def agent(llm_mock, github_mock, workspace):
    return CodeAgent(llm_mock, github_mock, workspace)


def test_parse_plan_returns_files_list(agent):
    raw = '{"files": [{"path": "a.py", "content": "x=1"}]}'
    plan = agent._parse_plan(raw)
    assert len(plan) == 1
    assert plan[0]["path"] == "a.py"
    assert plan[0]["content"] == "x=1"


def test_parse_plan_strips_markdown(agent):
    raw = '```json\n{"files": [{"path": "b.py", "content": "y=2"}]}\n```'
    plan = agent._parse_plan(raw)
    assert len(plan) == 1
    assert plan[0]["path"] == "b.py"


def test_apply_plan_creates_file(agent):
    plan = [{"path": "subdir/foo.py", "content": "print(1)"}]
    agent.apply_plan(plan)
    p = agent._workspace / "subdir" / "foo.py"
    assert p.exists()
    assert p.read_text() == "print(1)"
