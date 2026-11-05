# WordWave Studio Pro — built on the original Muneeb TTS project

## Important
- `tts.py` is the Streamlit entry point. There is no `app.py`.
- The original Quick Voice, Multi-Voice Dialogue, and Audiobook Studio tabs are retained.
- Existing upload extraction, language detection, Edge TTS chunking/retries, speed/pitch controls, progress, dialogue voice assignment, background music, and optional word-boundary SRT flow are retained.
- Added tabs: Audio Editor, Subtitle Studio (SRT/VTT), Batch Studio, and Project Library.
- New helper code is separated into `wordwave/` modules.

## Run locally
1. Install Python (3.10+ recommended).
2. Install FFmpeg and add it to PATH.
3. Open a terminal in this folder.
4. Run `python -m pip install -r requirements.txt`.
5. Run `streamlit run tts.py`.

## Notes
- Word-level SRT/VTT requires Edge TTS to return WordBoundary events. The app does not invent timestamps.
- Edge TTS is an online service and is not guaranteed to be unlimited or continuously available.
- Project Library stores scripts/settings in a local SQLite database. It does not store large audio files.
- This build was syntax-checked; live provider calls and all UI interactions still require local testing.
