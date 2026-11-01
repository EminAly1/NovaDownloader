import importlib.metadata
import subprocess

import pytest

from novadownloader.core import dependencies as deps


@pytest.fixture
def available_environment(monkeypatch):
    monkeypatch.setattr(deps.sys, "version_info", (3, 12, 14))
    monkeypatch.setattr(deps.importlib.metadata, "version", lambda name: "1.2.3")
    monkeypatch.setattr(deps.shutil, "which", lambda command: f"/usr/bin/{command}")

    def run(arguments, **kwargs):
        assert isinstance(arguments, list)
        assert kwargs["timeout"] == deps.COMMAND_TIMEOUT
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert "shell" not in kwargs
        output = "deno 2.5.1\nv8 14.0" if "deno" in arguments[0] else "ffmpeg version 7.1.5"
        return subprocess.CompletedProcess(arguments, 0, output, "")

    monkeypatch.setattr(deps.subprocess, "run", run)


def test_reports_every_required_component(available_environment):
    checks = deps.check_dependencies()
    assert [check.name for check in checks] == [
        "Python",
        "PySide6 / Qt",
        "yt-dlp",
        "EJS",
        "FFmpeg",
        "FFprobe",
        "Deno",
    ]
    assert all(check.available for check in checks)
    assert checks[-1].version == "2.5.1"
    assert checks[-1].to_dict()["state"] == "available"


def test_missing_package_has_actionable_remedy(available_environment, monkeypatch):
    def version(name):
        if name == "yt-dlp-ejs":
            raise importlib.metadata.PackageNotFoundError(name)
        return "1.2.3"

    monkeypatch.setattr(deps.importlib.metadata, "version", version)
    checks = deps.check_dependencies()
    ejs = next(check for check in checks if check.name == "EJS")
    assert ejs.state == deps.DependencyState.MISSING
    assert ejs.version == ""
    assert "setup-dev.sh" in ejs.remedy


def test_missing_executables_do_not_attempt_subprocess(available_environment, monkeypatch):
    monkeypatch.setattr(deps.shutil, "which", lambda _: None)
    monkeypatch.setattr(deps.sys, "executable", "/nonexistent-test-env/bin/python")
    monkeypatch.setattr(deps.subprocess, "run", lambda *a, **kw: pytest.fail("must not execute"))
    checks = deps.check_dependencies()
    assert all(check.state == deps.DependencyState.MISSING for check in checks[-3:])


@pytest.mark.parametrize("error", [subprocess.TimeoutExpired("tool", 2), PermissionError()])
def test_command_errors_are_visible_and_do_not_expose_details(
    available_environment, monkeypatch, error
):
    def run(*args, **kwargs):
        raise error

    monkeypatch.setattr(deps.subprocess, "run", run)
    checks = deps.check_dependencies()
    assert all(check.state == deps.DependencyState.ERROR for check in checks[-3:])
    assert all(check.remedy for check in checks[-3:])
    assert "/usr/bin" not in str([check.to_dict() for check in checks])


@pytest.mark.parametrize(
    ("output", "returncode", "state"),
    [
        ("deno 2.2.9", 0, deps.DependencyState.UNSUPPORTED),
        ("deno 2.3.0", 0, deps.DependencyState.AVAILABLE),
        ("deno 3.0.0", 0, deps.DependencyState.AVAILABLE),
        ("unexpected output", 0, deps.DependencyState.ERROR),
        ("deno 2.5.1", 1, deps.DependencyState.ERROR),
        ("deno 2.3", 0, deps.DependencyState.ERROR),
    ],
)
def test_deno_version_validation(available_environment, monkeypatch, output, returncode, state):
    monkeypatch.setattr(
        deps.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a, returncode, output, ""),
    )
    assert deps.check_dependencies()[-1].state == state


def test_unsupported_python_is_reported(available_environment, monkeypatch):
    monkeypatch.setattr(deps.sys, "version_info", (3, 11, 10))
    check = deps.check_dependencies()[0]
    assert check.state == deps.DependencyState.UNSUPPORTED
    assert "3.12" in check.remedy


def test_interruption_stops_before_additional_checks(available_environment, monkeypatch):
    monkeypatch.setattr(
        deps.importlib.metadata, "version", lambda _: pytest.fail("must not inspect packages")
    )
    checks = deps.check_dependencies(should_stop=lambda: True)
    assert [check.name for check in checks] == ["Python"]


def test_local_deno_next_to_interpreter_is_discovered(monkeypatch, tmp_path):
    monkeypatch.setattr(deps.shutil, "which", lambda _: None)
    monkeypatch.setattr(deps.sys, "executable", str(tmp_path / "python"))
    local_deno = tmp_path / "deno"
    local_deno.touch()
    assert deps.find_deno() == str(local_deno)
