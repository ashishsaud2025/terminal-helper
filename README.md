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

- Data dir overridable via `TH_DATA_DIR`.
- Config path overridable via `TH_CONFIG_PATH`.
