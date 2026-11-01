import pytest

from novadownloader.core.paths import AppPaths


@pytest.fixture(autouse=True)
def clear_xdg(monkeypatch):
    for suffix in ("CONFIG", "DATA", "CACHE", "STATE"):
        monkeypatch.delenv(f"XDG_{suffix}_HOME", raising=False)


def test_xdg_defaults_use_home_without_creating_directories(monkeypatch, tmp_path):
    home = tmp_path / "olmayan-ev"
    monkeypatch.setattr("novadownloader.core.paths.Path.home", lambda: home)
    paths = AppPaths.discover()
    assert paths.config == home / ".config/novadownloader"
    assert paths.data == home / ".local/share/novadownloader"
    assert paths.cache == home / ".cache/novadownloader"
    assert paths.state == home / ".local/state/novadownloader"
    assert not home.exists()


def test_absolute_xdg_overrides_are_respected(monkeypatch, tmp_path):
    for suffix in ("CONFIG", "DATA", "CACHE", "STATE"):
        monkeypatch.setenv(f"XDG_{suffix}_HOME", str(tmp_path / suffix))
    paths = AppPaths.discover()
    assert paths.config == tmp_path / "CONFIG/novadownloader"
    assert paths.data == tmp_path / "DATA/novadownloader"
    assert paths.cache == tmp_path / "CACHE/novadownloader"
    assert paths.state == tmp_path / "STATE/novadownloader"


@pytest.mark.parametrize("value", ["", "relative/path", "~/config"])
def test_relative_and_empty_xdg_paths_are_ignored(monkeypatch, tmp_path, value):
    monkeypatch.setattr("novadownloader.core.paths.Path.home", lambda: tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", value)
    assert AppPaths.discover().config == tmp_path / ".config/novadownloader"
