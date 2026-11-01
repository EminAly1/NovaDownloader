import sys
from threading import Event, Timer

import pytest

from novadownloader.core.exceptions import AnalysisError, AnalysisErrorCode
from novadownloader.services import video_analyzer as service


def test_real_subprocess_output():
    assert (
        service._run_process([sys.executable, "-c", "print('metadata')"], Event(), 5).strip()
        == "metadata"
    )


@pytest.mark.parametrize("action,expected", [("cancel", "cancelled"), ("timeout", "timeout")])
def test_subprocess_is_reaped_after_cancel_or_timeout(monkeypatch, action, expected):
    original = service.subprocess.Popen
    processes = []

    def track(*args, **kwargs):
        process = original(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(service.subprocess, "Popen", track)
    event = Event()
    timer = Timer(0.2, event.set)
    if action == "cancel":
        timer.start()
    try:
        with pytest.raises(AnalysisError) as exc:
            service._run_process(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                event,
                0.2 if action == "timeout" else 5,
            )
        assert exc.value.code == AnalysisErrorCode(expected)
        assert processes[0].poll() is not None
        assert processes[0].stdout.closed and processes[0].stderr.closed
    finally:
        timer.cancel()


def test_subprocess_nonzero_exit_is_failure():
    with pytest.raises(AnalysisError) as exc:
        service._run_process([sys.executable, "-c", "raise SystemExit(1)"], Event(), 5)
    assert exc.value.code == AnalysisErrorCode.EXTRACTOR
