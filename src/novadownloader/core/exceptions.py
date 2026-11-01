from enum import StrEnum


class AnalysisErrorCode(StrEnum):
    INVALID_URL = "invalid_url"
    NETWORK = "network"
    TIMEOUT = "timeout"
    REMOVED = "removed"
    PRIVATE = "private"
    RESTRICTED = "restricted"
    EXTRACTOR = "extractor"
    DEPENDENCY = "dependency"
    CANCELLED = "cancelled"


MESSAGES = {
    AnalysisErrorCode.INVALID_URL: (
        "Geçersiz bağlantı",
        "Desteklenen tek bir YouTube video bağlantısı girin.",
    ),
    AnalysisErrorCode.NETWORK: (
        "Bağlantı kurulamadı",
        "İnternet ve ağ erişim izinlerini kontrol edip tekrar deneyin.",
    ),
    AnalysisErrorCode.TIMEOUT: (
        "İstek zaman aşımına uğradı",
        "Bağlantı yavaş olabilir. Biraz sonra tekrar deneyin.",
    ),
    AnalysisErrorCode.REMOVED: (
        "Video kullanılamıyor",
        "Video kaldırılmış veya silinmiş olabilir. Bağlantıyı kontrol edin.",
    ),
    AnalysisErrorCode.PRIVATE: (
        "Video özel",
        "Bu video herkese açık değil. Erişebildiğiniz başka bir bağlantı deneyin.",
    ),
    AnalysisErrorCode.RESTRICTED: (
        "Erişim kısıtlı",
        "Yaş, bölge veya platform erişim kısıtlaması var. Kısıtlamalar aşılmaz.",
    ),
    AnalysisErrorCode.EXTRACTOR: (
        "Video analiz edilemedi",
        "yt-dlp sürümünü ve bağlantıyı kontrol edip tekrar deneyin.",
    ),
    AnalysisErrorCode.DEPENDENCY: (
        "Analiz bağımlılığı eksik",
        "yt-dlp, uyumlu EJS ve Deno 2.3.0+ kurulumunu kontrol edin.",
    ),
    AnalysisErrorCode.CANCELLED: ("Analiz iptal edildi", "Yeni bir bağlantı analiz edebilirsiniz."),
}


class AnalysisError(Exception):
    def __init__(self, code: AnalysisErrorCode):
        self.code = code
        self.title, self.suggestion = MESSAGES[code]
        super().__init__(self.title)

    @property
    def user_message(self) -> str:
        return f"{self.title}. {self.suggestion}"


def classify_analysis_error(error: Exception) -> AnalysisError:
    """yt-dlp wraps transport/extractor exceptions; classify without displaying raw text."""
    if isinstance(error, AnalysisError):
        return error
    text = str(error).lower()
    if isinstance(error, TimeoutError) or any(x in text for x in ("timed out", "timeout")):
        code = AnalysisErrorCode.TIMEOUT
    elif any(x in text for x in ("private video", "this video is private")):
        code = AnalysisErrorCode.PRIVATE
    elif any(x in text for x in ("removed", "deleted", "no longer available", "does not exist")):
        code = AnalysisErrorCode.REMOVED
    elif any(
        x in text
        for x in (
            "sign in",
            "sign-in",
            "login",
            "not a bot",
            "age-restricted",
            "age restricted",
            "not available in your country",
            "geo-restricted",
            "geo restricted",
            "members-only",
            "drm",
            "premium",
            "copyright",
        )
    ):
        code = AnalysisErrorCode.RESTRICTED
    elif any(x in text for x in ("deno", "javascript runtime", "yt-dlp-ejs", "ejs component")):
        code = AnalysisErrorCode.DEPENDENCY
    elif any(
        x in text
        for x in (
            "connection",
            "network",
            "resolve",
            "name resolution",
            "dns",
            "unreachable",
            "proxy",
            "http error 403",
        )
    ):
        code = AnalysisErrorCode.NETWORK
    else:
        code = AnalysisErrorCode.EXTRACTOR
    return AnalysisError(code)
