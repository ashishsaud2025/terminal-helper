#!/usr/bin/env bash
set -euo pipefail

# Terminal Helper installer.
#
# 1. Requires bash >= 4.4 (buffer hotkeys need bind -x + READLINE_LINE).
# 2. Pip-installs the package editable, user scope (pip install --user -e .).
# 3. Appends the th hook block (sourcing shells/th.bash) to ~/.bashrc.
#    Idempotent: re-running replaces the existing block, never duplicates it.

# 1. bash >= 4.4
bash_major_minor=$(bash --version | head -1 | sed -E 's/.*version ([0-9]+)\.([0-9]+).*/\1.\2/')
bash_major=${bash_major_minor%%.*}
bash_minor=${bash_major_minor##*.}
if [ "$bash_major" -lt 4 ] || { [ "$bash_major" -eq 4 ] && [ "$bash_minor" -lt 4 ]; }; then
  echo "th: bash >= 4.4 required (found $bash_major_minor)" >&2
  exit 1
fi

# 2. pip-install (editable, user scope)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! python3 -m pip install --user -e "$SCRIPT_DIR"; then
  echo "th: pip install failed" >&2
  exit 1
fi

# 3. Append guarded block sourcing shells/th.bash to ~/.bashrc (idempotent)
BASHRC="${HOME}/.bashrc"
touch "$BASHRC"
START="# >>> th >>>"
END="# <<< th <<<"
if grep -qF "$START" "$BASHRC"; then
  # remove existing block so re-runs stay idempotent
  python3 - "$BASHRC" "$START" "$END" <<'PY'
import sys
path, start, end = sys.argv[1], sys.argv[2], sys.argv[3]
lines = open(path).read().splitlines(keepends=True)
out = []
skip = False
for ln in lines:
    if ln.strip() == start:
        skip = True
        continue
    if ln.strip() == end:
        skip = False
        continue
    if not skip:
        out.append(ln)
open(path, "w").write("".join(out))
PY
fi

{
  echo "$START"
  echo "source \"$SCRIPT_DIR/shells/th.bash\""
  echo "$END"
} >> "$BASHRC"

echo "th installed."
echo "  - Restart your shell or run: source ~/.bashrc"
echo "  - Verify with: th doctor"
echo "  - Data dir: ${TH_DATA_DIR:-$HOME/.local/share/th}"
