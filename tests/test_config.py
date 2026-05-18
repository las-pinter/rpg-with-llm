"""Tests for the provider configuration management module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app.llm.base import ProviderConfig
from app.llm.config import ConfigError, ConfigManager

# =========================================================================
# ProviderConfig tests
# =========================================================================


class TestProviderConfig:
    """Tests for ProviderConfig serialisation and repr."""

    def test_repr_redacts_api_key(self):
        """__repr__ should show '****' when api_key is set."""
        cfg = ProviderConfig(
            base_url="http://localhost:11434",
            model="llama3.2",
            api_key="sk-abc123",
        )
        assert "****" in repr(cfg)
        assert "sk-abc123" not in repr(cfg)

    def test_repr_shows_none_when_no_api_key(self):
        """__repr__ should show None when api_key is not set."""
        cfg = ProviderConfig(
            base_url="http://localhost:11434",
            model="llama3.2",
        )
        assert "None" in repr(cfg)
        assert "****" not in repr(cfg)

    def test_to_dict_without_redaction(self):
        """to_dict() should include the real api_key."""
        cfg = ProviderConfig(
            base_url="http://localhost:11434",
            model="llama3.2",
            api_key="sk-abc123",
        )
        d = cfg.to_dict(redact_api_key=False)  # default
        assert d["api_key"] == "sk-abc123"
        assert d["base_url"] == "http://localhost:11434"
        assert d["model"] == "llama3.2"
        assert d["timeout"] == 30

    def test_to_dict_with_redaction(self):
        """to_dict(redact_api_key=True) should redact the api_key."""
        cfg = ProviderConfig(
            base_url="http://localhost:11434",
            model="llama3.2",
            api_key="sk-abc123",
        )
        d = cfg.to_dict(redact_api_key=True)
        assert d["api_key"] == "****"
        assert "sk-abc123" not in str(d)

    def test_to_dict_no_api_key(self):
        """to_dict() should still work when api_key is None."""
        cfg = ProviderConfig(
            base_url="http://localhost:11434",
            model="llama3.2",
        )
        d = cfg.to_dict(redact_api_key=True)
        assert d["api_key"] is None

    def test_from_dict(self):
        """from_dict() should reconstruct a ProviderConfig."""
        data = {
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4",
            "api_key": "sk-test",
            "timeout": 60,
        }
        cfg = ProviderConfig.from_dict(data)
        assert cfg.base_url == "https://api.openai.com/v1"
        assert cfg.model == "gpt-4"
        assert cfg.api_key == "sk-test"
        assert cfg.timeout == 60

    def test_from_dict_minimal(self):
        """from_dict() should apply defaults for missing optional fields."""
        data = {
            "base_url": "http://localhost:11434",
            "model": "llama3.2",
        }
        cfg = ProviderConfig.from_dict(data)
        assert cfg.api_key is None
        assert cfg.timeout == 30

    def test_round_trip(self):
        """to_dict() -> from_dict() should preserve all fields."""
        original = ProviderConfig(
            base_url="https://api.example.com",
            model="claude-3",
            api_key="sk-secret",
            timeout=120,
        )
        data = original.to_dict()
        restored = ProviderConfig.from_dict(data)
        assert restored == original

    def test_from_dict_missing_base_url_raises_value_error(self):
        """from_dict() should raise ValueError when base_url is missing."""
        data = {"model": "gpt-4"}
        with pytest.raises(ValueError, match="Missing required config field"):
            ProviderConfig.from_dict(data)

    def test_from_dict_missing_model_raises_value_error(self):
        """from_dict() should raise ValueError when model is missing."""
        data = {"base_url": "http://localhost:11434"}
        with pytest.raises(ValueError, match="Missing required config field"):
            ProviderConfig.from_dict(data)


# =========================================================================
# ConfigManager tests
# =========================================================================


class TestConfigManager:
    """Tests for the ConfigManager CRUD operations."""

    @pytest.fixture
    def tmp_config_dir(self) -> Path:
        """Yield a temporary directory that is cleaned up afterwards."""
        with tempfile.TemporaryDirectory() as td:
            yield Path(td)

    @pytest.fixture
    def manager(self, tmp_config_dir: Path) -> ConfigManager:
        """Return a ConfigManager pointed at the temp directory."""
        return ConfigManager(tmp_config_dir)

    # ------------------------------------------------------------------
    # get_default
    # ------------------------------------------------------------------

    def test_get_default(self):
        """get_default() should return the default Ollama config."""
        cfg = ConfigManager.get_default()
        assert cfg.base_url == "http://localhost:11434"
        assert cfg.model == "llama3.2"
        assert cfg.api_key is None
        assert cfg.timeout == 30

    # ------------------------------------------------------------------
    # save_config / get_config
    # ------------------------------------------------------------------

    def test_save_and_load_config(self, manager: ConfigManager, tmp_config_dir: Path):
        """Saved config should be retrievable via get_config()."""
        cfg = ProviderConfig(
            base_url="http://localhost:11434",
            model="mistral",
            api_key="sk-mistral",
            timeout=45,
        )
        manager.save_config(cfg, name="mistral")

        loaded = manager.get_config("mistral")
        assert loaded == cfg
        assert loaded.base_url == "http://localhost:11434"
        assert loaded.model == "mistral"
        assert loaded.api_key == "sk-mistral"
        assert loaded.timeout == 45

    def test_save_overwrites_existing(self, manager: ConfigManager):
        """Saving with the same name should overwrite the old config."""
        original = ProviderConfig(base_url="http://localhost:11434", model="llama3.2")
        manager.save_config(original, name="default")

        updated = ProviderConfig(base_url="http://localhost:11434", model="llama3.1")
        manager.save_config(updated, name="default")

        loaded = manager.get_config("default")
        assert loaded.model == "llama3.1"

    def test_get_config_not_found(self, manager: ConfigManager):
        """Getting a non-existent config should raise ConfigError."""
        with pytest.raises(ConfigError, match="not found"):
            manager.get_config("nonexistent")

    # ------------------------------------------------------------------
    # list_configs
    # ------------------------------------------------------------------

    def test_list_configs_empty(self, manager: ConfigManager):
        """list_configs() should return empty list when no configs exist."""
        assert manager.list_configs() == []

    def test_list_configs(self, manager: ConfigManager):
        """list_configs() should return sorted config names."""
        manager.save_config(
            ProviderConfig(base_url="http://localhost:11434", model="zephyr"),
            name="zephyr",
        )
        manager.save_config(
            ProviderConfig(base_url="http://localhost:11434", model="llama3.2"),
            name="default",
        )
        manager.save_config(
            ProviderConfig(base_url="http://localhost:11434", model="mistral"),
            name="mistral",
        )

        names = manager.list_configs()
        assert names == ["default", "mistral", "zephyr"]

    def test_list_after_delete(self, manager: ConfigManager):
        """list_configs() should reflect deleted configs."""
        manager.save_config(
            ProviderConfig(base_url="http://localhost:11434", model="a"),
            name="alpha",
        )
        manager.save_config(
            ProviderConfig(base_url="http://localhost:11434", model="b"),
            name="beta",
        )
        manager.delete_config("alpha")
        assert manager.list_configs() == ["beta"]

    # ------------------------------------------------------------------
    # delete_config
    # ------------------------------------------------------------------

    def test_delete_config(self, manager: ConfigManager):
        """delete_config() should remove the file."""
        manager.save_config(
            ProviderConfig(base_url="http://localhost:11434", model="test"),
            name="delete-me",
        )
        manager.delete_config("delete-me")
        assert "delete-me" not in manager.list_configs()

    def test_delete_nonexistent_config(self, manager: ConfigManager):
        """delete_config() on a missing config should raise ConfigError."""
        with pytest.raises(ConfigError, match="not found"):
            manager.delete_config("ghost")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def test_validation_empty_model(self, manager: ConfigManager):
        """Saving a config with empty model should raise ConfigError."""
        cfg = ProviderConfig(
            base_url="http://localhost:11434",
            model="",
        )
        with pytest.raises(ConfigError, match="model must not be empty"):
            manager.save_config(cfg)

    def test_validation_whitespace_model(self, manager: ConfigManager):
        """Saving a config with whitespace-only model should raise."""
        cfg = ProviderConfig(
            base_url="http://localhost:11434",
            model="   ",
        )
        with pytest.raises(ConfigError, match="model must not be empty"):
            manager.save_config(cfg)

    def test_validation_invalid_url_no_scheme(self, manager: ConfigManager):
        """Saving a config without a URL scheme should raise."""
        cfg = ProviderConfig(
            base_url="localhost:11434",
            model="llama3.2",
        )
        with pytest.raises(ConfigError, match="Invalid base URL"):
            manager.save_config(cfg)

    def test_validation_invalid_url_garbage(self, manager: ConfigManager):
        """Saving a config with a nonsense URL should raise."""
        cfg = ProviderConfig(
            base_url="not-a-url",
            model="llama3.2",
        )
        with pytest.raises(ConfigError, match="Invalid base URL"):
            manager.save_config(cfg)

    def test_validation_invalid_timeout(self, manager: ConfigManager):
        """Saving a config with a non-positive timeout should raise."""
        cfg = ProviderConfig(
            base_url="http://localhost:11434",
            model="llama3.2",
            timeout=0,
        )
        with pytest.raises(ConfigError, match="timeout must be a positive integer"):
            manager.save_config(cfg)

    def test_validation_negative_timeout(self, manager: ConfigManager):
        """Saving a config with a negative timeout should raise."""
        cfg = ProviderConfig(
            base_url="http://localhost:11434",
            model="llama3.2",
            timeout=-5,
        )
        with pytest.raises(ConfigError, match="timeout must be a positive integer"):
            manager.save_config(cfg)

    # ------------------------------------------------------------------
    # Config name validation
    # ------------------------------------------------------------------

    def test_save_config_with_empty_name(self, manager: ConfigManager):
        """save_config() with empty name should raise ConfigError."""
        cfg = ProviderConfig(base_url="http://localhost:11434", model="llama3.2")
        with pytest.raises(ConfigError, match="Config name must be non-empty"):
            manager.save_config(cfg, name="")

    def test_get_config_with_empty_name(self, manager: ConfigManager):
        """get_config() with empty name should raise ConfigError."""
        with pytest.raises(ConfigError, match="Config name must be non-empty"):
            manager.get_config(name="")

    def test_delete_config_with_empty_name(self, manager: ConfigManager):
        """delete_config() with empty name should raise ConfigError."""
        with pytest.raises(ConfigError, match="Config name must be non-empty"):
            manager.delete_config("")

    def test_config_name_with_path_traversal(self, manager: ConfigManager):
        """Config name with '../' should raise ConfigError."""
        cfg = ProviderConfig(base_url="http://localhost:11434", model="llama3.2")
        with pytest.raises(ConfigError, match="Invalid config name"):
            manager.save_config(cfg, name="../../evil")

    def test_config_name_with_slash(self, manager: ConfigManager):
        """Config name with '/' should raise ConfigError."""
        cfg = ProviderConfig(base_url="http://localhost:11434", model="llama3.2")
        with pytest.raises(ConfigError, match="Invalid config name"):
            manager.save_config(cfg, name="foo/bar")

    def test_config_name_with_dotdot(self, manager: ConfigManager):
        """Config name with '..' should raise ConfigError."""
        cfg = ProviderConfig(base_url="http://localhost:11434", model="llama3.2")
        with pytest.raises(ConfigError, match="Invalid config name"):
            manager.save_config(cfg, name="..")

    def test_config_name_too_long(self, manager: ConfigManager):
        """Config name over 200 chars should raise ConfigError."""
        cfg = ProviderConfig(base_url="http://localhost:11434", model="llama3.2")
        with pytest.raises(ConfigError, match="Config name too long"):
            manager.save_config(cfg, name="a" * 201)

    # ------------------------------------------------------------------
    # Type checking
    # ------------------------------------------------------------------

    def test_save_config_non_providerconfig(self, manager: ConfigManager):
        """save_config() with non-ProviderConfig should raise ConfigError."""
        with pytest.raises(ConfigError, match="Expected ProviderConfig, got dict"):
            manager.save_config({"base_url": "http://localhost:11434"})  # type: ignore

    # ------------------------------------------------------------------
    # get_config with corrupted data
    # ------------------------------------------------------------------

    def test_get_config_corrupted_data_missing_model(
        self, manager: ConfigManager, tmp_config_dir: Path
    ):
        """get_config() with missing model in JSON should raise ConfigError."""
        cfg = ProviderConfig(base_url="http://localhost:11434", model="llama3.2")
        manager.save_config(cfg, name="test")

        # Manually corrupt the JSON file to remove model
        json_path = tmp_config_dir / "providers" / "test.json"
        import json as _json

        data = _json.loads(json_path.read_text(encoding="utf-8"))
        del data["model"]
        json_path.write_text(_json.dumps(data), encoding="utf-8")

        with pytest.raises(ConfigError, match="Missing required config field"):
            manager.get_config("test")

    def test_get_config_corrupted_data_empty_model(
        self, manager: ConfigManager, tmp_config_dir: Path
    ):
        """get_config() with empty model in JSON should raise ConfigError."""
        cfg = ProviderConfig(base_url="http://localhost:11434", model="llama3.2")
        manager.save_config(cfg, name="test2")

        # Manually corrupt the JSON to have empty model
        json_path = tmp_config_dir / "providers" / "test2.json"
        import json as _json

        data = _json.loads(json_path.read_text(encoding="utf-8"))
        data["model"] = ""
        json_path.write_text(_json.dumps(data), encoding="utf-8")

        with pytest.raises(ConfigError, match="model must not be empty"):
            manager.get_config("test2")

    # ------------------------------------------------------------------
    # Atomic writes — no .tmp files left behind
    # ------------------------------------------------------------------

    def test_atomic_write_leaves_no_temp_files(
        self, manager: ConfigManager, tmp_config_dir: Path
    ):
        """After saving, no .tmp files should remain in the directory."""
        cfg = ProviderConfig(base_url="http://localhost:11434", model="llama3.2")
        manager.save_config(cfg, name="atomic-test")

        provider_dir = tmp_config_dir / "providers"
        tmp_files = list(provider_dir.glob("*.tmp"))
        assert tmp_files == [], f"Left-over temp files: {tmp_files}"

    def test_atomic_write_creates_valid_json(
        self, manager: ConfigManager, tmp_config_dir: Path
    ):
        """The saved JSON file should be valid and parseable."""
        cfg = ProviderConfig(
            base_url="http://localhost:11434",
            model="test-model",
            api_key="sk-test-atomic",
            timeout=99,
        )
        manager.save_config(cfg, name="atomic-json")

        json_path = tmp_config_dir / "providers" / "atomic-json.json"
        raw = json_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        assert data["base_url"] == "http://localhost:11434"
        assert data["model"] == "test-model"
        assert data["api_key"] == "sk-test-atomic"
        assert data["timeout"] == 99

    # ------------------------------------------------------------------
    # Directory creation on first save
    # ------------------------------------------------------------------

    def test_directory_created_on_first_save(self, tmp_config_dir: Path):
        """The providers directory should be created automatically on save."""
        manager = ConfigManager(tmp_config_dir)
        assert not (tmp_config_dir / "providers").exists()

        cfg = ProviderConfig(base_url="http://localhost:11434", model="llama3.2")
        manager.save_config(cfg, name="first")

        assert (tmp_config_dir / "providers").is_dir()

    def test_directory_persists_across_saves(self, tmp_config_dir: Path):
        """The providers directory should survive multiple saves."""
        manager = ConfigManager(tmp_config_dir)
        cfg = ProviderConfig(base_url="http://localhost:11434", model="llama3.2")
        manager.save_config(cfg, name="first")
        manager.save_config(cfg, name="second")
        manager.save_config(cfg, name="third")

        provider_dir = tmp_config_dir / "providers"
        assert provider_dir.is_dir()
        assert len(list(provider_dir.iterdir())) == 3

    # ------------------------------------------------------------------
    # Config file location
    # ------------------------------------------------------------------

    def test_config_stored_as_json_in_providers_dir(
        self, manager: ConfigManager, tmp_config_dir: Path
    ):
        """Config should be stored at {config_dir}/providers/{name}.json."""
        cfg = ProviderConfig(base_url="http://localhost:11434", model="llama3.2")
        manager.save_config(cfg, name="ollama")

        expected = tmp_config_dir / "providers" / "ollama.json"
        assert expected.is_file()

    def test_multiple_configs_separate_files(
        self, manager: ConfigManager, tmp_config_dir: Path
    ):
        """Multiple configs should each get their own JSON file."""
        for name in ("alpha", "beta", "gamma"):
            manager.save_config(
                ProviderConfig(base_url="http://localhost:11434", model=name),
                name=name,
            )

        provider_dir = tmp_config_dir / "providers"
        files = sorted(f.name for f in provider_dir.iterdir())
        assert files == ["alpha.json", "beta.json", "gamma.json"]

    # ------------------------------------------------------------------
    # Error messages do not leak api_key
    # ------------------------------------------------------------------

    def test_error_message_does_not_contain_api_key(self, manager: ConfigManager):
        """Validation errors should never include the api_key value."""
        cfg = ProviderConfig(
            base_url="not-a-valid-url",
            model="llama3.2",
            api_key="super-secret-key-12345",
        )
        try:
            manager.save_config(cfg)
        except ConfigError as e:
            msg = str(e).lower()
            assert "super-secret-key-12345" not in msg
            assert "****" not in msg

    def test_get_default_includes_provider_type(self):
        """get_default() should include provider_type='ollama'."""
        cfg = ConfigManager.get_default()
        assert cfg.provider_type == "ollama"


class TestCreateProvider:
    """Tests for the create_provider factory function."""

    def test_create_ollama_provider(self):
        """create_provider should create an OllamaProvider."""
        from app.llm.config import create_provider
        from app.llm.ollama import OllamaProvider

        config = ProviderConfig(
            base_url="http://localhost:11434",
            model="llama3.2",
            provider_type="ollama",
        )
        provider = create_provider(config)
        assert isinstance(provider, OllamaProvider)
        assert provider.base_url == "http://localhost:11434"
        assert provider.model == "llama3.2"

    def test_create_groq_provider(self):
        """create_provider should create a GroqProvider."""
        from app.llm.config import create_provider
        from app.llm.groq import GroqProvider

        config = ProviderConfig(
            base_url="https://api.groq.com/openai",
            model="llama3-70b-8192",
            provider_type="groq",
            api_key="gsk-test",
        )
        provider = create_provider(config)
        assert isinstance(provider, GroqProvider)

    def test_create_openrouter_provider(self):
        """create_provider should create an OpenRouterProvider."""
        from app.llm.config import create_provider
        from app.llm.openrouter import OpenRouterProvider

        config = ProviderConfig(
            base_url="https://openrouter.ai/api",
            model="mistralai/mistral-7b-instruct:free",
            provider_type="openrouter",
            api_key="sk-or-v1-test",
        )
        provider = create_provider(config)
        assert isinstance(provider, OpenRouterProvider)

    def test_create_unsloth_provider(self):
        """create_provider should create an UnslothProvider."""
        from app.llm.config import create_provider
        from app.llm.unsloth import UnslothProvider

        config = ProviderConfig(
            base_url="http://localhost:8888",
            model="unsloth/Llama-3.2-1B-Instruct",
            provider_type="unsloth",
        )
        provider = create_provider(config)
        assert isinstance(provider, UnslothProvider)

    def test_create_llamacpp_provider(self):
        """create_provider should create a LlamacppProvider."""
        from app.llm.config import create_provider
        from app.llm.llamacpp import LlamacppProvider

        config = ProviderConfig(
            base_url="http://localhost:8080",
            model="default",
            provider_type="llamacpp",
        )
        provider = create_provider(config)
        assert isinstance(provider, LlamacppProvider)

    def test_create_provider_unknown_type_raises_error(self):
        """create_provider should raise ConfigError for unknown types."""
        from app.llm.config import ConfigError, create_provider

        config = ProviderConfig(
            base_url="http://localhost:11434",
            model="llama3.2",
            provider_type="nonexistent",
        )
        with pytest.raises(ConfigError) as excinfo:
            create_provider(config)
        assert "Unknown provider type" in str(excinfo.value)

    def test_create_provider_with_timeout(self):
        """create_provider should pass timeout to the provider."""
        from app.llm.config import create_provider

        config = ProviderConfig(
            base_url="http://localhost:11434",
            model="llama3.2",
            provider_type="ollama",
            timeout=120,
        )
        provider = create_provider(config)
        assert provider.timeout == 120

    def test_create_provider_minimal_config(self):
        """create_provider should work with minimal config (just provider_type)."""
        from app.llm.config import create_provider
        from app.llm.ollama import OllamaProvider

        config = ProviderConfig(
            base_url="http://localhost:11434",
            model="test-model",
            provider_type="ollama",
        )
        provider = create_provider(config)
        assert isinstance(provider, OllamaProvider)
        assert provider.api_key is None
        assert provider.timeout == 30
