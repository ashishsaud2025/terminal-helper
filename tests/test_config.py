import os
from pathlib import Path

from th import config


def _cfg_defaults(tmp_path):
    return config.Config(
        data_dir=Path(os.environ.get("TH_DATA_DIR", str(Path.home() / ".local" / "share" / "th"))),
        config_path=tmp_path / "config.toml",
    )


def test_missing_file_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.delenv("TH_CONFIG_PATH", raising=False)
    p = tmp_path / "missing.toml"
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    cfg = config.load_config(p)
    assert cfg.llm_enabled is True
    assert cfg.llm_backend == "ollama"
    assert cfg.llm_model == "qwen3:4b"
    assert cfg.llm_ollama_url == "http://127.0.0.1:11434"
    assert cfg.llm_timeout_s == 3.0
    assert cfg.preflight_on_enter is False
    assert cfg.history_limit == 5
    assert cfg.hotkey_fix == "\\e\\C-f"
    assert cfg.hotkey_check == "\\e\\C-c"
    assert cfg.hotkey_describe == "\\C-g"
    assert cfg.config_path == p
    assert cfg.data_dir == tmp_path


def test_empty_file_returns_defaults(tmp_path, monkeypatch):
    p = tmp_path / "config.toml"
    p.write_text("")
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    cfg = config.load_config(p)
    assert cfg.llm_enabled is True
    assert cfg.llm_model == "qwen3:4b"
    assert cfg.config_path == p


def test_invalid_toml_returns_defaults_plus_warning(tmp_path, monkeypatch, capsys):
    p = tmp_path / "config.toml"
    p.write_text("this is not = valid toml [[[")
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    cfg = config.load_config(p)
    assert cfg.llm_enabled is True
    captured = capsys.readouterr()
    assert "th: warning:" in captured.err
    assert str(p) in captured.err
    assert "could not parse" in captured.err
    assert captured.out == ""


def test_partial_file_overrides_only_given_keys(tmp_path, monkeypatch):
    p = tmp_path / "config.toml"
    p.write_text('llm_model = "custom-model"\npreflight_on_enter = true\n')
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    cfg = config.load_config(p)
    assert cfg.llm_model == "custom-model"
    assert cfg.preflight_on_enter is True
    assert cfg.llm_enabled is True
    assert cfg.llm_backend == "ollama"
    assert cfg.history_limit == 5


def test_unknown_keys_ignored(tmp_path, monkeypatch):
    p = tmp_path / "config.toml"
    p.write_text('totally_unknown = 42\nanother = "x"\nllm_model = "m"\n')
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    cfg = config.load_config(p)
    assert cfg.llm_model == "m"


def test_llm_disabled_toggle(tmp_path, monkeypatch):
    p = tmp_path / "config.toml"
    p.write_text("llm_enabled = false\n")
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    cfg = config.load_config(p)
    assert cfg.llm_enabled is False


def test_nested_llm_table(tmp_path, monkeypatch):
    p = tmp_path / "config.toml"
    p.write_text('[llm]\nenabled = false\nmodel = "nested"\ntimeout_s = 7\n')
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    cfg = config.load_config(p)
    assert cfg.llm_enabled is False
    assert cfg.llm_model == "nested"
    assert cfg.llm_timeout_s == 7.0


def test_bad_type_uses_default(tmp_path, monkeypatch):
    p = tmp_path / "config.toml"
    p.write_text('llm_enabled = "false"\nhistory_limit = "five"\nllm_timeout_s = "3"\n')
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    cfg = config.load_config(p)
    assert cfg.llm_enabled is True
    assert cfg.history_limit == 5
    assert cfg.llm_timeout_s == 3.0


def test_env_config_path(tmp_path, monkeypatch):
    p = tmp_path / "env.toml"
    p.write_text('llm_model = "from-env"\n')
    monkeypatch.setenv("TH_CONFIG_PATH", str(p))
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    cfg = config.load_config()
    assert cfg.config_path == p
    assert cfg.llm_model == "from-env"
