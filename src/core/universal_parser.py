"""Local-first document ingestion with coordinate-preserving text extraction."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import json
import re

DPI = 144
SUPPORTED = {".pdf", ".txt", ".md", ".png", ".jpg", ".jpeg"}

@dataclass
class WordToken:
    font_size: int
    length: int
    text: str
    orientation: str
    x: int
    y: int

@dataclass
class ParsedPage:
    page_num: int
    dpi: int
    Word: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

class UniversalParser:
    """Extract words and page coordinates. PDF extraction uses PyMuPDF when available."""
    def parse(self, filename: str | Path) -> list[dict[str, Any]]:
        path = Path(filename)
        if not path.is_file():
            raise FileNotFoundError(path)
        ext = path.suffix.lower()
        if ext not in SUPPORTED:
            raise ValueError(f"Unsupported file type: {ext}")
        if ext == ".pdf":
            pages = self._pdf(path)
        elif ext in {".txt", ".md"}:
            pages = self._text(path.read_text(encoding="utf-8", errors="replace"))
        else:
            pages = self._image(path)
        return [p.to_dict() for p in pages]

    def json_stream(self, filename: str | Path) -> str:
        return json.dumps(self.parse(filename), ensure_ascii=False)

    @staticmethod
    def _token(text: str, size: float, x: float, y: float) -> dict[str, Any]:
        return {"font-size": max(1, int(round(size))), "length": len(text),
                "text": text, "orientation": "U", "x": max(0, int(round(x))),
                "y": max(0, int(round(y)))}

    def _pdf(self, path: Path) -> list[ParsedPage]:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PDF parsing requires PyMuPDF (fitz).") from exc
        out = []
        with fitz.open(path) as doc:
            for index, page in enumerate(doc, start=1):
                words = []
                # PyMuPDF coordinates are points; scale to the requested 144-DPI canvas.
                scale = DPI / 72.0
                for block in page.get_text("dict").get("blocks", []):
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            size = span.get("size", 10)
                            for item in re.finditer(r"\S+", span.get("text", "")):
                                text = item.group(0)
                                bbox = span.get("bbox", (0, 0, 0, 0))
                                words.append(self._token(text, size, bbox[0] * scale, bbox[1] * scale))
                out.append(ParsedPage(index, DPI, words))
        return out

    def _text(self, text: str) -> list[ParsedPage]:
        pages = []
        for page_num, page_text in enumerate(text.split("\f"), start=1):
            words = []
            for line_num, line in enumerate(page_text.splitlines()):
                x = 0
                for word in re.findall(r"\S+", line):
                    words.append(self._token(word, 12, x * 8, line_num * 20))
                    x += len(word) + 1
            pages.append(ParsedPage(page_num, DPI, words))
        return pages or [ParsedPage(1, DPI, [])]

    def _image(self, path: Path) -> list[ParsedPage]:
        # OCR is optional and local. Preserve the image as the source artifact even when
        # no OCR engine is installed; never invent text or coordinates.
        try:
            import pytesseract
            from PIL import Image
            data = pytesseract.image_to_data(Image.open(path), output_type=pytesseract.Output.DICT)
            words = []
            for i, text in enumerate(data["text"]):
                if text.strip():
                    words.append(self._token(text.strip(), data["height"][i],
                                              data["left"][i], data["top"][i]))
            return [ParsedPage(1, DPI, words)]
        except ImportError:
            return [ParsedPage(1, DPI, [])]
