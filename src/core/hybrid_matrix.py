"""Offline hybrid retrieval: TF-IDF-like dense vectors plus BM25 keyword ranking."""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable
import math
import re
import numpy as np

WORD_RE = re.compile(r"[A-Za-z0-9_]+", re.UNICODE)

@dataclass(frozen=True)
class Citation:
    source_name: str
    page_num: int
    rect: tuple[float, float, float, float]  # normalized x0,y0,x1,y1 in [0,1]
    excerpt: str = ""

@dataclass
class StudyChunk:
    chunk_id: str
    text: str
    citation: Citation

class HybridMatrix:
    def __init__(self, dense_weight: float = 0.55, bm25_weight: float = 0.45):
        self.dense_weight, self.bm25_weight = dense_weight, bm25_weight
        self.chunks: list[StudyChunk] = []
        self.vocab: dict[str, int] = {}
        self.matrix = np.zeros((0, 0), dtype=np.float32)
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.doc_lengths: list[int] = []
        self.avgdl = 0.0

    @staticmethod
    def tokenize(text: str) -> list[str]:
        return [x.lower() for x in WORD_RE.findall(text)]

    def add(self, chunk: StudyChunk) -> None:
        if any(c.chunk_id == chunk.chunk_id for c in self.chunks):
            raise ValueError(f"Duplicate chunk id: {chunk.chunk_id}")
        self.chunks.append(chunk)
        self._rebuild()

    def extend(self, chunks: Iterable[StudyChunk]) -> None:
        for chunk in chunks:
            self.chunks.append(chunk)
        self._rebuild()

    def _rebuild(self) -> None:
        docs = [self.tokenize(c.text) for c in self.chunks]
        vocab = sorted({term for doc in docs for term in doc})
        self.vocab = {term: i for i, term in enumerate(vocab)}
        df = Counter(term for doc in docs for term in set(doc))
        n, v = len(docs), len(vocab)
        matrix = np.zeros((n, v), dtype=np.float32)
        self.postings = defaultdict(list)
        self.doc_lengths = []
        for i, doc in enumerate(docs):
            counts = Counter(doc)
            self.doc_lengths.append(len(doc))
            for term, tf in counts.items():
                j = self.vocab[term]
                idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
                matrix[i, j] = (1 + math.log(tf)) * idf
                self.postings[term].append((i, tf))
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        self.matrix = matrix / np.maximum(norms, 1e-12)
        self.avgdl = sum(self.doc_lengths) / max(1, n)

    def search(self, query: str, limit: int = 10, k1: float = 1.5, b: float = 0.75) -> list[dict]:
        if limit < 1:
            return []
        terms = self.tokenize(query)
        if not terms or not self.chunks:
            return []
        q = np.zeros(len(self.vocab), dtype=np.float32)
        for term in terms:
            if term in self.vocab:
                q[self.vocab[term]] += 1.0
        qnorm = np.linalg.norm(q)
        dense = (self.matrix @ (q / qnorm)) if qnorm else np.zeros(len(self.chunks))
        n = len(self.chunks)
        bm25 = np.zeros(n, dtype=np.float64)
        df = {term: len(self.postings.get(term, [])) for term in set(terms)}
        for term in terms:
            entries = self.postings.get(term, [])
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5)) if df[term] else 0
            for i, tf in entries:
                dl = self.doc_lengths[i]
                denom = tf + k1 * (1 - b + b * dl / max(self.avgdl, 1e-9))
                bm25[i] += idf * tf * (k1 + 1) / denom
        if bm25.max() > 0:
            bm25 /= bm25.max()
        scores = self.dense_weight * dense + self.bm25_weight * bm25
        indices = np.argsort(scores)[::-1][:limit]
        return [{"chunk_id": self.chunks[i].chunk_id, "text": self.chunks[i].text,
                 "score": float(scores[i]), "citation": asdict(self.chunks[i].citation)}
                for i in indices if scores[i] > 0]

    @staticmethod
    def citation_from_page(source_name: str, page_num: int, words: list[dict],
                           canvas_width: float, canvas_height: float) -> Citation:
        if not words or canvas_width <= 0 or canvas_height <= 0:
            return Citation(source_name, page_num, (0, 0, 1, 1), "")
        xs = [w["x"] for w in words]; ys = [w["y"] for w in words]
        x1 = [w["x"] + max(1, w["length"]) * max(1, w["font-size"]) * .55 for w in words]
        y1 = [w["y"] + max(1, w["font-size"]) for w in words]
        rect = (max(0, min(xs) / canvas_width), max(0, min(ys) / canvas_height),
                min(1, max(x1) / canvas_width), min(1, max(y1) / canvas_height))
        return Citation(source_name, page_num, rect, " ".join(w["text"] for w in words))
