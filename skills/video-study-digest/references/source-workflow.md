# Source Workflow

Use this guide to decide how to obtain and trust the source material before writing study notes.

## Source Priority

1. User-provided transcript with timestamps.
2. Local `.vtt`, `.srt`, or timestamped `.txt` file.
3. Public video URL with source context from `scripts/extract_video_context.py` plus captions from `scripts/prepare_transcript.py`.
4. Local video/audio transcribed with an available speech-to-text tool, then normalized.
5. User-supplied rough notes, only if transcript extraction is impossible.

## Extracting Source Context

For URL input, collect metadata before or alongside transcript extraction:

```bash
python <skill-dir>/scripts/extract_video_context.py <url> --output source_context.json
```

For an existing `yt-dlp` info JSON:

```bash
python <skill-dir>/scripts/extract_video_context.py info.json --output source_context.json
```

Use source context for title, uploader, duration, chapter hints, description, tags, and available caption languages. Treat it as metadata, not as proof of what was said. The transcript remains the primary evidence for claims about video content.

For the usual URL or local transcript workflow, prefer the one-command pipeline:

```bash
python <skill-dir>/scripts/video_digest_pipeline.py <url-or-transcript> --output-dir video-study-output
```

It writes source context when available, transcript Markdown/JSON, and `run_report.json`/`run_report.md`.

## Pipeline Output Files

The pipeline writes result files under the requested `--output-dir`:

| File | When it appears | How to use it |
| --- | --- | --- |
| `source_context.json` | URL or `yt-dlp` info JSON input when metadata extraction works | Machine-readable metadata: title, uploader, duration, chapters, description, tags, thumbnails, and available captions. Use for triage and source orientation only. |
| `source_context.md` | Same as `source_context.json` | Human-readable metadata summary. Do not cite it as spoken transcript evidence. |
| `transcript.md` | Local transcript/subtitle input, or public captions found by `yt-dlp` | Primary human-readable transcript evidence for study notes. Cite timestamps from this file when available. |
| `transcript.json` | Same as `transcript.md` | Machine-readable transcript segments for chunking, filtering, or downstream processing. |
| `transcript_whisper.vtt` | Audio transcription fallback after `--transcribe-if-needed` | Timestamped faster-whisper transcript. Treat as generated transcript and state that limitation when useful. |
| `transcript_whisper.md` | Same transcription fallback | Human-readable faster-whisper transcript. |
| `transcript_whisper.json` | Same transcription fallback | Machine-readable transcription segments and metadata. |
| `run_report.json` | Every pipeline run | Machine-readable status, transcript method, cache root, output paths, warnings, and errors. |
| `run_report.md` | Every pipeline run | Human-readable run summary and output index. |

The pipeline prepares source material; it does not generate final learning notes. Save final notes separately, commonly as `study_notes.md`, when the user asks for a file artifact.

## Normalizing Captions

Run the bundled script when a file or URL needs normalization:

```bash
python <skill-dir>/scripts/prepare_transcript.py <source> --output transcript.md
```

For machine-readable segments:

```bash
python <skill-dir>/scripts/prepare_transcript.py <source> --format json --output transcript.json
```

For URL input, the script uses `yt-dlp` when available and downloads captions only. It does not download the video stream.

## When Captions Are Missing

- For a local video/audio file, use a locally available transcription tool such as Whisper or faster-whisper if the environment supports it.
- For a public URL with no captions, use `scripts/transcribe_audio.py` only when the user wants transcription and accepts the audio download/cache step.
- Cache root priority:
  1. `--cache-root`
  2. `VIDEO_STUDY_CACHE_ROOT`
  3. existing `F:\cc_project\CodexMediaCache` on Windows
  4. platform user cache directory
- Cache layout:

```text
<cache-root>\
  audio\
  metadata\
  models\
    huggingface\
  transcripts\
  tmp\
```

- Before using local transcription, probe support with one of:

```bash
whisper --help
```

```bash
python -c "import faster_whisper; print('faster-whisper available')"
```

- Prefer output as `.vtt`, `.srt`, or timestamped `.txt`, then normalize it with `scripts/prepare_transcript.py`.
- If the tool is unavailable, the media is very long, or transcription would dominate the task, ask the user for captions/transcript or confirm before spending time on transcription.
- If transcription is unavailable or would be too slow, ask the user for a transcript or captions.
- Do not pretend to have watched visual content when only audio/transcript was available.

Audio transcription command:

```bash
python <skill-dir>/scripts/transcribe_audio.py <url-or-local-media> --cache-root <cache-root> --model-size base
```

This downloads audio only, not the full video, then writes `.vtt`, `.json`, and `.md` transcript outputs under `transcripts\`.
The faster-whisper model files are downloaded under `models\huggingface\` inside the same cache root.

Before diagnosing user environment issues, run:

```bash
python <skill-dir>/scripts/doctor.py
```

## Chunking Long Transcripts

For long videos, process by 10-20 minute windows, then synthesize:

1. Make a timestamped chapter map first.
2. Summarize each chapter locally.
3. Merge repeated ideas across chapters.
4. Keep the final output organized by learning objective, not by every tiny caption cue.

## Quality Checks

Before finalizing:

- Every major claim has a timestamp or an explicit "inference" label.
- Title, description, tags, chapters, and thumbnails are not cited as if they were spoken content.
- The recommendation to watch or skip the original is tied to the user's learning goal.
- The output includes active recall material unless the user asked for a very short answer.
- Missing context and source limitations are stated.
- The answer preserves technical terms where translation would reduce precision.
