"""XDG base directories without side effects during import."""

import os
from dataclasses import dataclass
from pathlib import Path


def _xdg_path(variable: str, fallback: Path) -> Path:
    value = os.environ.get(variable)
    # The XDG specification says relative values must be ignored.
    return Path(value) if value and Path(value).is_absolute() else fallback


@dataclass(frozen=True, slots=True)
class AppPaths:
    config: Path
    data: Path
    cache: Path
    state: Path

    @classmethod
    def discover(cls) -> "AppPaths":
        home = Path.home()
        return cls(
            config=_xdg_path("XDG_CONFIG_HOME", home / ".config") / "novadownloader",
            data=_xdg_path("XDG_DATA_HOME", home / ".local/share") / "novadownloader",
            cache=_xdg_path("XDG_CACHE_HOME", home / ".cache") / "novadownloader",
            state=_xdg_path("XDG_STATE_HOME", home / ".local/state") / "novadownloader",
        )
