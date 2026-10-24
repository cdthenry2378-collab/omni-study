"""Asynchronous, network-backed Edge TTS podcast compositor."""
from __future__ import annotations
import asyncio, re
from pathlib import Path

class AudioCompositor:
    VOICES = ("en-US-AndrewNeural", "en-US-EmmaNeural")

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def dialogue_tree(text: str, max_words: int = 90) -> list[dict[str, str]]:
        words = re.findall(r"\S+", text)
        chunks = [" ".join(words[i:i+max_words]) for i in range(0, len(words), max_words)]
        return [{"speaker": "Andrew" if i % 2 == 0 else "Emma",
                 "voice": AudioCompositor.VOICES[i % 2], "text": chunk}
                for i, chunk in enumerate(chunks) if chunk]

    async def compose(self, text: str, filename: str = "study_overview.mp3") -> Path:
        """Network required for speech synthesis; all other app features work offline."""
        if not text.strip():
            raise ValueError("Cannot synthesize an empty overview.")
        try:
            import edge_tts
        except ImportError as exc:
            raise RuntimeError("Install edge-tts to enable audio generation.") from exc
        safe_name = Path(filename).name
        if not safe_name.lower().endswith(".mp3"):
            safe_name += ".mp3"
        destination = self.output_dir / safe_name
        temp_files = []
        try:
            for i, segment in enumerate(self.dialogue_tree(text)):
                part = self.output_dir / f".part_{i}_{destination.stem}.mp3"
                await edge_tts.Communicate(segment["text"], segment["voice"]).save(str(part))
                temp_files.append(part)
            # MP3 frame streams concatenate safely for common players.
            with destination.open("wb") as output:
                for part in temp_files:
                    output.write(part.read_bytes())
            return destination
        finally:
            for part in temp_files:
                try: part.unlink(missing_ok=True)
                except OSError: pass
