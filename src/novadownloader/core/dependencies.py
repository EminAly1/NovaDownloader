"""Bounded, offline runtime checks. Never install or update anything here."""

import importlib.metadata
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

COMMAND_TIMEOUT = 2.0


def find_deno() -> str | None:
    executable = shutil.which("deno")
    sibling = Path(sys.executable).parent / "deno"
    return executable or (str(sibling) if sibling.is_file() else None)


class DependencyState(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class DependencyCheck:
    name: str
    state: DependencyState
    version: str
    message: str
    remedy: str = ""

    @property
    def available(self) -> bool:
        return self.state == DependencyState.AVAILABLE

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _package_check(name: str, distribution: str, remedy: str) -> DependencyCheck:
    try:
        version = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return DependencyCheck(name, DependencyState.MISSING, "", "Python paketi eksik.", remedy)
    return DependencyCheck(name, DependencyState.AVAILABLE, version, "Python paketi kurulu.")


def _command_check(name: str, command: str, flag: str, remedy: str) -> DependencyCheck:
    executable = find_deno() if command == "deno" else shutil.which(command)
    if not executable:
        return DependencyCheck(
            name, DependencyState.MISSING, "", "PATH üzerinde bulunamadı.", remedy
        )
    try:
        result = subprocess.run(
            [executable, flag],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=COMMAND_TIMEOUT,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return DependencyCheck(
            name, DependencyState.ERROR, "", "Sürüm kontrolü zaman aşımına uğradı.", remedy
        )
    except OSError:
        return DependencyCheck(name, DependencyState.ERROR, "", "Araç çalıştırılamadı.", remedy)
    if result.returncode != 0:
        return DependencyCheck(name, DependencyState.ERROR, "", "Sürüm kontrolü başarısız.", remedy)
    # Avoid showing arbitrary tool output or local paths in UI/copied diagnostics.
    output = result.stdout or result.stderr
    is_deno = Path(command).name == "deno"
    pattern = r"\bdeno\s+(\d+\.\d+\.\d+)" if is_deno else r"\bversion\s+(\S+)"
    match = re.search(pattern, output)
    if not match:
        return DependencyCheck(name, DependencyState.ERROR, "", "Sürüm bilgisi okunamadı.", remedy)
    version = match[1][:80]
    if is_deno and tuple(map(int, version.split("."))) < (2, 3, 0):
        return DependencyCheck(
            name, DependencyState.UNSUPPORTED, version, "Deno 2.3.0 veya yenisi gerekli.", remedy
        )
    return DependencyCheck(name, DependencyState.AVAILABLE, version, "Araç çalıştırıldı.")


def check_dependencies(
    should_stop: Callable[[], bool] = lambda: False,
) -> list[DependencyCheck]:
    """Run in a worker/CLI, never on the UI thread. Cancellation is cooperative."""
    python_ok = sys.version_info[:2] == (3, 12)
    checks = [
        DependencyCheck(
            "Python",
            DependencyState.AVAILABLE if python_ok else DependencyState.UNSUPPORTED,
            ".".join(map(str, sys.version_info[:3])),
            "Desteklenen Python sürümü." if python_ok else "Bu sürüm Python 3.12 gerektirir.",
            "" if python_ok else "Python 3.12 ile sanal ortam oluşturun.",
        )
    ]
    for name, distribution in (
        ("PySide6 / Qt", "PySide6"),
        ("yt-dlp", "yt-dlp"),
        ("EJS", "yt-dlp-ejs"),
    ):
        if should_stop():
            return checks
        checks.append(
            _package_check(
                name,
                distribution,
                "Proje kökünde scripts/setup-dev.sh çalıştırın; kilitli paketleri kurar.",
            )
        )
    for name, command, flag, remedy in (
        ("FFmpeg", "ffmpeg", "-version", "Sistem paket yöneticisiyle ffmpeg paketini kurun."),
        ("FFprobe", "ffprobe", "-version", "FFprobe içeren ffmpeg paketini kurun."),
        (
            "Deno",
            "deno",
            "--version",
            "Deno 2.3.0+ kurup PATH'e ekleyin. README içindeki resmî kurulum bağlantısına bakın.",
        ),
    ):
        if should_stop():
            return checks
        checks.append(_command_check(name, command, flag, remedy))
    return checks
