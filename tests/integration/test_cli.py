import json
import subprocess
import sys


def test_version_without_gui():
    result = subprocess.run(
        [sys.executable, "-m", "novadownloader", "--version"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "NovaDownloader 0.1.0"
    assert not result.stderr


def test_real_offline_diagnostics_have_consistent_exit_code():
    result = subprocess.run(
        [sys.executable, "-m", "novadownloader", "--check-dependencies"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    checks = json.loads(result.stdout)
    assert len(checks) == 7
    assert all(
        check["state"] in {"available", "missing", "error", "unsupported"} for check in checks
    )
    assert result.returncode == (0 if all(c["state"] == "available" for c in checks) else 1)
    assert not result.stderr
