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

__th_describe() {
  local out rc line cmd
  local -a cands=()

  # Mid-cycle: walk the cached candidate list on each repeat press without
  # re-querying the LLM. Dangerous candidates were never cached.
  if [[ -n "${__TH_CANDIDATES:-}" && -n "${__TH_CAND_IDX:-}" ]]; then
    mapfile -t cands <<< "$__TH_CANDIDATES"
    local -a safe=() c
    for c in "${cands[@]}"; do
      [[ -n $c ]] && safe+=("$c")
    done
    if [[ ${#safe[@]} -gt 0 ]]; then
      __TH_CAND_IDX=$(( (__TH_CAND_IDX + 1) % ${#safe[@]} ))
      __TH_CANDIDATES="$(printf '%s\n' "${safe[@]}")"
      READLINE_LINE="${safe[__TH_CAND_IDX]}"
      READLINE_POINT=${#READLINE_LINE}
      return 0
    fi
    __TH_CANDIDATES=""
    __TH_CAND_IDX=""
  fi

  out=$(th describe -- "$READLINE_LINE" 2>/dev/null) || return 0
  rc=$?

  # Single candidate -> replace the buffer with it.
  if [[ $rc -eq 0 && -n "${out:-}" ]]; then
    __TH_CANDIDATES=""
    __TH_CAND_IDX=""
    READLINE_LINE="${out%%$'\t'*}"
    READLINE_POINT=${#READLINE_LINE}
    return 0
  fi

  # Ambiguous (rc 4) -> cache the numbered candidates, skipping danger-marked
  # ones ("! " prefix) which are never offered for buffer insertion, then
  # insert the first.
  if [[ $rc -eq 4 && -n "${out:-}" ]]; then
    while IFS= read -r line; do
      [[ $line =~ ^[[:space:]]*[0-9]+\)[[:space:]]*(.+)$ ]] || continue
      cmd="${BASH_REMATCH[1]}"
      cmd="${cmd%%$'\t'*}"
      # "! " prefix marks a danger candidate: shown but never inserted.
      [[ $cmd == "! "* ]] && continue
      [[ -n $cmd ]] && cands+=("$cmd")
    done <<< "$out"
    if [[ ${#cands[@]} -gt 0 ]]; then
      __TH_CAND_IDX=0
      __TH_CANDIDATES="$(printf '%s\n' "${cands[@]}")"
      READLINE_LINE="${cands[0]}"
      READLINE_POINT=${#READLINE_LINE}
    fi
  fi
}

# Hotkey: Ctrl+Alt+F (overridable via TH_HOTKEY_FIX). Needs bash >= 4.4 for
# bind -x + READLINE_LINE/READLINE_POINT.
bind -x "${TH_HOTKEY_FIX:-\"\e\C-f\"}":__th_fix 2>/dev/null || true

# Hotkey: Ctrl+G (overridable via TH_HOTKEY_DESCRIBE). Cycles through ambiguous
# candidates on repeat presses via __TH_CANDIDATES/__TH_CAND_IDX.
bind -x "${TH_HOTKEY_DESCRIBE:-\"\C-g\"}":__th_describe 2>/dev/null || true

trap '__th_preexec' DEBUG
PROMPT_COMMAND="__th_precmd${PROMPT_COMMAND:+;$PROMPT_COMMAND}"
