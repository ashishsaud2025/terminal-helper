# Terminal Helper (`th`)

Local-first CLI that logs shell commands and, eventually, suggests fixes for
typos and failed commands.

Status: logging hook and SQLite history are in place.

## Install

```bash
bash install.sh
```

Optional: set `TH_CAPTURE_STDERR=1` to capture stderr (documented; out of scope
for the hook itself).

## Configuration

- Data dir overridable via `TH_DATA_DIR` (default `~/.local/share/th`).
- Config path overridable via `TH_CONFIG_PATH` (default `~/.config/th/config.toml`).
- Config is TOML. Missing or invalid file falls back to defaults; unknown keys
  are ignored. Set `llm.enabled = false` (under `[llm]`) to disable all LLM use.
- Default hotkeys: fix `Ctrl+Alt+F` (`\e\C-f`), check `Ctrl+Alt+C` (`\e\C-c`),
  describe `Ctrl+G` (`\C-g`).
