# Video Study Digest Skill

Source-grounded study notes from videos, transcripts, and subtitle files.

This skill is for agents that need to help users learn from video content instead of only summarizing it. It prioritizes timestamped evidence, watch/skip guidance, concept explanations, active recall, and clear source boundaries.

## What It Does

- Normalizes `.srt`, `.vtt`, and timestamped `.txt` transcripts.
- Extracts source context from video URLs or `yt-dlp` info JSON.
- Keeps metadata separate from transcript-backed claims.
- Produces Chinese study notes by default, preserving important source terms.
- Supports compact, default, and deep study outputs.

## Install

Clone this repository and symlink or copy the skill folder into your agent's skills directory:

```bash
mkdir -p ~/.codex/skills
ln -s "$(pwd)/skills/video-study-digest" ~/.codex/skills/video-study-digest
```

On Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force $env:USERPROFILE\.codex\skills
Copy-Item -Recurse .\skills\video-study-digest $env:USERPROFILE\.codex\skills\video-study-digest
```

## Usage

```text
Use $video-study-digest to turn this video transcript into concise study notes.
```

For URL metadata context:

```bash
python skills/video-study-digest/scripts/extract_video_context.py "https://www.youtube.com/watch?v=VIDEO_ID" --output source_context.json
```

For captions or transcript normalization:

```bash
python skills/video-study-digest/scripts/prepare_transcript.py transcript.vtt --output transcript.md
```

For videos without public captions, audio-only transcription can use the default non-C-drive cache:

```bash
python skills/video-study-digest/scripts/transcribe_audio.py "https://www.youtube.com/watch?v=VIDEO_ID" --cache-root F:\cc_project\CodexMediaCache --model-size base
```

The cache stores audio, transcripts, temporary files, and faster-whisper model files under `F:\cc_project\CodexMediaCache` by default.

## Dependencies

- Python 3.10+ recommended.
- `yt-dlp` is optional but recommended for URL metadata and caption extraction.
- `faster-whisper` is optional for audio transcription when captions are missing.

The tests use only the Python standard library.

## Source Discipline

Metadata such as title, description, tags, chapters, thumbnails, and available captions can guide triage and learning goals. They are not transcript evidence. Claims about what the video says should come from timestamped transcript content or be explicitly labeled as inference.

## Test

```bash
python -m unittest discover -s tests
```

## License

MIT
