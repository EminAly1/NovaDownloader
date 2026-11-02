"""Asynchronous bounded thumbnail fetches; no insecure TLS fallback."""

import os
from urllib.parse import unquote, urlsplit

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QImageReader, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkProxy, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QLabel

from novadownloader.core.logging_config import log_failure
from novadownloader.models.video_metadata import safe_thumbnail_url

MAX_THUMBNAIL_BYTES = 2 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000


class ThumbnailLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._image = None
        self.setFixedSize(224, 126)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setAccessibleName("Video küçük resmi")
        self.manager = QNetworkAccessManager(self)
        self.proxy_invalid = False
        # Qt does not consistently consume HTTPS_PROXY; preserve the cloud proxy route explicitly.
        proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        if proxy_url:
            try:
                parsed = urlsplit(proxy_url)
                if parsed.scheme != "http" or not parsed.hostname:
                    raise ValueError("Unsupported proxy configuration")
                proxy = QNetworkProxy(
                    QNetworkProxy.ProxyType.HttpProxy, parsed.hostname, parsed.port or 8080
                )
                proxy.setUser(unquote(parsed.username or ""))
                proxy.setPassword(unquote(parsed.password or ""))
                self.manager.setProxy(proxy)
            except ValueError:
                self.proxy_invalid = True
                log_failure("Thumbnail", "invalid proxy configuration")
        self.reply = None
        self.data = bytearray()
        self.generation = 0
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._timeout)
        self.load_url(None)

    def cancel(self) -> None:
        self.generation += 1
        self.timer.stop()
        if self.reply is not None:
            reply, self.reply = self.reply, None
            reply.abort()
            reply.deleteLater()
        self.data.clear()

    def load_url(self, url: str | None) -> None:
        self.cancel()
        self._image = None
        self.clear()
        self.setText("Önizleme yok")
        if not safe_thumbnail_url(url):
            return
        if self.proxy_invalid:
            self.setText("Önizleme yüklenemedi")
            return
        self.setText("Görsel yükleniyor…")
        request = QNetworkRequest(QUrl(url))
        request.setTransferTimeout(8000)
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.ManualRedirectPolicy,
        )
        self.reply = self.manager.get(request)
        self.reply.setReadBufferSize(64 * 1024)
        generation, reply = self.generation, self.reply
        reply.readyRead.connect(lambda: self._read(reply, generation))
        reply.finished.connect(lambda: self._finish(reply, generation))
        self.timer.start(10_000)

    def _timeout(self) -> None:
        self.cancel()
        self.setText("Önizleme yüklenemedi")
        log_failure("Thumbnail", "request timeout")

    def _read(self, reply, generation: int) -> None:
        if generation != self.generation or reply is not self.reply:
            return
        self.data.extend(bytes(reply.readAll()))
        if len(self.data) > MAX_THUMBNAIL_BYTES:
            self.cancel()
            self.setText("Önizleme yüklenemedi")
            log_failure("Thumbnail", "image exceeds byte limit")

    def _finish(self, reply, generation: int) -> None:
        if generation != self.generation or reply is not self.reply:
            return
        self._read(reply, generation)
        if reply is not self.reply:
            return
        self.timer.stop()
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if reply.error() != QNetworkReply.NetworkError.NoError or status != 200:
            log_failure("Thumbnail", f"network error {reply.error().name}, HTTP {status}")
            self.setText("Önizleme yüklenemedi")
        elif not self._show_image(bytes(self.data)):
            log_failure("Thumbnail", "invalid image")
            self.setText("Önizleme yüklenemedi")
        self.reply = None
        self.data.clear()
        reply.deleteLater()

    def _show_image(self, data: bytes) -> bool:
        buffer = QBuffer()
        buffer.setData(QByteArray(data))
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        reader = QImageReader(buffer)
        if bytes(reader.format()).lower() not in {b"jpeg", b"jpg", b"png", b"webp"}:
            return False
        size = reader.size()
        if not size.isValid() or size.width() * size.height() > MAX_IMAGE_PIXELS:
            return False
        reader.setScaledSize(size.scaled(QSize(448, 252), Qt.AspectRatioMode.KeepAspectRatio))
        image = reader.read()
        if image.isNull():
            return False
        self._image = QPixmap.fromImage(image)
        self._refresh_pixmap()
        return True

    def _refresh_pixmap(self):
        if self._image is not None:
            ratio = self.devicePixelRatioF()
            pixmap = self._image.scaled(
                self.size() * ratio,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            pixmap.setDevicePixelRatio(ratio)
            self.setPixmap(pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_pixmap()
