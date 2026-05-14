"""
Provider Configuration Management.

Stores, retrieves, and manages LLM provider configurations as JSON files.
Configs are stored one per file under ``{config_dir}/providers/{name}.json``.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from app.llm.base import ProviderConfig

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ConfigError(Exception):
    """Raised when a configuration operation fails."""


# ---------------------------------------------------------------------------
# ConfigManager
# ---------------------------------------------------------------------------

class ConfigManager:
    """Manages named provider configurations stored as JSON files.

    Each named config is a single JSON file under
    ``<config_dir>/providers/<name>.json``.

    Parameters
    ----------
    config_dir : str | Path
        Top-level directory under which the ``providers/`` subdirectory
        will be created.
    """

    def __init__(self, config_dir: str | Path) -> None:
        self._config_dir = Path(config_dir)
        self._providers_dir = self._config_dir / "providers"

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_name(name: str) -> None:
        """Validate a config name for safety and correctness.

        Raises
        ------
        ConfigError
            If the name is empty, contains path separators, or is
            too long.
        """
        if not name or not name.strip():
            raise ConfigError("Config name must be non-empty")
        if "/" in name or "\\" in name or ".." in name:
            raise ConfigError(f"Invalid config name: '{name}'")
        if len(name) > 200:
            raise ConfigError("Config name too long (max 200 chars)")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_config(self, name: str = "default") -> ProviderConfig:
        """Load and return a named provider configuration.

        Parameters
        ----------
        name : str
            Name of the config to load (without ``.json`` suffix).

        Returns
        -------
        ProviderConfig
            The deserialised configuration.

        Raises
        ------
        ConfigError
            If the config file does not exist or cannot be read.
        """
        self._validate_name(name)
        path = self._providers_dir / f"{name}.json"
        if not path.exists():
            raise ConfigError(
                f"Provider config '{name}' not found at {path}"
            )
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ConfigError(
                f"Failed to read provider config '{name}': {exc}"
            ) from exc
        try:
            config = ProviderConfig.from_dict(data)
        except ValueError as e:
            raise ConfigError(str(e)) from e
        self._validate(config)
        return config

    def save_config(
        self, config: ProviderConfig, name: str = "default"
    ) -> None:
        """Save (create or update) a named provider configuration.

        Writes atomically: the JSON is first written to a temporary file
        in the same directory, then renamed into place.

        Parameters
        ----------
        config : ProviderConfig
            The configuration to persist.
        name : str
            Name of the config (becomes ``<name>.json``).

        Raises
        ------
        ConfigError
            If validation fails or the file cannot be written.
        """
        if not isinstance(config, ProviderConfig):
            raise ConfigError(
                f"Expected ProviderConfig, got {type(config).__name__}"
            )
        self._validate_name(name)
        self._validate(config)
        path = self._providers_dir / f"{name}.json"
        data = config.to_dict(redact_api_key=False)
        content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        try:
            self._atomic_write(path, content)
        except OSError as exc:
            raise ConfigError(
                f"Failed to save provider config '{name}': {exc}"
            ) from exc

    def list_configs(self) -> list[str]:
        """Return sorted list of all saved config names."""
        if not self._providers_dir.exists():
            return []
        return sorted(
            p.stem
            for p in self._providers_dir.iterdir()
            if p.suffix == ".json"
        )

    def delete_config(self, name: str) -> None:
        """Delete a named provider configuration.

        Parameters
        ----------
        name : str
            Name of the config to delete.

        Raises
        ------
        ConfigError
            If the config does not exist or cannot be deleted.
        """
        self._validate_name(name)
        path = self._providers_dir / f"{name}.json"
        if not path.exists():
            raise ConfigError(
                f"Provider config '{name}' not found at {path}"
            )
        try:
            path.unlink()
        except OSError as exc:
            raise ConfigError(
                f"Failed to delete provider config '{name}': {exc}"
            ) from exc

    @staticmethod
    def get_default() -> ProviderConfig:
        """Return the default Ollama provider configuration.

        Returns
        -------
        ProviderConfig
            ``base_url=http://localhost:11434``, ``model=llama3.2``.
        """
        return ProviderConfig(
            base_url="http://localhost:11434",
            model="llama3.2",
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _validate(config: ProviderConfig) -> None:
        """Validate a configuration before saving.

        Raises
        ------
        ConfigError
            If any field is invalid.  API keys are never included in
            error messages.
        """
        if not config.model or not config.model.strip():
            raise ConfigError("model must not be empty")

        parsed = urlparse(config.base_url)
        if not parsed.scheme or not parsed.netloc:
            raise ConfigError(
                f"Invalid base URL: '{config.base_url}' — "
                "must include a scheme and host "
                "(e.g. http://localhost:11434)"
            )

        if not isinstance(config.timeout, int) or config.timeout < 1:
            raise ConfigError(
                "timeout must be a positive integer"
            )

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        """Atomically write *content* to *path*.

        Creates parent directories as needed.  Writes to a temporary
        file in the same directory first, then renames — this prevents
        partial/corrupt files on crash.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=path.parent, suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, path)
        except BaseException:
            # Clean up the temp file on any failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
