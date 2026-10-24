"""Premium monochrome PyQt6 workspace shell."""
from __future__ import annotations
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QStackedWidget, QTextEdit, QLineEdit, QMessageBox,
    QFrame, QSplitter, QComboBox, QPlainTextEdit)
from src.core.universal_parser import UniversalParser
from src.core.hybrid_matrix import HybridMatrix, StudyChunk, Citation
from src.core.cognitive_scheduler import CognitiveScheduler
from src.core.feynman_sandbox import FeynmanSandbox
from src.gui.modules.attention_feed import AttentionFeed
from src.gui.modules.kinetic_canvas import ParticleOverlay, validation_chime

STYLESHEET = """
QMainWindow,QWidget { background:#060607; color:#E4E4E7; font-family:'Segoe UI'; font-size:13px; }
QFrame#Panel,QFrame#StudyCard { background:#0D0D10; border:1px solid #1A1A1E; border-radius:12px; }
QLabel#Title { font-size:24px; font-weight:700; color:#E4E4E7; }
QLabel#Subtitle,QLabel#CardEyebrow { color:#8A8A93; letter-spacing:1px; }
QPushButton { background:#0D0D10; color:#E4E4E7; border:1px solid #28282E; border-radius:8px; padding:10px 14px; }
QPushButton:hover { border-color:#00F0FF; color:#00F0FF; background:#0A2A35; }
QPushButton:pressed { background:#123A45; }
QLineEdit,QTextEdit,QPlainTextEdit,QComboBox { background:#08080A; border:1px solid #28282E; border-radius:8px; padding:8px; selection-background-color:#0A2A35; }
QScrollArea { border:0; }
QScrollBar:vertical { background:#08080A; width:10px; margin:0; }
QScrollBar::handle:vertical { background:#34343C; border-radius:5px; min-height:25px; }
QScrollBar::handle:vertical:hover { background:#00A8B5; }
"""
class StudioShell(QMainWindow):
    def __init__(self, data_dir: str | Path, executor=None):
        super().__init__()
        self.data_dir = Path(data_dir); self.data_dir.mkdir(parents=True, exist_ok=True)
        self.executor = executor
        self.parser = UniversalParser()
        self.matrix = HybridMatrix()
        self.scheduler = CognitiveScheduler(self.data_dir / "data_vault.db")
        self.sandbox = FeynmanSandbox()
        self.setWindowTitle("OmniStudy AI")
        self.resize(1440, 900); self.setMinimumSize(960, 640)
        self.setStyleSheet(STYLESHEET)
        self._build_ui()
        self.particles = ParticleOverlay(self); self.particles.setGeometry(self.rect()); self.particles.hide()

    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(22,18,22,18); root.setSpacing(16)
        header = QHBoxLayout()
        brand = QVBoxLayout()
        brand.addWidget(QLabel("OMNISTUDY / LOCAL WORKSPACE", objectName="Subtitle"))
        brand.addWidget(QLabel("Your knowledge, in motion.", objectName="Title"))
        header.addLayout(brand); header.addStretch()
        self.status_label = QLabel("LOCAL MODE  •  READY"); header.addWidget(self.status_label)
        root.addLayout(header)
        nav = QHBoxLayout()
        self.pages = QStackedWidget()
        for name in ("Library", "Study Feed", "Recall", "Feynman Lab"):
            btn = QPushButton(name); btn.clicked.connect(lambda checked=False, n=name: self._navigate(n))
            nav.addWidget(btn)
        import_btn = QPushButton("＋ Import document"); import_btn.clicked.connect(self.import_document); nav.addWidget(import_btn)
        root.addLayout(nav)
        self.library_page = self._library_page()
        self.feed_page = AttentionFeed()
        self.recall_page = self._recall_page()
        self.feynman_page = self._feynman_page()
        for page in (self.library_page, self.feed_page, self.recall_page, self.feynman_page):
            self.pages.addWidget(page)
        root.addWidget(self.pages, 1)
        self._navigate("Library")

    def _panel(self, layout=None):
        panel = QFrame(); panel.setObjectName("Panel")
        if layout is not None:
            panel.setLayout(layout)
        return panel

    def _library_page(self):
        page = QWidget(); layout = QHBoxLayout(page); layout.setContentsMargins(0,0,0,0)
        left_layout = QVBoxLayout(); left_layout.addWidget(QLabel("SOURCE LIBRARY", objectName="Subtitle"))
        self.sources = QTextEdit(); self.sources.setReadOnly(True); self.sources.setPlaceholderText("Imported source documents and extraction summaries appear here.")
        left_layout.addWidget(self.sources)
        left = self._panel(left_layout)
        right_layout = QVBoxLayout(); right_layout.addWidget(QLabel("HYBRID SEARCH", objectName="Subtitle"))
        self.search_input = QLineEdit(); self.search_input.setPlaceholderText("Search concepts, definitions, or phrases…")
        self.search_input.returnPressed.connect(self.search)
        right_layout.addWidget(self.search_input)
        search_btn = QPushButton("Search locally"); search_btn.clicked.connect(self.search); right_layout.addWidget(search_btn)
        self.search_results = QTextEdit(); self.search_results.setReadOnly(True); right_layout.addWidget(self.search_results,1)
        right = self._panel(right_layout)
        layout.addWidget(left, 1); layout.addWidget(right, 1)
        return page

    def _recall_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        layout.addWidget(QLabel("SPACED REPETITION", objectName="Subtitle"))
        self.recall_text = QTextEdit(); self.recall_text.setReadOnly(True); layout.addWidget(self.recall_text,1)
        row = QHBoxLayout()
        self.review_mode = QComboBox(); self.review_mode.addItems(["leitner", "fsrs"]); row.addWidget(self.review_mode)
        refresh = QPushButton("Refresh due cards"); refresh.clicked.connect(self.refresh_due); row.addWidget(refresh)
        layout.addLayout(row)
        self.refresh_due()
        return self._panel(layout)

    def _feynman_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        layout.addWidget(QLabel("FEYNMAN LAB / EXPLAIN IT, THEN TEST IT", objectName="Subtitle"))
        self.code_input = QPlainTextEdit(); self.code_input.setPlaceholderText("print(2 ** 10)\\n# Or write a short Python explanation / calculation.")
        self.code_input.setPlainText("print(2 ** 10)")
        layout.addWidget(self.code_input,2)
        run = QPushButton("Run in isolated subprocess"); run.clicked.connect(self.run_code); layout.addWidget(run)
        self.code_output = QPlainTextEdit(); self.code_output.setReadOnly(True); layout.addWidget(self.code_output,1)
        return self._panel(layout)

    def _navigate(self, name):
        index = {"Library":0, "Study Feed":1, "Recall":2, "Feynman Lab":3}[name]
        self.pages.setCurrentIndex(index)

    def import_document(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Import study source", "",
            "Supported documents (*.pdf *.txt *.md *.png *.jpg *.jpeg)")
        if not filename: return
        self.status_label.setText("IMPORTING…")
        if self.executor:
            future = self.executor.submit(self.parser.parse, filename)
            future.add_done_callback(lambda f: self._import_finished(filename, f))
        else:
            try: self._ingest(filename, self.parser.parse(filename))
            except Exception as exc: self._show_error("Import failed", str(exc))

    def _import_finished(self, filename, future):
        from PyQt6.QtCore import QTimer
        def apply():
            try: self._ingest(filename, future.result())
            except Exception as exc: self._show_error("Import failed", str(exc))
        QTimer.singleShot(0, apply)

    def _ingest(self, filename, pages):
        path = Path(filename)
        all_words = 0
        for page in pages:
            words = page["Word"]; all_words += len(words)
            text = " ".join(w["text"] for w in words)
            if not text.strip():
                continue
            citation = HybridMatrix.citation_from_page(path.name, page["page_num"], words, 2000, 3000)
            chunk = StudyChunk(f"{path.name}:{page['page_num']}", text, citation)
            try: self.matrix.add(chunk)
            except ValueError: pass
        self.sources.append(f"• {path.name} — {len(pages)} page(s), {all_words} extracted token(s)")
        combined = "\n\n".join(" ".join(w["text"] for w in p["Word"]) for p in pages)
        self.feed_page.set_text(combined)
        self.status_label.setText("LOCAL MODE  •  IMPORT COMPLETE")
        self._navigate("Study Feed")

    def search(self):
        query = self.search_input.text().strip()
        try:
            results = self.matrix.search(query, 10)
            if not results:
                self.search_results.setPlainText("No matching indexed text. Import a text-based PDF or document first.")
                return
            lines = []
            for r in results:
                c = r["citation"]
                lines.append(f"{r['score']:.3f}  ·  {c['source_name']}  ·  page {c['page_num']}\\n"
                             f"{r['text']}\\nNormalized source rectangle: {c['rect']}\\n")
            self.search_results.setPlainText("\\n".join(lines))
        except Exception as exc: self._show_error("Search failed", str(exc))

    def refresh_due(self):
        try:
            cards = self.scheduler.due_cards()
            self.recall_text.setPlainText("\\n\\n".join(
                f"{i+1}. {c['front']}\\nAnswer: {c['back']}\\nSource: {c['source_name']} · page {c['page_num']} · Box {c['box']}"
                for i,c in enumerate(cards)) or "You're all caught up. Add cards through the scheduler API to start a deck.")
        except Exception as exc: self.recall_text.setPlainText(f"Could not load cards: {exc}")

    def run_code(self):
        self.code_output.setPlainText("Running…")
        source = self.code_input.toPlainText()
        if self.executor:
            future = self.executor.submit(self.sandbox.run, source)
            future.add_done_callback(self._code_finished)
        else:
            self._show_execution(self.sandbox.run(source))

    def _code_finished(self, future):
        from PyQt6.QtCore import QTimer
        def apply():
            try: self._show_execution(future.result())
            except Exception as exc: self._show_error("Execution failed", str(exc))
        QTimer.singleShot(0, apply)

    def _show_execution(self, result):
        self.code_output.setPlainText(f"EXIT CODE: {result.returncode}\\n\\nSTDOUT\\n{result.stdout}\\nSTDERR\\n{result.stderr}")
        if result.ok:
            self.particles.setGeometry(self.rect()); self.particles.burst()
            validation_chime()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "particles"): self.particles.setGeometry(self.rect())

    def _show_error(self, title, message):
        self.status_label.setText("ACTION FAILED  •  SEE DETAILS")
        QMessageBox.warning(self, title, message)
