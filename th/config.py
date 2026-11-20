"""Configuration loader for Terminal Helper.

Reads a TOML config file (stdlib ``tomllib``) and returns a :class:`Config`
with safe defaults when the file is missing, empty, or unparseable.
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_DEFAULT_HOTKEY_FIX = "\\e\\C-f"
_DEFAULT_HOTKEY_CHECK = "\\e\\C-c"
_DEFAULT_HOTKEY_DESCRIBE = "\\C-g"


@dataclass
class Config:
    data_dir: Path = field(default_factory=lambda: _default_data_dir())
    config_path: Path = field(default_factory=lambda: _default_config_path())
    llm_enabled: bool = True
    llm_backend: str = "ollama"
    llm_model: str = "qwen3:4b"
    llm_ollama_url: str = "http://127.0.0.1:11434"
    llm_timeout_s: float = 3.0
    preflight_on_enter: bool = False
    history_limit: int = 5
    hotkey_fix: str = _DEFAULT_HOTKEY_FIX
    hotkey_check: str = _DEFAULT_HOTKEY_CHECK
    hotkey_describe: str = _DEFAULT_HOTKEY_DESCRIBE


def _default_data_dir() -> Path:
    env = os.environ.get("TH_DATA_DIR")
    if env:
        return Path(env)
    return Path.home() / ".local" / "share" / "th"


def _default_config_path() -> Path:
    env = os.environ.get("TH_CONFIG_PATH")
    if env:
        return Path(env)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "th" / "config.toml"


def _resolve_config_path(path: Path | None) -> Path:
    if path is not None:
        return Path(path)
    env = os.environ.get("TH_CONFIG_PATH")
    if env:
        return Path(env)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "th" / "config.toml"


def _resolve_data_dir() -> Path:
    env = os.environ.get("TH_DATA_DIR")
    if env:
        return Path(env)
    return Path.home() / ".local" / "share" / "th"


def _default_values() -> dict[str, Any]:
    return {
        "llm_enabled": True,
        "llm_backend": "ollama",
        "llm_model": "qwen3:4b",
        "llm_ollama_url": "http://127.0.0.1:11434",
        "llm_timeout_s": 3.0,
        "preflight_on_enter": False,
        "history_limit": 5,
        "hotkey_fix": _DEFAULT_HOTKEY_FIX,
        "hotkey_check": _DEFAULT_HOTKEY_CHECK,
        "hotkey_describe": _DEFAULT_HOTKEY_DESCRIBE,
    }


def _extract(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten supported TOML layouts into canonical keys."""
    out: dict[str, Any] = {}

    llm = raw.get("llm")
    if isinstance(llm, dict):
        if "enabled" in llm:
            out["llm_enabled"] = llm.get("enabled")
        if "backend" in llm:
            out["llm_backend"] = llm.get("backend")
        if "model" in llm:
            out["llm_model"] = llm.get("model")
        if "ollama_url" in llm:
            out["llm_ollama_url"] = llm.get("ollama_url")
        elif "url" in llm:
            out["llm_ollama_url"] = llm.get("url")
        if "timeout_s" in llm:
            out["llm_timeout_s"] = llm.get("timeout_s")
        elif "timeout" in llm:
            out["llm_timeout_s"] = llm.get("timeout")

    history = raw.get("history")
    if isinstance(history, dict):
        if "limit" in history:
            out["history_limit"] = history.get("limit")
        if "history_limit" in history:
            out["history_limit"] = history.get("history_limit")

    preflight = raw.get("preflight")
    if isinstance(preflight, dict):
        if "on_enter" in preflight:
            out["preflight_on_enter"] = preflight.get("on_enter")
        if "preflight_on_enter" in preflight:
            out["preflight_on_enter"] = preflight.get("preflight_on_enter")

    for hotkeys_key in ("hotkeys", "keys", "hotkey"):
        hotkeys = raw.get(hotkeys_key)
        if isinstance(hotkeys, dict):
            if "fix" in hotkeys:
                out["hotkey_fix"] = hotkeys.get("fix")
            if "check" in hotkeys:
                out["hotkey_check"] = hotkeys.get("check")
            if "describe" in hotkeys:
                out["hotkey_describe"] = hotkeys.get("describe")

    ui = raw.get("ui")
    if isinstance(ui, dict) and "preflight_on_enter" in ui:
        out["preflight_on_enter"] = ui.get("preflight_on_enter")

    flat_keys = (
        "llm_enabled", "llm_backend", "llm_model", "llm_ollama_url",
        "llm_timeout_s", "preflight_on_enter", "history_limit",
        "hotkey_fix", "hotkey_check", "hotkey_describe",
    )
    for key in flat_keys:
        if key in raw:
            out[key] = raw.get(key)

    return out


def _apply_value(values: dict[str, Any], key: str, value: Any) -> None:
    if key == "llm_enabled":
        if isinstance(value, bool):
            values[key] = value
    elif key == "preflight_on_enter":
        if isinstance(value, bool):
            values[key] = value
    elif key in ("llm_backend", "llm_model", "llm_ollama_url", "hotkey_fix", "hotkey_check", "hotkey_describe"):
        if isinstance(value, str):
            values[key] = value
    elif key == "llm_timeout_s":
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)):
            values[key] = float(value)
    elif key == "history_limit":
        if isinstance(value, bool):
            return
        if isinstance(value, int):
            values[key] = value
        elif isinstance(value, float) and value.is_integer():
            values[key] = int(value)


def load_config(path: Path | None = None) -> Config:
    resolved_path = _resolve_config_path(path)
    data_dir = _resolve_data_dir()

    values = _default_values()

    if resolved_path.exists():
        try:
            with resolved_path.open("rb") as f:
                content = f.read()
            if content.strip() == b"":
                raw: Any = {}
            else:
                raw = tomllib.loads(content.decode("utf-8"))
            if not isinstance(raw, dict):
                raw = {}
            extracted = _extract(raw)
            for key, val in extracted.items():
                _apply_value(values, key, val)
        except tomllib.TOMLDecodeError as exc:
            print(
                f"th: warning: {resolved_path}: could not parse ({exc}); using defaults",
                file=sys.stderr,
            )
        except Exception as exc:
            print(
                f"th: warning: {resolved_path}: could not parse ({exc}); using defaults",
                file=sys.stderr,
            )

    return Config(
        data_dir=data_dir,
        config_path=resolved_path,
        llm_enabled=values["llm_enabled"],
        llm_backend=values["llm_backend"],
        llm_model=values["llm_model"],
        llm_ollama_url=values["llm_ollama_url"],
        llm_timeout_s=values["llm_timeout_s"],
        preflight_on_enter=values["preflight_on_enter"],
        history_limit=values["history_limit"],
        hotkey_fix=values["hotkey_fix"],
        hotkey_check=values["hotkey_check"],
        hotkey_describe=values["hotkey_describe"],
    )
