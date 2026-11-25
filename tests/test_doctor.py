"""Tests for `th doctor`: injectable probes, all-checks-run, warn-only Ollama."""

from th import cli

_PROBES = (
    "probe_bash_version",
    "probe_bashrc_hook",
    "probe_data_dir",
    "probe_config",
    "probe_ollama",
    "probe_th_on_path",
    "probe_hotkey_collision",
)


def _install_fakes(monkeypatch, fakes):
    for name in _PROBES:
        fake = fakes.get(name, lambda: cli.DoctorResult(True, "ok"))
        if not callable(fake):
            value = fake
            fake = lambda _v=value: _v
        monkeypatch.setattr(cli, name, fake)


def _doctor(monkeypatch, fakes):
    _install_fakes(monkeypatch, fakes)
    args = cli.build_parser().parse_args(["doctor"])
    return cli.cmd_doctor(args)


def _ok(detail="ok"):
    return cli.DoctorResult(True, detail)


def _fail(detail="fail"):
    return cli.DoctorResult(False, detail)


def _warn(detail="warn"):
    return cli.DoctorResult(False, detail, fatal=False)


def _all_ok():
    return {name: _ok(f"{name} ok") for name in _PROBES}


def test_doctor_all_green_exit_zero(monkeypatch, capsys):
    rc = _doctor(monkeypatch, _all_ok())
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    assert rc == 0
    assert len(lines) == 7  # one line per check
    assert all(line.startswith("[ok]") for line in lines)


def test_doctor_each_check_passes_fails_independently(monkeypatch, capsys):
    fakes = _all_ok()
    fakes["probe_bash_version"] = _fail("bash 3.2")
    rc = _doctor(monkeypatch, fakes)
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    assert rc != 0
    assert len(lines) == 7
    assert lines[0].startswith("[fail]") and "bash 3.2" in lines[0]
    assert all(line.startswith("[ok]") for line in lines[1:])


def test_doctor_all_checks_run_even_if_one_fails(monkeypatch, capsys):
    calls = []

    def make(name):
        def probe():
            calls.append(name)
            return _fail("boom") if name == "probe_bash_version" else _ok()

        return probe

    fakes = {name: make(name) for name in _PROBES}
    rc = _doctor(monkeypatch, fakes)
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    assert rc != 0
    assert calls == list(_PROBES)  # every probe ran, in order
    assert len(lines) == 7  # one line per check despite the failure


def test_doctor_exit_nonzero_when_any_fatal_check_fails(monkeypatch, capsys):
    _NON_FATAL = {"probe_ollama", "probe_hotkey_collision"}
    for name in _PROBES:
        fakes = _all_ok()
        fakes[name] = _fail(f"{name} broken")
        rc = _doctor(monkeypatch, fakes)
        out = capsys.readouterr().out
        if name in _NON_FATAL:
            assert rc == 0, f"{name} is warn-only, must exit zero"
            continue
        assert rc != 0, f"{name} failure should exit non-zero"
        fail_lines = [line for line in out.splitlines() if line.startswith("[fail]")]
        assert len(fail_lines) == 1
        assert f"{name} broken" in fail_lines[0]


def test_doctor_ollama_unreachable_is_warn_only(monkeypatch, capsys):
    fakes = _all_ok()
    fakes["probe_ollama"] = _warn(
        "Ollama not reachable at http://127.0.0.1:11434/api/tags - "
        "mirrored-networking hint: networkingMode=mirrored, then wsl --shutdown"
    )
    rc = _doctor(monkeypatch, fakes)
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    assert rc == 0  # warn-only: not a failure
    ollama = [line for line in lines if "Ollama model" in line][0]
    assert "[warn]" in ollama
    assert "mirrored-networking" in ollama
    assert all(line.startswith("[ok]") for line in lines if "Ollama model" not in line)


def test_doctor_ollama_disabled_is_warn_only(monkeypatch, capsys):
    fakes = _all_ok()
    fakes["probe_ollama"] = cli.DoctorResult(True, "LLM disabled (rules-only mode)", fatal=False)
    rc = _doctor(monkeypatch, fakes)
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    assert rc == 0
    assert lines[4].startswith("[ok]")
    assert "LLM disabled" in lines[4]
