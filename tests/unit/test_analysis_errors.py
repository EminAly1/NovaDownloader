import pytest

from novadownloader.core.exceptions import AnalysisErrorCode, classify_analysis_error
from novadownloader.core.logging_config import safe_detail


@pytest.mark.parametrize(
    "message,code",
    [
        ("Connection reset by peer", "network"),
        ("Temporary failure in name resolution", "network"),
        ("Request timed out", "timeout"),
        ("Video has been removed", "removed"),
        ("Private video", "private"),
        ("Sign in to confirm your age", "restricted"),
        ("Video not available in your country", "restricted"),
        ("DRM protected", "restricted"),
        ("No JavaScript runtime found (deno)", "dependency"),
        ("Unable to extract data", "extractor"),
    ],
)
def test_friendly_error_classification(message, code):
    failure = classify_analysis_error(RuntimeError(message))
    assert failure.code == AnalysisErrorCode(code)
    assert failure.suggestion
    assert message not in failure.user_message


def test_log_redacts_url_and_authentication():
    detail = safe_detail("failure https://example.test/?token=abc Cookie=secret password=private")
    assert "abc" not in detail and "secret" not in detail and "private" not in detail
    assert len(safe_detail("a" * 10000)) == 4000
