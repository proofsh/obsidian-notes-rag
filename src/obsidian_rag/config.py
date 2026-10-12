"""Configuration management for obsidian-notes-rag."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found]

import tomli_w
from platformdirs import user_config_dir, user_data_dir
from .indexer import IndexerConfig


APP_NAME = "obsidian-notes-rag"


def resolve_path_case(path: str) -> str:
    """Resolve a path to its correct case on case-insensitive filesystems.

    On macOS, the filesystem is case-insensitive but case-preserving.
    Watchdog requires the exact case to detect file changes properly.
    """
    import sys

    p = Path(path).expanduser()
    if not p.exists():
        return path

    # On macOS, use the real path which preserves correct case
    if sys.platform == "darwin":
        import subprocess
        try:
            # Use realpath command which returns the canonical path with correct case
            result = subprocess.run(
                ["realpath", str(p)],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    return str(p.resolve())


def get_config_dir() -> Path:
    """Get the configuration directory (cross-platform)."""
    # appauthor=False: platformdirs>=4 defaults appauthor to appname on
    # Windows, which would double the segment
    # (".../obsidian-notes-rag/obsidian-notes-rag"). roaming=True keeps the
    # documented %APPDATA% location on Windows.
    return Path(user_config_dir(APP_NAME, appauthor=False, roaming=True))


def get_data_dir() -> Path:
    """Get the data directory (cross-platform)."""
    return Path(user_data_dir(APP_NAME, appauthor=False))


def _legacy_config_path() -> Path:
    """Config path used before the platformdirs-4 double-segment fix.

    platformdirs>=4 on Windows returned
    ".../obsidian-notes-rag/obsidian-notes-rag", so configs written by
    `setup` may live there. Used as a read fallback only.
    """
    return Path(user_config_dir(APP_NAME)) / "config.toml"


def get_config_path() -> Path:
    """Get the path to the config file."""
    return get_config_dir() / "config.toml"


@dataclass
class Config:
    """Application configuration."""

    # Core settings
    provider: str = "openai"
    vault_path: Optional[str] = None
    data_path: Optional[str] = None

    # OpenAI settings
    openai_api_key: Optional[str] = None

    # Ollama settings
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "nomic-embed-text"
    ollama_api_key: Optional[str] = None  # Bearer token for protected Ollama instances

    # LM Studio settings
    lmstudio_url: str = "http://localhost:1234"
    lmstudio_model: str = "text-embedding-nomic-embed-text-v1.5"
    lmstudio_api_key: Optional[str] = None  # Bearer token for protected LM Studio instances

    # llama.cpp settings (llama-server, OpenAI-compatible /v1/embeddings)
    # Default port is 9931 since llama.cpp b11521 (was 8080).
    # Supports both single-model mode and router mode (model-name routing
    # with on-demand loading). See LlamaCppEmbedder in indexer.py.
    llamacpp_url: str = "http://localhost:9931"
    llamacpp_model: str = "default"
    llamacpp_api_key: Optional[str] = None  # Bearer token when started with --api-key

    # OpenAI model (optional override)
    openai_model: str = "text-embedding-3-small"
    indexer: IndexerConfig = field(default_factory=IndexerConfig)

    def get_data_path(self) -> str:
        """Get the data path, using default if not set."""
        return self.data_path or str(get_data_dir())

    def get_openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key from config or environment."""
        return self.openai_api_key or os.environ.get("OPENAI_API_KEY")

    def get_ollama_api_key(self) -> Optional[str]:
        """Get Ollama Bearer token from config or environment."""
        return self.ollama_api_key or os.environ.get("OBSIDIAN_RAG_OLLAMA_API_KEY")

    def get_lmstudio_api_key(self) -> Optional[str]:
        """Get LM Studio Bearer token from config or environment."""
        return self.lmstudio_api_key or os.environ.get("OBSIDIAN_RAG_LMSTUDIO_API_KEY")

    def get_llamacpp_api_key(self) -> Optional[str]:
        """Get llama.cpp Bearer token from config or environment."""
        return self.llamacpp_api_key or os.environ.get("OBSIDIAN_RAG_LLAMACPP_API_KEY")


def load_config() -> Config:
    """Load configuration from file with environment variable overrides.

    Priority (highest to lowest):
    1. Environment variables
    2. Config file
    3. Defaults
    """
    config = Config()

    # Load from config file if it exists
    config_path = get_config_path()
    if not config_path.exists():
        # Fall back to the pre-fix doubled-segment location (Windows +
        # platformdirs>=4) so existing setups keep working.
        legacy_path = _legacy_config_path()
        if legacy_path != config_path and legacy_path.exists():
            config_path = legacy_path
    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)

            config.provider = data.get("provider", config.provider)
            vault_path = data.get("vault_path", config.vault_path)
            if vault_path:
                config.vault_path = resolve_path_case(vault_path)
            config.data_path = data.get("data_path", config.data_path)

            # OpenAI settings
            if "openai" in data:
                config.openai_api_key = data["openai"].get("api_key")
                config.openai_model = data["openai"].get("model", config.openai_model)

            # Ollama settings
            if "ollama" in data:
                config.ollama_url = data["ollama"].get("url", config.ollama_url)
                config.ollama_model = data["ollama"].get("model", config.ollama_model)
                config.ollama_api_key = data["ollama"].get("api_key", config.ollama_api_key)

            # LM Studio settings
            if "lmstudio" in data:
                config.lmstudio_url = data["lmstudio"].get("url", config.lmstudio_url)
                config.lmstudio_model = data["lmstudio"].get("model", config.lmstudio_model)
                config.lmstudio_api_key = data["lmstudio"].get("api_key", config.lmstudio_api_key)

            # llama.cpp settings
            if "llamacpp" in data:
                config.llamacpp_url = data["llamacpp"].get("url", config.llamacpp_url)
                config.llamacpp_model = data["llamacpp"].get("model", config.llamacpp_model)
                config.llamacpp_api_key = data["llamacpp"].get("api_key", config.llamacpp_api_key)

            # Indexer settings
            if "indexer" in data:
                config.indexer = IndexerConfig.from_dict(data["indexer"])

        except Exception:
            pass  # Use defaults if config file is invalid

    # Environment variable overrides
    if os.environ.get("OBSIDIAN_RAG_PROVIDER"):
        config.provider = os.environ["OBSIDIAN_RAG_PROVIDER"]
    if os.environ.get("OBSIDIAN_RAG_VAULT"):
        config.vault_path = resolve_path_case(os.environ["OBSIDIAN_RAG_VAULT"])
    if os.environ.get("OBSIDIAN_RAG_DATA"):
        config.data_path = os.environ["OBSIDIAN_RAG_DATA"]
    if os.environ.get("OBSIDIAN_RAG_OLLAMA_URL"):
        config.ollama_url = os.environ["OBSIDIAN_RAG_OLLAMA_URL"]
    if os.environ.get("OBSIDIAN_RAG_LMSTUDIO_URL"):
        config.lmstudio_url = os.environ["OBSIDIAN_RAG_LMSTUDIO_URL"]
    if os.environ.get("OBSIDIAN_RAG_LLAMACPP_URL"):
        config.llamacpp_url = os.environ["OBSIDIAN_RAG_LLAMACPP_URL"]
    # Bearer token overrides for local providers
    if os.environ.get("OBSIDIAN_RAG_OLLAMA_API_KEY"):
        config.ollama_api_key = os.environ["OBSIDIAN_RAG_OLLAMA_API_KEY"]
    if os.environ.get("OBSIDIAN_RAG_LMSTUDIO_API_KEY"):
        config.lmstudio_api_key = os.environ["OBSIDIAN_RAG_LMSTUDIO_API_KEY"]
    if os.environ.get("OBSIDIAN_RAG_LLAMACPP_API_KEY"):
        config.llamacpp_api_key = os.environ["OBSIDIAN_RAG_LLAMACPP_API_KEY"]
    if os.environ.get("OBSIDIAN_RAG_MODEL"):
        if config.provider == "ollama":
            config.ollama_model = os.environ["OBSIDIAN_RAG_MODEL"]
        elif config.provider == "lmstudio":
            config.lmstudio_model = os.environ["OBSIDIAN_RAG_MODEL"]
        elif config.provider == "llamacpp":
            config.llamacpp_model = os.environ["OBSIDIAN_RAG_MODEL"]
        else:
            config.openai_model = os.environ["OBSIDIAN_RAG_MODEL"]

    return config


def save_config(config: Config) -> Path:
    """Save configuration to file.

    Returns:
        Path to the saved config file.
    """
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data: dict = {
        "provider": config.provider,
    }

    if config.vault_path:
        data["vault_path"] = resolve_path_case(config.vault_path)
    if config.data_path:
        data["data_path"] = config.data_path

    # OpenAI settings
    if config.provider == "openai" or config.openai_api_key:
        openai_section: dict = {}
        if config.openai_api_key:
            openai_section["api_key"] = config.openai_api_key
        if config.openai_model != "text-embedding-3-small":
            openai_section["model"] = config.openai_model
        if openai_section:
            data["openai"] = openai_section

    # Ollama settings
    if config.provider == "ollama":
        ollama_section: dict = {}
        if config.ollama_url != "http://localhost:11434":
            ollama_section["url"] = config.ollama_url
        if config.ollama_model != "nomic-embed-text":
            ollama_section["model"] = config.ollama_model
        if config.ollama_api_key:
            ollama_section["api_key"] = config.ollama_api_key
        if ollama_section:
            data["ollama"] = ollama_section

    # LM Studio settings
    if config.provider == "lmstudio":
        lmstudio_section: dict = {}
        if config.lmstudio_url != "http://localhost:1234":
            lmstudio_section["url"] = config.lmstudio_url
        if config.lmstudio_model != "text-embedding-nomic-embed-text-v1.5":
            lmstudio_section["model"] = config.lmstudio_model
        if config.lmstudio_api_key:
            lmstudio_section["api_key"] = config.lmstudio_api_key
        if lmstudio_section:
            data["lmstudio"] = lmstudio_section

    # llama.cpp settings
    if config.provider == "llamacpp":
        llamacpp_section: dict = {}
        if config.llamacpp_url != "http://localhost:9931":
            llamacpp_section["url"] = config.llamacpp_url
        if config.llamacpp_model != "default":
            llamacpp_section["model"] = config.llamacpp_model
        if config.llamacpp_api_key:
            llamacpp_section["api_key"] = config.llamacpp_api_key
        if llamacpp_section:
            data["llamacpp"] = llamacpp_section

    # Indexer settings — write if preset is non-default OR any overrides are present
    indexer_dict = config.indexer.to_dict()
    if indexer_dict.get("preset", "default") != "default" or len(indexer_dict) > 1:
        data["indexer"] = indexer_dict

    with open(config_path, "wb") as f:
        tomli_w.dump(data, f)

    return config_path
