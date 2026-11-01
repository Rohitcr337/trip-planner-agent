"""
Smoke test for project skeleton (task 1.1).
Verifies that every required module path exists and is importable.
"""
import os
import pytest


REQUIRED_FILES = [
    "requirements.txt",
    ".gitignore",
    ".env.example",
    os.path.join("backend", "app", "main.py"),
    os.path.join("backend", "app", "llm.py"),
    os.path.join("backend", "app", "schemas.py"),
    os.path.join("backend", "app", "graph", "state.py"),
    os.path.join("backend", "app", "graph", "nodes.py"),
    os.path.join("backend", "app", "graph", "build.py"),
]

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def test_required_files_exist():
    missing = [f for f in REQUIRED_FILES if not os.path.exists(os.path.join(REPO_ROOT, f))]
    assert missing == [], f"Missing files: {missing}"


def test_gitignore_excludes_env():
    gitignore_path = os.path.join(REPO_ROOT, ".gitignore")
    content = open(gitignore_path).read()
    assert ".env" in content, ".gitignore must exclude .env"
    assert "cache/" in content, ".gitignore must exclude cache/"
    assert "chroma/" in content, ".gitignore must exclude chroma/"
    assert ".venv/" in content, ".gitignore must exclude .venv/"


def test_env_example_has_llm_key():
    env_example_path = os.path.join(REPO_ROOT, ".env.example")
    content = open(env_example_path).read()
    assert "LLM_API_KEY" in content, ".env.example must document LLM_API_KEY"
