"""Offline validation and bounded, cancellable orchestration of yt-dlp metadata."""

import importlib.metadata
import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from contextlib import suppress
from threading import Event

from novadownloader.core.dependencies import _command_check, find_deno
from novadownloader.core.exceptions import AnalysisError, AnalysisErrorCode
from novadownloader.core.logging_config import log_failure
from novadownloader.models.video_metadata import VideoMetadata
from novadownloader.services.youtube_url_validator import validate_youtube_url

ANALYSIS_TIMEOUT = 45.0


def ensure_analysis_dependencies() -> str:
    try:
        importlib.metadata.version("yt-dlp")
        importlib.metadata.version("yt-dlp-ejs")
    except importlib.metadata.PackageNotFoundError:
        raise AnalysisError(AnalysisErrorCode.DEPENDENCY) from None
    deno = find_deno()
    if deno is None or not _command_check("Deno", deno, "--version", "").available:
        raise AnalysisError(AnalysisErrorCode.DEPENDENCY)
    return deno


def _stop_process(process: subprocess.Popen) -> None:
    # A JS helper may be a descendant. Terminate only this new process group.
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.communicate(timeout=0.5)
    except subprocess.TimeoutExpired:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.communicate()


def _run_process(command: list[str], cancel: Event, timeout: float) -> str:
    if cancel.is_set():
        raise AnalysisError(AnalysisErrorCode.CANCELLED)
    deadline = time.monotonic() + timeout
    with subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=True,
    ) as process:
        try:
            while True:
                if cancel.is_set():
                    raise AnalysisError(AnalysisErrorCode.CANCELLED)
                if time.monotonic() >= deadline:
                    raise AnalysisError(AnalysisErrorCode.TIMEOUT)
                try:
                    stdout, stderr = process.communicate(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    continue
            if cancel.is_set():
                raise AnalysisError(AnalysisErrorCode.CANCELLED)
            if process.returncode != 0:
                log_failure("Analysis subprocess", stderr or f"exit {process.returncode}")
                raise AnalysisError(AnalysisErrorCode.EXTRACTOR)
            return stdout
        finally:
            # Also clean up descendants if the leader exited before a helper.
            _stop_process(process)


class VideoAnalyzer:
    def __init__(self, dependency_check: Callable[[], str] = ensure_analysis_dependencies):
        self.dependency_check = dependency_check

    def analyze(self, value: str, cancel: Event) -> VideoMetadata:
        source = validate_youtube_url(value)
        if cancel.is_set():
            raise AnalysisError(AnalysisErrorCode.CANCELLED)
        try:
            deno = self.dependency_check()
            output = _run_process(
                [
                    sys.executable,
                    "-m",
                    "novadownloader.workers.analysis_process",
                    source.normalized_url,
                    deno,
                ],
                cancel,
                ANALYSIS_TIMEOUT,
            )
            result = json.loads(output)
            if "error" in result:
                raise AnalysisError(AnalysisErrorCode(result["error"]))
            # Reuse the defensive model parser at the process boundary.
            return VideoMetadata.from_info(result["metadata"], source)
        except AnalysisError:
            raise
        except Exception as error:
            log_failure("Analysis protocol", error)
            raise AnalysisError(AnalysisErrorCode.EXTRACTOR) from None
