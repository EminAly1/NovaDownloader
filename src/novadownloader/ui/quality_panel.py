"""Selection widgets consume service models; no bitrate or size math lives here."""

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
)

from novadownloader.models.download_request import DownloadRequest
from novadownloader.models.format_selection import SelectionKind, SizeCertainty
from novadownloader.services.format_selector import QUALITY_NAMES, codec_family
from novadownloader.services.selection_service import selection_catalog
from novadownloader.ui.components import EmptyStateWidget, text_label
from novadownloader.ui.icons import icon
from novadownloader.ui.theme import COLORS, SPACE


def size_text(estimate):
    return (
        f"Boyut: {estimate.label}" if estimate.certainty == SizeCertainty.EXACT else estimate.label
    )


def option_title(choice):
    if choice.kind == SelectionKind.VIDEO:
        resolution = f"{choice.resolution}p" if choice.resolution else "Çözünürlük bilinmiyor"
        name = QUALITY_NAMES.get(choice.resolution)
        return f"{resolution} — {name}" if name else resolution
    return f"{(choice.output_ext or 'Format bilinmiyor').upper()} — " + (
        "Dönüştürme" if choice.requires_conversion else "Orijinal ses"
    )


def option_detail(choice):
    codec = codec_family(choice.codec).upper()
    codec = {"H264": "H.264", "UNKNOWN": "Codec bilinmiyor"}.get(codec, codec)
    if choice.kind == SelectionKind.VIDEO:
        fps = f"{choice.fps:g} FPS" if choice.fps else "FPS bilinmiyor"
        return f"{(choice.output_ext or 'Kapsayıcı bilinmiyor').upper()} · {fps} · {codec}"
    source = choice.audio
    rate = source.abr or source.tbr
    bitrate = f"{rate:g} kbps" if rate else "Bit hızı bilinmiyor"
    if choice.requires_conversion:
        return f"Hedef {choice.target_audio_bitrate} kbps · Kaynak: {codec} / {bitrate}"
    return f"{codec} · {bitrate}"


class MediaTypeSelector(QFrame):
    mode_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("segmented")
        self.group = QButtonGroup(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self.buttons = {}
        for mode, label, symbol in (
            (SelectionKind.VIDEO, "Video İndir", "video"),
            (SelectionKind.AUDIO, "Sadece Ses İndir", "audio"),
        ):
            button = QPushButton(label)
            button.setObjectName("segment")
            button.setIcon(icon(symbol))
            button.setCheckable(True)
            button.setAccessibleName(label)
            button.installEventFilter(self)
            self.group.addButton(button)
            self.buttons[mode] = button
            button.clicked.connect(lambda checked=False, mode=mode: self.mode_changed.emit(mode))
            layout.addWidget(button, 1)
        self.buttons[SelectionKind.VIDEO].setChecked(True)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress and event.key() in (
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
        ):
            mode = next(mode for mode, button in self.buttons.items() if button is not watched)
            self.buttons[mode].setFocus()
            self.buttons[mode].click()
            return True
        return super().eventFilter(watched, event)


class QualityOptionCard(QPushButton):
    def __init__(self, choice, parent=None):
        super().__init__(parent)
        self.choice = choice
        self.setObjectName("qualityCard")
        self.setCheckable(True)
        self.setEnabled(choice.available)
        self.setProperty("available", choice.available)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)
        self.marker = text_label("○")
        self.marker.setFixedWidth(20)
        layout.addWidget(self.marker)
        left = QVBoxLayout()
        left.setSpacing(4)
        self.title = text_label(option_title(choice), "cardTitle")
        self.detail = text_label(option_detail(choice), "subtitle")
        left.addWidget(self.title)
        left.addWidget(self.detail)
        stream = choice.video or choice.audio
        extras = [
            value for value in (stream.language, stream.dynamic_range, stream.format_note) if value
        ]
        if extras:
            left.addWidget(text_label(" · ".join(extras), "footer"))
        if not choice.available:
            left.addWidget(text_label(choice.unavailable_reason, "subtitle"))
        layout.addLayout(left, 3)
        right = QVBoxLayout()
        right.setSpacing(4)
        self.size_label = text_label(size_text(choice.download_size))
        self.size_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        right.addWidget(self.size_label)
        if choice.recommended:
            badge = text_label("Önerilen", "badge")
            badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
            right.addWidget(badge, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(right, 2)
        # The whole row is one accessible, keyboard-operable button.
        for label in self.findChildren(type(self.title)):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAccessibleName(
            f"{self.title.text()}. {self.detail.text()}. {self.size_label.text()}."
            + (" Önerilen." if choice.recommended else "")
            + choice.unavailable_reason
        )
        self.setToolTip(choice.display_name + "\n" + "\n".join(choice.notes))
        self.toggled.connect(lambda checked: self.marker.setText("●" if checked else "○"))

    def focusInEvent(self, event):
        super().focusInEvent(event)
        # Rows are added dynamically; allow Qt to finish layout before scrolling.
        QTimer.singleShot(0, self, self._ensure_visible)

    def _ensure_visible(self):
        ancestor = self.parentWidget()
        while ancestor is not None:
            if isinstance(ancestor, QScrollArea):
                ancestor.ensureWidgetVisible(self, 8, 8)
                break
            ancestor = ancestor.parentWidget()

    def sizeHint(self):
        return self.layout().sizeHint()

    def minimumSizeHint(self):
        return self.layout().minimumSize()


class QualitySelectionPanel(QFrame):
    selection_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.metadata = None
        self.catalog = None
        self.mode = SelectionKind.VIDEO
        self.remembered = {}
        self.selected = None
        self.cards = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        self.media_type = MediaTypeSelector()
        self.media_type.mode_changed.connect(self.set_mode)
        layout.addWidget(self.media_type)
        heading = QHBoxLayout()
        heading.addWidget(text_label("Kalitenizi seçin", "sectionHeading"), 1)
        self.count_label = text_label("", "subtitle")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        heading.addWidget(self.count_label, 1)
        layout.addLayout(heading)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(SPACE)
        layout.addLayout(self.rows)
        self.empty = EmptyStateWidget(
            "Uygun format bulunamadı.",
            "Bu video için kullanılabilir bir seçenek bulunmuyor.",
            "info",
        )
        layout.addWidget(self.empty)
        self.group = QButtonGroup(self)

    def clear(self):
        self.metadata = self.catalog = self.selected = None
        self.remembered.clear()
        self.mode = SelectionKind.VIDEO
        self.media_type.buttons[self.mode].setChecked(True)
        self._render()
        self.hide()

    def set_metadata(self, metadata):
        self.metadata = metadata
        self.catalog = selection_catalog(metadata)
        self.remembered.clear()
        self.mode = SelectionKind.VIDEO
        self.media_type.buttons[self.mode].setChecked(True)
        self._render()
        self.show()

    def set_mode(self, mode):
        self.mode = mode
        self.media_type.buttons[mode].setChecked(True)
        self._render()

    def _render(self):
        for card in self.cards:
            self.group.removeButton(card)
            self.rows.removeWidget(card)
            card.hide()
            card.deleteLater()
        self.cards = []
        choices = (
            ()
            if self.catalog is None
            else (
                self.catalog.video_options
                if self.mode == SelectionKind.VIDEO
                else self.catalog.audio_options
            )
        )
        selected = self.remembered.get(self.mode)
        if selected not in choices or (selected is not None and not selected.available):
            selected = next(
                (choice for choice in choices if choice.recommended and choice.available), None
            )
            if selected is None:
                selected = next((choice for choice in choices if choice.available), None)
        for choice in choices:
            card = QualityOptionCard(choice)
            self.cards.append(card)
            self.group.addButton(card)
            card.setChecked(choice == selected)
            card.clicked.connect(lambda checked=False, choice=choice: self._choose(choice))
            card.installEventFilter(self)
            self.rows.addWidget(card)
        self.count_label.setText(f"{len(choices)} seçenek")
        self.empty.setVisible(not choices)
        self.empty.description.setText(
            "Bu video için "
            + ("video" if self.mode == SelectionKind.VIDEO else "ayrı ses")
            + " formatı bulunamadı. Diğer modu deneyebilirsiniz."
        )
        self._choose(selected)

    def _choose(self, choice):
        self.selected = choice
        self.remembered[self.mode] = choice
        request = (
            DownloadRequest.from_selection(self.metadata, choice)
            if choice and self.metadata
            else None
        )
        self.selection_changed.emit(request)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress and event.key() in (
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
            Qt.Key.Key_Home,
            Qt.Key.Key_End,
        ):
            enabled = [card for card in self.cards if card.isEnabled()]
            if watched in enabled:
                index = enabled.index(watched)
                if event.key() == Qt.Key.Key_Home:
                    index = 0
                elif event.key() == Qt.Key.Key_End:
                    index = len(enabled) - 1
                else:
                    index = (index + (1 if event.key() == Qt.Key.Key_Down else -1)) % len(enabled)
                enabled[index].setFocus()
                enabled[index].click()
                return True
        return super().eventFilter(watched, event)


class DownloadSummaryCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.request = None
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(SPACE)
        layout.addWidget(text_label("Seçiminiz", "cardTitle"))
        self.summary_label = text_label()
        self.size_label = text_label("", "subtitle")
        self.processing_label = text_label("", "subtitle")
        for label in (self.summary_label, self.size_label, self.processing_label):
            layout.addWidget(label)
        self.details_button = QPushButton("Teknik ayrıntılar")
        self.details_button.setCheckable(True)
        self.details_button.setAccessibleName("Seçili formatın teknik ayrıntılarını göster")
        self.technical = text_label("", "technical")
        self.technical.hide()
        self.details_button.toggled.connect(self.technical.setVisible)
        layout.addWidget(self.details_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.technical)
        self.download_button = QPushButton("İndirmeyi başlat")
        self.download_button.setIcon(icon("download", COLORS["muted"]))
        self.download_button.setEnabled(False)
        self.download_button.setToolTip("İndirme özelliği sonraki fazda etkinleştirilecek.")
        layout.addWidget(self.download_button)
        layout.addWidget(
            text_label("İndirme özelliği sonraki fazda etkinleştirilecek.", "subtitle")
        )
        self.set_request(None)

    def set_request(self, request):
        self.request = request
        self.download_button.setEnabled(False)
        self.details_button.setEnabled(request is not None)
        self.details_button.setChecked(False)
        if request is None:
            self.summary_label.setText("Devam etmek için kullanılabilir bir kalite seçin.")
            self.size_label.setText("Boyut bilinmiyor")
            self.processing_label.clear()
            self.technical.clear()
            return
        choice = request.selection
        kind = "Video" if choice.kind == SelectionKind.VIDEO else "Ses"
        self.summary_label.setText(f"{kind} · {option_title(choice)} · {option_detail(choice)}")
        self.size_label.setText("Aktarım: " + size_text(choice.download_size))
        if choice.requires_conversion:
            processing = (
                f"FFmpeg ile MP3 dönüşümü gerekir. Çıktı: {choice.output_size.label}. "
                "Hedef bit hızı kaynak kalitesini artırmaz."
            )
        elif choice.requires_merge:
            processing = "Ses birleştirilecek · FFmpeg gerekir. Nihai dosya boyutu değişebilir."
        elif choice.requires_remux:
            processing = "FFmpeg ile kapsayıcı işlemi gerekir. Nihai dosya boyutu değişebilir."
        else:
            processing = (
                "Ses dahil · Tek dosya."
                if choice.kind == SelectionKind.VIDEO
                else "Orijinal ses kalitesi korunur."
            )
        self.processing_label.setText(processing)
        streams = [stream for stream in (choice.video, choice.audio) if stream]
        technical = [
            f"Format ID: {choice.format_expression}",
            f"Çıktı boyutu: {choice.output_size.label}",
        ]
        technical.extend(
            f"{stream.format_id} · {stream.vcodec or '?'} / {stream.acodec or '?'} · "
            f"{stream.protocol or 'Protokol bilinmiyor'}"
            for stream in streams
        )
        self.technical.setText("\n".join(technical))
