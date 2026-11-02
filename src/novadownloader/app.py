"""CLI entry point and Qt application bootstrap."""

import argparse
import json
import sys
from importlib.resources import files

from novadownloader import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NovaDownloader — yerel Linux uygulaması")
    parser.add_argument("--version", action="version", version=f"NovaDownloader {__version__}")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check-dependencies", action="store_true", help="GUI açmadan JSON tanılama yazdır"
    )
    mode.add_argument(
        "--smoke-test", action="store_true", help="Pencereyi aç, kontrolleri bekle ve güvenle kapat"
    )
    args = parser.parse_args(argv)
    if args.check_dependencies:
        from novadownloader.core.dependencies import check_dependencies

        checks = check_dependencies()
        print(json.dumps([check.to_dict() for check in checks], ensure_ascii=False, indent=2))
        return 0 if all(check.available for check in checks) else 1

    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from novadownloader.ui.main_window import MainWindow
    from novadownloader.ui.theme import stylesheet

    application = QApplication([sys.argv[0]])
    application.setApplicationName("NovaDownloader")
    application.setOrganizationName("NovaDownloader")
    application.setApplicationVersion(__version__)
    application.setDesktopFileName("io.github.novadownloader.NovaDownloader")
    application.setStyle("Fusion")
    application.setStyleSheet(stylesheet())
    application.setWindowIcon(QIcon(str(files("novadownloader").joinpath("resources", "icon.svg"))))
    window = MainWindow()
    smoke_failed = False
    smoke_timer = QTimer(window)
    smoke_timer.setSingleShot(True)

    def smoke_complete() -> None:
        smoke_timer.stop()
        print(f"GUI smoke: pencere açıldı, {len(window.checks)} bileşen kontrol edildi.")
        QTimer.singleShot(50, window.close)

    def smoke_timeout() -> None:
        nonlocal smoke_failed
        smoke_failed = True
        print("GUI smoke: ortam kontrolü tamamlanamadı.", file=sys.stderr)
        window.close()

    if args.smoke_test:
        window.checks_completed.connect(smoke_complete)
        smoke_timer.timeout.connect(smoke_timeout)
        smoke_timer.start(15_000)
    window.show()
    result = application.exec()
    return 1 if smoke_failed else result
