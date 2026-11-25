# Terminal Helper (`th`)

Local-first CLI that logs shell commands and suggests fixes for mistyped or
failed commands: rules first, optional LLM second. Works entirely offline;
no network is used unless you enable an LLM backend.

## What `th` is

`th` is a terminal helper: it logs every command you run (exit code, cwd,
stderr tail) into a local SQLite database, then helps you recover from
failures:

- `th fix`: suggest a fix for the last failed command (typo correction,
  unknown-flag correction, did-you-mean parsing, then LLM fallback)
- `th check <cmd>`: pre-flight check a command line without executing it
- `th describe <what you want>`: convert an English request into a shell command
- `th help <cmd>`: show help for a command
- `th log`: record a command (used by the shell hook)
- `th doctor`: run pre-flight health checks on the installation

Buffer hotkeys (`Ctrl+Alt+F` fix, `Ctrl+Alt+C` check, `Ctrl+G` describe)
operate on your readline buffer via a `~/.bashrc` hook.

## Install

```bash
./install.sh
```

`install.sh`:

1. checks `bash >= 4.4` (required for the buffer hotkeys);
2. pip-installs the package editable, user scope (`pip install --user -e .`);
3. appends a guarded block sourcing `shells/th.bash` to `~/.bashrc`
   (between `# >>> th >>>` and `# <<< th <<<`);
4. is idempotent: re-running replaces the existing block, never duplicates it,
   and never touches other `~/.bashrc content`.

Next steps: restart your shell (`source ~/.bashrc`), then run `th doctor` to
verify the installation.

## Uninstall

```bash
./uninstall.sh        # remove the th block from ~/.bashrc
./uninstall.sh --purge # also delete the th data dir
```

`uninstall.sh` removes only the guarded block; it never touches any other
`~/.bashrc` content. The pip-installed package itself is left in place;
remove it with `pip uninstall terminal-helper` (or `pip uninstall th`) if
desired.

## Requirements

- **bash >= 4.4** is required for the buffer hotkeys, which use `bind -x`
  with `READLINE_LINE`/`READLINE_POINT`.
- `th log`, `th help`, `th check`, and `th doctor` work on any bash version.
- **zsh** parity is best-effort and is not the acceptance bar.

## Configuration

- Data dir: `~/.local/share/th`, overridable via `TH_DATA_DIR`.
- Config: `~/.config/th/config.toml`, overridable via `TH_CONFIG_PATH`.
  TOML format; missing or invalid files fall back to defaults; unknown keys
  are ignored.

Example `config.toml`:

```toml
[llm]
enabled = true
backend = "ollama"        # ollama | openai_compatible | anthropic | cli_agent
model = "qwen3:4b"
ollama_url = "http://127.0.0.1:11434"
timeout_s = 3.0

history_limit = 5
preflight_on_enter = false

[hotkeys]
fix = "\e\C-f"    # Ctrl+Alt+F
check = "\e\C-c"  # Ctrl+Alt+C
describe = "\C-g" # Ctrl+G
```

### Per-backend setup

- **Ollama (default, model `qwen3:4b`)**: install Ollama, pull the model
  (`ollama pull qwen3:4b`), and keep the server running at `llm_ollama_url`.
  `th` calls `POST /api/generate`; `th doctor` verifies reachability and that
  the model appears in `GET /api/tags`.
- **Disable the LLM entirely**: set `llm.enabled = false` → rules-only mode.
  Typo/flag/did-you-mean fixes keep working; no network is used at all.
- **openai_compatible**, **anthropic**, **cli_agent** (experimental): set
  `llm.backend` accordingly and configure the backend-specific URL/keys in
  `config.toml`.

### Mirrored networking (WSL → Windows Ollama)

If Ollama runs on Windows and you call it from WSL, WSL's NAT networking may
not reach it. One-time user-consent step:

1. On Windows, edit `%USERPROFILE%\.wslconfig`:

   ```ini
   [wsl2]
   networkingMode=mirrored
   ```

2. Run `wsl --shutdown`, then restart your WSL shell.

`th doctor` check 5 reports reachability and prints this hint when Ollama is
unreachable. The mirrored-networking change requires explicit user action (a
WSL restart) and is never performed by the installer.

## Stderr capture

Stderr capture is **not enabled by default**: the `~/.bashrc` hook logs the
exit code only, never the command's stderr. To keep a stderr tail for a
specific command, run `th log --stderr-file <file>` manually, or wrap command
execution with a tee approach (e.g. `cmd 2>err.txt; th log --cmd "$cmd" --stderr-file err.txt`).

## Hotkeys

| Key | Action |
|-----|--------|
| `Ctrl+Alt+F` | Fix the last failed command (rules → LLM fallback) |
| `Ctrl+Alt+C` | Pre-flight check the current readline buffer |
| `Ctrl+G` | Describe: English request → shell command |

All configurable via `[hotkeys]` in `config.toml`. Requires bash >= 4.4.

## Danger-confirm semantics

Dangerous commands (`rm -rf`, shell redirection truncation, `dd`, …) produce a
warning banner on stderr and are **never auto-inserted** into your buffer.
`Enter` is never blocked: you always decide whether to run a suggested
command. Danger suggestions are shown with a `!` marker but never inserted
without your explicit action.

## `th doctor`

Run `th doctor` to verify the installation. It runs 7 checks (**all of them,
even if an earlier check fails**), prints one line per check, and exits 0 iff
all fatal checks pass:

1. `bash >= 4.4` (`bash --version`)
2. th hook present in `~/.bashrc` (guarded block) **and** `~/.bashrc` parses
   (`bash -n`)
3. data dir writable and db schema current (`init_db` succeeds, tables present)
4. config parses (defaults OK), backend reported
5. Ollama reachable at `llm_ollama_url` and `llm_model` in `/api/tags`:
   **warn-only** (not a failure) when unreachable or LLM disabled, with a
   mirrored-networking hint
6. `th` on PATH (`shutil.which`)
7. hotkey collision check (`.inputrc` grep, best-effort, non-fatal)

### Troubleshooting: `th doctor` output meanings

- `[fail] bash >= 4.4`: upgrade bash; hotkeys need >= 4.4, everything else
  still works.
- `[fail] ~/.bashrc hook`: re-run `./install.sh`; confirm the guarded block is
  present and `bash -n ~/.bashrc` is clean.
- `[fail] data dir + schema`: check write permissions on the data dir
  (`~/.local/share/th` or `$TH_DATA_DIR`).
- `[warn] Ollama model`: Ollama unreachable or `llm_model` missing from
  `/api/tags`. Not a failure unless you need LLM fixes: see mirrored
  networking above, or set `llm.enabled = false` for rules-only mode.
- `[fail] th on PATH`: re-run `./install.sh` or add the install location to
  PATH.
- `[warn] hotkey collision`: another binding in `~/.inputrc` uses one of the
  th hotkeys; non-fatal.
