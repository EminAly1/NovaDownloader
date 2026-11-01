from threading import Event

import pytest
from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import QApplication

from novadownloader.core.dependencies import DependencyCheck, DependencyState
from novadownloader.ui.main_window import MainWindow
from novadownloader.workers import dependency_worker


@pytest.fixture
def sample_checks():
    return [
        DependencyCheck("Python", DependencyState.AVAILABLE, "3.12.14", "Destekleniyor."),
        DependencyCheck("Deno", DependencyState.MISSING, "", "Bulunamadı.", "Deno kurun."),
    ]


def test_window_populates_results_off_main_thread(qtbot, monkeypatch, sample_checks):
    threads = []

    def check(stop):
        threads.append(QThread.currentThread())
        return sample_checks

    monkeypatch.setattr(dependency_worker, "check_dependencies", check)
    window = MainWindow()
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.checks_completed, timeout=3000):
        window.show()
    qtbot.waitUntil(window.recheck_button.isEnabled)
    assert threads[0] != QApplication.instance().thread()
    assert window.windowTitle() == "NovaDownloader"
    assert "1 bileşen" in window.summary_label.text()
    assert window.copy_button.isEnabled()
    assert not window.busy_bar.isVisible()
    qtbot.mouseClick(window.copy_button, Qt.MouseButton.LeftButton)
    assert "Deno: Eksik" in QApplication.clipboard().text()
    assert "Deno kurun." in QApplication.clipboard().text()


def test_duplicate_checks_are_prevented_and_close_is_cooperative(qtbot, monkeypatch, sample_checks):
    entered = Event()
    release = Event()

    def check(stop):
        entered.set()
        release.wait(timeout=3)
        return sample_checks

    monkeypatch.setattr(dependency_worker, "check_dependencies", check)
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    try:
        qtbot.waitUntil(entered.is_set)
        worker = window._worker
        assert not window.recheck_button.isEnabled()
        assert window.busy_bar.isVisible()
        window.start_checks()
        assert window._worker is worker
        window.close()
        assert worker.isInterruptionRequested()
        assert window.isVisible()  # Closing waits without blocking the GUI event loop.
    finally:
        release.set()
        qtbot.waitUntil(lambda: not window.isVisible(), timeout=4000)
    assert not worker.isRunning()


def test_unexpected_check_error_can_be_retried(qtbot, monkeypatch, sample_checks):
    def fail(stop):
        raise RuntimeError("private/path/should-not-be-shown")

    monkeypatch.setattr(dependency_worker, "check_dependencies", fail)
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: "tamamlanamadı" in window.summary_label.text())
    qtbot.waitUntil(window.recheck_button.isEnabled)
    assert "private" not in window.summary_label.text()
    assert not window.copy_button.isEnabled()
    monkeypatch.setattr(dependency_worker, "check_dependencies", lambda stop: sample_checks)
    with qtbot.waitSignal(window.checks_completed, timeout=3000):
        qtbot.mouseClick(window.recheck_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(window.recheck_button.isEnabled)
    assert window.copy_button.isEnabled()


@pytest.mark.parametrize("size", [(640, 520), (1000, 760), (1440, 900)])
def test_window_sizes_and_repeated_refresh(qtbot, monkeypatch, sample_checks, size):
    monkeypatch.setattr(dependency_worker, "check_dependencies", lambda stop: sample_checks)
    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(*size)
    with qtbot.waitSignal(window.checks_completed, timeout=3000):
        window.show()
    qtbot.waitUntil(window.recheck_button.isEnabled)
    original_items = window.results_layout.count()
    with qtbot.waitSignal(window.checks_completed, timeout=3000):
        qtbot.mouseClick(window.recheck_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(window.recheck_button.isEnabled)
    assert window.results_layout.count() == original_items
    assert window.recheck_button.geometry().intersects(window.copy_button.geometry()) is False
    assert window.centralWidget().horizontalScrollBar().maximum() == 0
