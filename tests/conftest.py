"""Shared pytest fixtures."""

import os

import pytest


@pytest.fixture(autouse=True)
def isolate_user_config(tmp_path_factory, monkeypatch):
    """Keep tests independent of the developer's real config and environment.

    Without this, CLI tests read ~/.config/obsidian-notes-rag/config.toml and
    OBSIDIAN_RAG_* variables, so they pass on a configured machine and fail in CI.
    """
    config_path = tmp_path_factory.mktemp("config") / "config.toml"
    monkeypatch.setattr("obsidian_rag.config.get_config_path", lambda: config_path)
    monkeypatch.setattr("obsidian_rag.cli.get_config_path", lambda: config_path)
    for name in list(os.environ):
        if name.startswith("OBSIDIAN_RAG_"):
            monkeypatch.delenv(name)
