# OmniStudy AI

Local-first PyQt6 desktop study workspace. The first run creates `%LOCALAPPDATA%\\OmniStudyAI\\data_vault.db` and a local log. The GUI, parser, retrieval, scheduler, and Feynman runner do not require a cloud account. Edge TTS audio synthesis requires internet access.

## Build locally (Windows PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller
python -m src.main
```

## Download the Windows executable

Push to `main`/`master`, or use **Actions → Build OmniStudy AI (Windows) → Run workflow**. Download the `OmniStudy_AI_Setup-windows-x64` artifact from the completed run.

The artifact is a portable single-file executable, not a conventional installer. GitHub Actions artifact downloads require a GitHub account; no payment card is needed for standard public-repository GitHub-hosted runner usage, subject to current GitHub usage limits.

## Notes and limitations

- Text-based PDFs and text/Markdown files preserve approximate word coordinates. Image OCR is optional; install Tesseract and `pytesseract` separately if image OCR is desired.
- Retrieval is fully local and combines normalized NumPy term vectors with BM25.
- FSRS mode is a transparent FSRS-inspired scheduling heuristic, not a certified exact implementation of the FSRS 4.5 parameter set.
- The subprocess sandbox has a timeout and isolated temporary working directory, but Python subprocesses are not a complete security boundary against malicious code.
- OpenCV face-presence monitoring is opt-in and is not a medical or precise gaze/blink detector.
- The 120 FPS value is a design target, not a guarantee; performance depends on GPU, display, drivers, and workload.
