import pytest

from novadownloader.core.exceptions import AnalysisError, AnalysisErrorCode
from novadownloader.services.youtube_url_validator import validate_youtube_url

ID = "BaW_jenozKc"
CANONICAL = f"https://www.youtube.com/watch?v={ID}"


@pytest.mark.parametrize(
    "url",
    [
        f"https://youtube.com/watch?v={ID}",
        f"youtube.com/watch?v={ID}",
        f"www.youtube.com/watch?v={ID}",
        f"http://www.youtube.com/watch?v={ID}&t=5&list=ignored",
        f"https://youtu.be/{ID}?si=tracking",
        f"youtu.be/{ID}/",
        f"https://youtube.com/shorts/{ID}",
        f"https://www.youtube.com/shorts/{ID}/?feature=share",
        f"https://m.youtube.com/watch?v={ID}",
        f"https://music.youtube.com/watch?v={ID}",
        f"  HTTPS://WWW.YOUTUBE.COM/watch?feature=share&v={ID}#t=2  ",
    ],
)
def test_supported_urls_are_normalized(url):
    result = validate_youtube_url(url)
    assert result.video_id == ID
    assert result.normalized_url == CANONICAL


@pytest.mark.parametrize(
    "url",
    [
        "",
        "https://youtube.com",
        "https://youtube.com/watch",
        "https://youtube.com/watch?v=",
        "https://youtube.com/watch?v=short",
        f"https://youtu.be/{ID}/extra",
        f"https://youtube.com/watch?v={ID}&v={ID}",
        "https://youtube.com/playlist?list=abc",
        f"https://youtube.com.evil.test/watch?v={ID}",
        f"https://evil-youtube.com/watch?v={ID}",
        f"https://youtube.com@evil.test/watch?v={ID}",
        f"https://evil.test@youtube.com/watch?v={ID}",
        f"https://youtube.com.:443/watch?v={ID}",
        f"https://youtube.com:443/watch?v={ID}",
        f"https://youtube.com:bad/watch?v={ID}",
        f"ftp://youtube.com/watch?v={ID}",
        f"https://youtube.com/shorts/{ID}/extra",
        f"https://youtu.be/{ID}%2fextra",
        f"https://youtube.com\\@evil.test/watch?v={ID}",
        f"https://youtube.com/watch?v={ID}\nother",
        f"https://youtube.com/wa\ttch?v={ID}",
        f"https://уoutube.com/watch?v={ID}",
        f"https://127.0.0.1/watch?v={ID}",
        f"//youtube.com/watch?v={ID}",
        f"https://www.youtube.com/embed/{ID}",
        "x" * 4097,
        None,
    ],
)
def test_invalid_and_deceptive_urls_are_rejected(url):
    with pytest.raises(AnalysisError) as exc:
        validate_youtube_url(url)
    assert exc.value.code == AnalysisErrorCode.INVALID_URL


def test_excessive_query_fields_are_rejected():
    with pytest.raises(AnalysisError):
        validate_youtube_url(CANONICAL + "&x=1" * 60)
