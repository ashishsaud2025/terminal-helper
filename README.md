# Terminal Helper (`th`)

`th` logs your shell commands and suggests fixes for mistakes. It uses rules first, then an optional LLM. It works offline unless you turn on an LLM backend. It never runs a command for you.

## What `th` does

`th` records every command you run (exit code, folder, error output) in a local SQLite database. When a command fails, `th` helps you recover:

- `th fix` : suggests a fix for the last failed command (typo, wrong flag, did-you-mean, then LLM fallback)
- `th check <cmd>` : checks a command line before you run it
- `th describe <what you want>` : turns an English request into a shell command
- `th help <cmd>` : shows help for a command
- `th log` : records a command (the shell hook uses this)
- `th doctor` : runs health checks on your installation

Buffer hotkeys (`Ctrl+Alt+F` fix, `Ctrl+Alt+C` check, `Ctrl+G` describe) edit your readline buffer through a `~/.bashrc` hook. You always press Enter.

## Install

```bash
./install.sh
```

`install.sh`:

1. checks bash is 4.4 or newer (needed for buffer hotkeys);
2. installs the package editable in user scope (`pip install --user -e .`);
3. adds a guarded block that sources `shells/th.bash` to `~/.bashrc` (between `# >>> th >>>` and `# <<< th <<<`);
4. runs idempotently: re-running replaces the block, never duplicates it, and never touches other `~/.bashrc` content.

Restart your shell (`source ~/.bashrc`), then run `th doctor` to verify.

## Uninstall

```bash
./uninstall.sh            # remove the th block from ~/.bashrc
./uninstall.sh --purge    # also delete the th data folder
```

`uninstall.sh` removes only the guarded block. It never touches other `~/.bashrc` content. The pip-installed package stays. Remove it with `pip uninstall terminal-helper` if you want.

## Requirements

- **bash 4.4 or newer** for buffer hotkeys (they use `bind -x` with `READLINE_LINE`/`READLINE_POINT`).
- `th log`, `th help`, `th check`, and `th doctor` work on any bash version.
- **zsh** support is best-effort only.

## Configuration

- Data folder: `~/.local/share/th` (set `TH_DATA_DIR` to change it).
- Config: `~/.config/th/config.toml` (set `TH_CONFIG_PATH` to change it). TOML format. Missing or invalid files fall back to defaults. Ignore unknown keys.

Example `config.toml`:

```toml
[llm]
enabled = true
backend = "ollama"
model = "qwen3:4b"
ollama_url = "http://127.0.0.1:11434"
timeout_s = 3.0

history_limit = 5
preflight_on_enter = false

[hotkeys]
fix = "\e\C-f"
check = "\e\C-c"
describe = "\C-g"
```

### Backend setup

- **Ollama (default, model `qwen3:4b`)**: install Ollama, pull the model (`ollama pull qwen3:4b`), and keep the server at `llm_ollama_url`. `th` calls `POST /api/generate`. `th doctor` checks reachability and that the model appears in `GET /api/tags`.
- **Turn off the LLM**: set `llm.enabled = false`. You get rules-only mode: typo, flag, and did-you-mean fixes still work, and no network is used.
- **openai_compatible**, **anthropic**, **cli_agent** (experimental): set `llm.backend` and add the backend URL and keys in `config.toml`.

### WSL to Windows Ollama

If Ollama runs on Windows and you call it from WSL, WSL's NAT networking may not reach it. Do this one-time step:

1. On Windows, edit `%USERPROFILE%\.wslconfig`:

   ```ini
   [wsl2]
   networkingMode=mirrored
   ```

2. Run `wsl --shutdown`, then restart your WSL shell.

`th doctor` check 5 reports reachability and prints this hint when Ollama is unreachable. You must run this step yourself. The installer never changes `.wslconfig` or restarts WSL.

## Stderr capture

Stderr capture is off by default. The `~/.bashrc` hook logs the exit code only, never the command's stderr. To keep an error tail for one command, run `th log --stderr-file <file>` manually, or wrap the command with a tee approach (for example: `cmd 2>err.txt; th log --cmd "$cmd" --stderr-file err.txt`).

## Hotkeys

| Key | Action |
|-----|--------|
| `Ctrl+Alt+F` | Fix the last failed command (rules then LLM fallback) |
| `Ctrl+Alt+C` | Pre-flight check the current readline buffer |
| `Ctrl+G` | Describe: English request to shell command |

Change them in `[hotkeys]` in `config.toml`. You need bash 4.4 or newer.

## Dangerous commands

Dangerous commands (`rm -rf`, shell redirection truncation, `dd`, and others) show a warning banner on stderr. `th` never inserts them into your buffer. Enter is never blocked. You decide whether to run a suggested command. Danger suggestions show a `!` marker but never insert without your action.

## th doctor

Run `th doctor` to verify your installation. It runs seven checks, all of them even if an earlier check fails, prints one line per check, and exits 0 only if all fatal checks pass:

1. `bash >= 4.4` (`bash --version`)
2. th hook present in `~/.bashrc` (guarded block) and `~/.bashrc` parses (`bash -n`)
3. data folder writable and database schema current (`init_db` succeeds, tables present)
4. config parses (defaults OK), backend reported
5. Ollama reachable at `llm_ollama_url` and `llm_model` in `/api/tags` : warn-only when unreachable or LLM disabled, with a mirrored-networking hint
6. `th` on PATH (`shutil.which`)
7. hotkey collision check (`.inputrc` grep, best-effort, non-fatal)

### Reading th doctor output

- `[fail] bash >= 4.4` : upgrade bash. Hotkeys need 4.4 or newer; everything else still works.
- `[fail] ~/.bashrc hook` : re-run `./install.sh`. Confirm the guarded block exists and `bash -n ~/.bashrc` is clean.
- `[fail] data folder + schema` : check write permission on the data folder (`~/.local/share/th` or `$TH_DATA_DIR`).
- `[warn] Ollama model` : Ollama unreachable or `llm_model` missing from `/api/tags`. Not a failure unless you need LLM fixes. See WSL networking above, or set `llm.enabled = false` for rules-only mode.
- `[fail] th on PATH` : re-run `./install.sh` or add the install location to PATH.
- `[warn] hotkey collision` : another binding in `~/.inputrc` uses one of the th hotkeys. Non-fatal.
