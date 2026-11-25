"""Performance tests for rules.preflight (< 50 ms warm cache)."""

import time
from pathlib import Path

from th import rules

KNOWN = {
    "git", "grep", "ls", "cat", "cp", "mv", "rm", "find", "tar", "chmod",
    "chown", "curl", "ssh", "python3", "mkdir", "touch", "sudo", "docker",
    "systemctl", "kubectl", "ps", "kill", "echo", "sed", "awk", "head",
    "tail", "wc", "unzip", "zip", "gzip", "tar",
}
HELP_TEXTS = {
    "git": "--version  show version\n-C <path>\n-c <name>=<value>\n",
    "ls": "-a  all\n-l  long\n--help\n",
    "rm": "-r  recursive\n-f  force\n--help\n",
}


def test_preflight_repeated_worst_case_under_50ms():
    cmdline = "git status --branch --versio | ls -a /tmp"
    durations = []
    for _ in range(200):
        start = time.perf_counter()
        rules.preflight(
            cmdline,
            known_commands=KNOWN,
            db_path=Path("does-not-exist.db"),
            history=["git status --branch"],
            help_texts=HELP_TEXTS,
        )
        durations.append(time.perf_counter() - start)
    worst = max(durations)
    assert worst < 0.050, f"worst-case preflight call took {worst * 1000:.1f} ms"
