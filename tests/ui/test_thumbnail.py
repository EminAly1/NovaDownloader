from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QTimer, Signal
from PySide6.QtGui import QColor, QImage
from PySide6.QtNetwork import QNetworkReply, QNetworkRequest

from novadownloader.ui.thumbnail import MAX_THUMBNAIL_BYTES, ThumbnailLabel


def png_bytes():
    array = QByteArray()
    buffer = QBuffer(array)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image = QImage(32, 18, QImage.Format.Format_RGB32)
    image.fill(QColor("blue"))
    assert image.save(buffer, "PNG")
    return bytes(array)


class FakeReply(QObject):
    readyRead = Signal()
    finished = Signal()

    def __init__(self, data, error=QNetworkReply.NetworkError.NoError):
        super().__init__()
        self.data = data
        self._error = error
        self.aborted = False

    def readAll(self):
        data, self.data = self.data, b""
        return QByteArray(data)

    def error(self):
        return self._error

    def attribute(self, key):
        assert key == QNetworkRequest.Attribute.HttpStatusCodeAttribute
        return 200

    def setReadBufferSize(self, size):
        pass

    def abort(self):
        self.aborted = True


def test_asynchronous_thumbnail_success_and_failure(qtbot, monkeypatch):
    widget = ThumbnailLabel()
    qtbot.addWidget(widget)
    replies = []
    data_items = [png_bytes(), b"corrupt image", b"network error"]

    def get(request):
        assert request.url().host() == "i.ytimg.com"
        reply = FakeReply(data_items[len(replies)])
        if len(replies) == 2:
            reply._error = QNetworkReply.NetworkError.ConnectionRefusedError
        replies.append(reply)
        QTimer.singleShot(0, reply.finished.emit)
        return reply

    monkeypatch.setattr(widget.manager, "get", get)
    widget.load_url("https://i.ytimg.com/image.jpg")
    qtbot.waitUntil(lambda: widget.reply is None)
    assert not widget.pixmap().isNull()
    for _ in range(2):
        widget.load_url("https://i.ytimg.com/image.jpg")
        qtbot.waitUntil(lambda: widget.reply is None)
        assert widget.text() == "Önizleme yüklenemedi"


def test_thumbnail_limits_cancellation_and_stale_callback(qtbot, monkeypatch):
    widget = ThumbnailLabel()
    qtbot.addWidget(widget)
    reply = FakeReply(b"x" * (MAX_THUMBNAIL_BYTES + 1))
    monkeypatch.setattr(widget.manager, "get", lambda request: reply)
    widget.load_url("https://i.ytimg.com/image.jpg")
    generation = widget.generation
    widget._read(reply, generation)
    assert reply.aborted and widget.reply is None
    assert widget.text() == "Önizleme yüklenemedi"
    widget.load_url(None)
    widget._finish(reply, generation)
    assert widget.text() == "Önizleme yok"


def test_thumbnail_timeout_and_disallowed_url(qtbot, monkeypatch):
    widget = ThumbnailLabel()
    qtbot.addWidget(widget)
    monkeypatch.setattr(widget.manager, "get", lambda request: FakeReply(b""))
    widget.load_url("file:///tmp/image.jpg")
    assert widget.reply is None
    widget.load_url("https://i.ytimg.com/image.jpg")
    widget._timeout()
    assert widget.reply is None
    assert widget.text() == "Önizleme yüklenemedi"
