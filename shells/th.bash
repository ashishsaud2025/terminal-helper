# Terminal Helper bash hook.
# Source this file from ~/.bashrc (install.sh does it).

__th_preexec() {
  [[ -n "${COMP_LINE:-}" ]] && return          # inside completion
  [[ "$BASH_COMMAND" == __th_* || "$BASH_COMMAND" == th\ * ]] && return  # no recursion
  [[ "$BASH_COMMAND" == PROMPT_COMMAND=* ]] && return  # hook self-setup
  __TH_LAST_CMD="$BASH_COMMAND"
}

__th_precmd() {
  local ec=$?
  [[ -n "${__TH_LAST_CMD:-}" ]] && th log --cmd "$__TH_LAST_CMD" --exit "$ec" --cwd "$PWD" >/dev/null 2>&1

  # Display-only hints after a failed command. Never modifies the buffer here.
  if [[ -n "${__TH_LAST_CMD:-}" && "$__TH_LAST_CMD" == "fix" && $ec -ne 0 ]]; then
    # The last thing typed was exactly `fix` and it failed: show a dim suggestion.
    local out
    out=$(th fix 2>/dev/null)
    if [[ $? -eq 0 && -n "${out:-}" ]]; then
      printf '\e[2mth fix: %s\e[0m\n' "${out%%$'\t'*}"
    fi
  elif [[ $ec -ne 0 ]]; then
    # One-line dim hint after any non-zero exit.
    printf '\e[2mth: previous command failed; run "th fix" or press Ctrl+Alt+F\e[0m\n'
  fi

  __TH_LAST_CMD=""
}

__th_fix() {
  local out
  out=$(th fix 2>/dev/null) || return 0
  [[ -n "${out:-}" ]] || return 0
  # Replace the readline buffer with the suggested command (tab-separated from reason).
  READLINE_LINE="${out%%$'\t'*}"
  READLINE_POINT=${#READLINE_LINE}
}

# Hotkey: Ctrl+Alt+F (overridable via TH_HOTKEY_FIX). Needs bash >= 4.4 for
# bind -x + READLINE_LINE/READLINE_POINT.
bind -x "${TH_HOTKEY_FIX:-\"\e\C-f\"}":__th_fix 2>/dev/null || true

trap '__th_preexec' DEBUG
PROMPT_COMMAND="__th_precmd${PROMPT_COMMAND:+;$PROMPT_COMMAND}"
