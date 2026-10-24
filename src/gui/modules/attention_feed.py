"""Lazy chunk feed with bounded widget creation and smooth scroll velocity."""
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame, QSizePolicy
import re

def chunk_text(text: str, max_words: int = 150) -> list[str]:
    max_words = max(1, min(150, int(max_words)))
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    result = []
    for paragraph in paragraphs:
        words = paragraph.split()
        for start in range(0, len(words), max_words):
            result.append(" ".join(words[start:start+max_words]))
    return result

class AttentionFeed(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._chunks = []
        self._rendered = set()
        self._velocity = 0.0
        self._last_y = None
        self.scroll = QScrollArea(self); self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content = QWidget(); self.layout = QVBoxLayout(self.content)
        self.layout.setContentsMargins(12,12,12,12); self.layout.setSpacing(12)
        self.scroll.setWidget(self.content)
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.addWidget(self.scroll)
        self.timer = QTimer(self); self.timer.timeout.connect(self._animate); self.timer.start(16)
        self.scroll.verticalScrollBar().valueChanged.connect(self._lazy_render)

    def set_text(self, text: str):
        self._chunks = chunk_text(text)
        self._rendered.clear()
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget: widget.deleteLater()
        # Spacer placeholders maintain scroll geometry while actual cards are instantiated on demand.
        for i, chunk in enumerate(self._chunks):
            placeholder = QWidget(); placeholder.setFixedHeight(124)
            placeholder.setProperty("chunk_index", i)
            self.layout.addWidget(placeholder)
        self.layout.addStretch(1)
        self._lazy_render()

    def _lazy_render(self, *_):
        bar = self.scroll.verticalScrollBar()
        top, bottom = bar.value()-500, bar.value()+self.scroll.viewport().height()+500
        for i in range(len(self._chunks)):
            item = self.layout.itemAt(i)
            if not item: continue
            widget = item.widget()
            if not widget: continue
            y = widget.mapTo(self.content, QPoint(0,0)).y()
            if top <= y <= bottom and i not in self._rendered:
                card = QFrame(); card.setObjectName("StudyCard")
                card_layout = QVBoxLayout(card)
                label = QLabel(f"STUDY NOTE  /  {i+1:03d}")
                label.setObjectName("CardEyebrow")
                body = QLabel(self._chunks[i]); body.setWordWrap(True)
                body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                card_layout.addWidget(label); card_layout.addWidget(body)
                card.setMinimumHeight(110); card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
                self.layout.replaceWidget(widget, card); widget.deleteLater()
                self._rendered.add(i)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        self._velocity += -delta * 0.6
        event.accept()

    def _animate(self):
        if abs(self._velocity) < .4:
            self._velocity = 0; return
        bar = self.scroll.verticalScrollBar()
        bar.setValue(int(bar.value() + self._velocity))
        self._velocity *= .88
