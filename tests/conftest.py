import json
import os
from pathlib import Path

import pytest

from novadownloader.models.media_format import parse_formats

# A real desktop run must retain Qt's native platform selection.
# Only the automated test process opts into headless rendering.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def raw_formats():
    return json.loads((Path(__file__).parent / "fixtures/formats.json").read_text())


@pytest.fixture
def media_formats(raw_formats):
    return parse_formats(raw_formats)
