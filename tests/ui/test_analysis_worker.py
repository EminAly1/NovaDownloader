from threading import Event

import pytest

from novadownloader.core.exceptions import AnalysisError, AnalysisErrorCode
from novadownloader.workers.analysis_worker import AnalysisWorker


@pytest.mark.parametrize("outcome", ["success", "error", "unexpected", "cancel"])
def test_worker_terminal_signals_and_lifecycle(qtbot, outcome):
    entered = Event()

    class Analyzer:
        def analyze(self, url, cancel):
            entered.set()
            if outcome == "error":
                raise AnalysisError(AnalysisErrorCode.NETWORK)
            if outcome == "unexpected":
                raise RuntimeError("extractor internal failure")
            if outcome == "cancel":
                cancel.wait(3)
                raise AnalysisError(AnalysisErrorCode.CANCELLED)
            return "metadata"

    worker = AnalysisWorker(17, "url", analyzer=Analyzer())
    signals = []
    worker.succeeded.connect(lambda key, data: signals.append(("success", key, data)))
    worker.failed.connect(lambda key, data: signals.append(("error", key, data.code)))
    worker.cancelled.connect(lambda key: signals.append(("cancel", key)))
    with qtbot.waitSignal(worker.finished, timeout=4000):
        worker.start()
        if outcome == "cancel":
            qtbot.waitUntil(entered.is_set)
            worker.cancel()
    assert not worker.isRunning()
    assert len(signals) == 1
    assert signals[0][1] == 17
    if outcome == "unexpected":
        assert signals[0] == ("error", 17, AnalysisErrorCode.EXTRACTOR)
    else:
        assert signals[0][0] == outcome
    worker.deleteLater()
