---
name: video-study-digest
description: Use when a user wants to learn from, summarize, review, or extract study materials from a video, YouTube link, transcript, subtitles, VTT/SRT file, lecture, webinar, interview, tutorial, course, talk, demo, or screen recording.
---

# Video Study Digest

## Overview

Create source-grounded study notes from video transcripts. Prefer timestamped evidence, active recall, and clear watch/skip guidance over generic summaries.

## Workflow

1. Identify the source type: pasted transcript, local subtitle file, video URL, local media file, or rough notes.
2. For video URLs, read `references/source-workflow.md` and prefer `scripts/video_digest_pipeline.py` when practical to prepare source context and transcript artifacts in one run.
3. If the environment is uncertain, run `scripts/doctor.py` before long downloads or transcription.
4. If the transcript is not already clean and timestamped, normalize it with `scripts/prepare_transcript.py` when practical.
5. If captions are unavailable and the user approves audio transcription, use `scripts/transcribe_audio.py` with `--cache-root` or the `VIDEO_STUDY_CACHE_ROOT` environment variable.
6. Read `references/study-note-contract.md` before writing the final learning output.
7. Match depth to the user's wording:
   - Short requests: compact output with `一句话结论`, `是否值得看原片`, `核心要点`, `下一步`, and `来源边界`.
   - "复习", "快速学习", "判断要不要看": default output.
   - "课程笔记", "深入", "Obsidian", "考试": deep output.
8. Cite timestamps for important claims whenever timestamps exist.

## Tooling

Normalize local `.srt`, `.vtt`, or timestamped `.txt`:

```bash
python <skill-dir>/scripts/prepare_transcript.py <source> --output transcript.md
```

Normalize to JSON segments:

```bash
python <skill-dir>/scripts/prepare_transcript.py <source> --format json --output transcript.json
```

For a public video URL, the script attempts caption extraction with `yt-dlp`. If captions are missing, use available transcription tools or ask for a transcript.

Extract URL metadata context without downloading the video:

```bash
python <skill-dir>/scripts/extract_video_context.py <url-or-info-json> --output source_context.json
```

Prepare a URL or local transcript with one command:

```bash
python <skill-dir>/scripts/video_digest_pipeline.py <url-or-transcript> --output-dir video-study-output
```

Check local dependencies and cache settings:

```bash
python <skill-dir>/scripts/doctor.py
```

When subtitles are missing and audio transcription is appropriate:

```bash
python <skill-dir>/scripts/transcribe_audio.py <url-or-local-media> --cache-root <cache-root> --model-size base
```

## Output Rules

- Write Chinese by default unless the user asks otherwise.
- Preserve precise technical terms in the original language on first use.
- Separate transcript-backed points from inference.
- For language-learning or phrase-heavy videos, include an `例句库` with timestamped source examples plus clearly labeled practice examples.
- Prefer `VIDEO_STUDY_CACHE_ROOT` or `--cache-root` over hard-coded machine-specific cache paths.
- Use source metadata for triage, chapters, and learning goals, but do not treat title, description, or tags as transcript evidence.
- Do not claim to have inspected visuals unless visual frames, screenshots, or multimodal video analysis were actually available.
- Include source limitations when the transcript is partial, auto-generated, translated, or missing timestamps.

## Common Mistakes

- Producing only a generic bullet summary.
- Listing vocabulary or phrases without examples.
- Dropping timestamps, making the original video hard to revisit.
- Translating away technical terms that should stay searchable.
- Inventing examples, speaker intent, or visual details not present in the source.
- Skipping flashcards or self-test material when the user asked to learn or review.
