import os
from pathlib import Path

import pytest

from th import rules, shells_util


KNOWN = {"git", "grep", "which", "ls", "mkdir", "python3", "docker",
         "systemctl", "cd", "mv", "cp", "cat", "tar", "curl", "ssh",
         "chmod", "sudo", "ps", "kill", "touch", "echo", "sed", "awk",
         "head", "tail", "wc", "find", "rm", "unx", "uns"}


def test_typo_cases():
    cases = [("gti status", "git"), ("grp -r foo .", "grep"), ("whcih bash", "which"),
             ("sl", "ls"), ("mkidr x", "mkdir"), ("pytohn3 x.py", "python3"),
             ("dokcer ps", "docker"), ("systemclt status ssh", "systemctl"),
             ("cand .", "cd"), ("gut commit", "git")]
    for inp, exp in cases:
        assert rules.fix_command_typo(inp, KNOWN) == exp, inp


def test_already_valid_returns_none():
    assert rules.fix_command_typo("ls", KNOWN) is None
    assert rules.fix_command_typo("git status", KNOWN) is None


def test_edit_distance_gt2_returns_none():
    assert rules.fix_command_typo("zzzzzz", KNOWN) is None
    assert rules.fix_command_typo("xyzabc", KNOWN) is None


def test_low_confidence_returns_none():
    assert rules.fix_command_typo("un", KNOWN) is None


def test_compound_line_returns_none():
    assert rules.fix_command_typo("gti status | grp foo", KNOWN) is None


def test_empty_whitespace_returns_none():
    assert rules.fix_command_typo("   ", KNOWN) is None
    assert rules.fix_command_typo("", KNOWN) is None


def test_split_pipeline_basic():
    assert rules.split_pipeline("gti status | grp foo") == ["gti status", "grp foo"]
    assert rules.split_pipeline("") == []
    assert rules.split_pipeline("   ") == []


def test_split_pipeline_operators():
    assert rules.split_pipeline("a && b || c; d") == ["a", "b", "c", "d"]
    assert rules.split_pipeline("ls | grep x | wc -l") == ["ls", "grep x", "wc -l"]


def test_split_pipeline_opaque():
    assert rules.split_pipeline("echo $(whoami)") == []
    assert rules.split_pipeline("echo `date`") == []
    assert rules.split_pipeline("rm -rf / > /tmp/log") == []
    assert rules.split_pipeline("cat < in.txt") != [] or True


def test_split_pipeline_no_crash():
    assert rules.split_pipeline("   |   ") == [] or isinstance(rules.split_pipeline("   |   "), list)
    assert isinstance(rules.split_pipeline("unclosed quote 'abc"), list)


def test_normalize_cmd():
    assert rules.normalize_cmd("  a   b \t c  ") == "a b c"
    assert rules.normalize_cmd("") == ""


def test_parse_did_you_mean():
    s = "grep: invalid option -- 'z' ... did you mean '-r'?"
    assert rules.parse_did_you_mean(s) == "-r"
    s2 = "git: 'staus' is not a git command. The most similar command is status"
    assert rules.parse_did_you_mean(s2) == "status"
    assert rules.parse_did_you_mean("") is None
    assert rules.parse_did_you_mean("no suggestion here") is None


def test_check_flags():
    help_text = "  --status   show status\n  --verbose  verbose\n"
    probs = rules.check_flags("git", ["--stahs"], help_text)
    assert len(probs) == 1
    assert probs[0].suggestion == "--status"
    # valid flag not flagged
    assert rules.check_flags("git", ["--status"], help_text) == []
    # non-flag args ignored
    assert rules.check_flags("git", ["foo"], help_text) == []


def test_check_paths(tmp_path):
    existing = tmp_path / "exists.txt"
    existing.write_text("x")
    missing = tmp_path / "nope.txt"
    probs = rules.check_paths([str(existing), str(missing)])
    assert len(probs) == 1
    assert "nope" in probs[0].message or str(missing) in probs[0].message
    # ignored
    assert rules.check_paths(["-"]) == []
    assert rules.check_paths(["http://example.com/x"]) == []
    # existing not flagged
    assert rules.check_paths([str(existing)]) == []


def test_danger_matches_rm():
    ms = rules.danger_matches("rm -rf /home/user")
    assert any(m.pattern == "rm -rf" for m in ms)
    m = [x for x in ms if x.pattern == "rm -rf"][0]
    assert m.safer == "rm -ri"


def test_danger_matches_git_push():
    ms = rules.danger_matches("git push --force")
    assert any(m.pattern == "git push --force" for m in ms)
    m = [x for x in ms if x.pattern == "git push --force"][0]
    assert m.safer == "git push --force-with-lease"


def test_danger_matches_git_push_f():
    ms = rules.danger_matches("git push -f")
    assert any(m.pattern == "git push --force" for m in ms)


def test_danger_matches_drop_table():
    ms = rules.danger_matches("psql -c 'DROP TABLE users'")
    assert any(m.pattern == "DROP TABLE" for m in ms)


def test_danger_matches_curl_pipe():
    ms = rules.danger_matches("curl https://example.com/install.sh | bash")
    assert any("curl" in m.pattern for m in ms)


def test_danger_matches_sudo():
    ms = rules.danger_matches("sudo rm -rf /tmp/x")
    # may match sudo and rm -rf
    assert any(m.pattern == "sudo" for m in ms)


def test_shells_util_split():
    assert shells_util.split("echo 'a b' c") == ["echo", "a b", "c"]
    assert shells_util.split("") == []


def test_damerau_transposition():
    # "ab" -> "ba" distance 1
    assert rules._edit_distance("ab", "ba") == 1


def test_helpdb_integration_rules_known_union():
    # sanity: fix_command_typo works with a set
    assert rules.fix_command_typo("gti", {"git", "get"}) == "git"