from PySide6.QtCore import QThread, Signal

from novadownloader.core.dependencies import check_dependencies


class DependencyWorker(QThread):
    checks_ready = Signal(object)
    check_failed = Signal(str)

    def run(self) -> None:
        try:
            checks = check_dependencies(self.isInterruptionRequested)
        except Exception:
            # Do not send traceback, environment values or private paths to the UI.
            self.check_failed.emit("Ortam kontrolü tamamlanamadı. Tekrar kontrol etmeyi deneyin.")
        else:
            if not self.isInterruptionRequested():
                self.checks_ready.emit(checks)
