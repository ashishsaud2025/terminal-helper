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
  __TH_LAST_CMD=""
}

trap '__th_preexec' DEBUG
PROMPT_COMMAND="__th_precmd${PROMPT_COMMAND:+;$PROMPT_COMMAND}"
