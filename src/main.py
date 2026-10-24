"""Application bootstrap: qasync integration and bounded background executor."""
from __future__ import annotations
import asyncio, json, logging, os, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from qasync import QEventLoop
from src.gui.studio_shell import StudioShell

APP_NAME = "OmniStudy AI"

def application_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    else:
        base = Path.home() / ".local" / "share"
    path = base / "OmniStudyAI"
    path.mkdir(parents=True, exist_ok=True)
    return path

def configure_logging(data_dir: Path):
    logging.basicConfig(filename=data_dir / "omnistudy.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

async def run_app():
    app = QApplication.instance()
    app.setApplicationName(APP_NAME)
    data_dir = application_data_dir()
    configure_logging(data_dir)
    executor = ThreadPoolExecutor(max_workers=max(2, min(8, (os.cpu_count() or 4))),
                                  thread_name_prefix="omnistudy-worker")
    window = StudioShell(data_dir, executor=executor)
    window.show()
    app.aboutToQuit.connect(lambda: executor.shutdown(wait=False, cancel_futures=True))
    await asyncio.Event().wait()

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    data_dir = application_data_dir()
    configure_logging(data_dir)
    executor = ThreadPoolExecutor(max_workers=max(2, min(8, (os.cpu_count() or 4))),
                                  thread_name_prefix="omnistudy-worker")
    window = StudioShell(data_dir, executor=executor)
    window.show()
    app.aboutToQuit.connect(lambda: executor.shutdown(wait=False, cancel_futures=True))
    with loop:
        loop.run_forever()

if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("Fatal startup failure")
        raise
