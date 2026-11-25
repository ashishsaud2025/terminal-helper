#!/usr/bin/env bash
set -euo pipefail

# Terminal Helper uninstaller.
#
# Removes only the th guarded block from ~/.bashrc (between
# "# >>> th >>>" and "# <<< th <<<"); never touches any other
# ~/.bashrc content. With --purge, also deletes the th data dir.
# The pip-installed package itself is left in place.

BASHRC="${HOME}/.bashrc"
START="# >>> th >>>"
END="# <<< th <<<"

if [ -f "$BASHRC" ] && grep -qF "$START" "$BASHRC"; then
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
  echo "Removed th block from $BASHRC."
else
  echo "No th block found in $BASHRC."
fi

if [ "${1:-}" = "--purge" ]; then
  rm -rf "${TH_DATA_DIR:-$HOME/.local/share/th}"
  echo "Purged data dir."
fi

echo "Uninstall complete. (Remove the package itself with: pip uninstall terminal-helper)"
