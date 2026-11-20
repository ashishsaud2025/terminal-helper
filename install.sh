#!/usr/bin/env bash
set -euo pipefail

# Check bash version >= 4.4
bash_major_minor=$(bash --version | head -1 | sed -E 's/.*version ([0-9]+)\.([0-9]+).*/\1.\2/')
bash_major=${bash_major_minor%%.*}
bash_minor=${bash_major_minor##*.}
if [ "$bash_major" -lt 4 ] || { [ "$bash_major" -eq 4 ] && [ "$bash_minor" -lt 4 ]; }; then
  echo "th: bash >= 4.4 required (found $bash_major_minor)" >&2
  exit 1
fi

# Resolve script dir
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Install package
if command -v pipx >/dev/null 2>&1; then
  pipx install -e "$SCRIPT_DIR" >/dev/null 2>&1 || pipx reinstall th >/dev/null 2>&1 || true
else
  python3 -m pip install --user -e "$SCRIPT_DIR"
fi

# Append guarded block to ~/.bashrc (idempotent)
BASHRC="${HOME}/.bashrc"
touch "$BASHRC"
START="# >>> th >>>"
END="# <<< th <<<"
if grep -qF "$START" "$BASHRC"; then
  # remove existing block
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

echo "th installed. Open a new shell or 'source ~/.bashrc'."
echo "Data dir: ${TH_DATA_DIR:-$HOME/.local/share/th}"
