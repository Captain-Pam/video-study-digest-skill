#!/usr/bin/env python3
"""Normalize video transcripts/subtitles into Markdown or JSON segments."""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse


TIME_RE = re.compile(
    r"(?P<start>(?:\d{1,2}:)?\d{2}:\d{2}(?:[,.]\d{1,3})?|\d{1,2}:\d{2})\s*-->"
)
INLINE_TIME_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\[)?(?P<time>(?:\d{1,2}:)?\d{2}:\d{2}(?:[,.]\d{1,3})?|\d{1,2}:\d{2})(?:\])?\s+(?P<text>.+)$"
)
TAG_RE = re.compile(r"<[^>]+>")
SPEAKER_RE = re.compile(r"^(?P<speaker>[A-Z][\w .-]{0,40}):\s+(?P<text>.+)$")


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def yt_dlp_command() -> list[str]:
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]
    if importlib.util.find_spec("yt_dlp"):
        return [sys.executable, "-m", "yt_dlp"]
    raise SystemExit(
        "yt-dlp is required for URL input. Install it or pass a local .vtt/.srt/.txt transcript."
    )


def language_preferences(languages: str) -> list[str]:
    preferences: list[str] = []
    for language in languages.split(","):
        cleaned = language.strip().lower().replace("*", "").strip(".")
        if cleaned and cleaned != "all":
            preferences.append(cleaned)
    return preferences


def candidate_score(path: Path, languages: str) -> tuple[int, int, str]:
    name = path.name.lower()
    preferences = language_preferences(languages)
    language_rank = len(preferences)
    for rank, language in enumerate(preferences):
        if f".{language}" in name or language in name:
            language_rank = rank
            break
    extension_rank = 0 if path.suffix.lower() == ".vtt" else 1
    return language_rank, extension_rank, name


def subtitle_candidates(download_dir: Path, before: set[Path]) -> list[Path]:
    candidates = [
        p
        for p in download_dir.glob("*")
        if p.is_file() and p.suffix.lower() in {".vtt", ".srt"} and p.resolve() not in before
    ]
    if not candidates:
        candidates = [
            p for p in download_dir.glob("*") if p.is_file() and p.suffix.lower() in {".vtt", ".srt"}
        ]
    return candidates


def run_subtitle_download(url: str, download_dir: Path, languages: str, *, auto: bool) -> list[Path]:
    before = {p.resolve() for p in download_dir.glob("*") if p.is_file()}
    output_template = str(download_dir / "%(title).200B.%(ext)s")
    command = yt_dlp_command() + [
        "--skip-download",
        "--write-auto-subs" if auto else "--write-subs",
        "--sub-langs",
        languages,
        "--sub-format",
        "vtt/srt/best",
        "-o",
        output_template,
        url,
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return subtitle_candidates(download_dir, before)


def download_subtitles(url: str, download_dir: Path, languages: str) -> Path:
    download_dir.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    for auto in (False, True):
        try:
            candidates = run_subtitle_download(url, download_dir, languages, auto=auto)
        except subprocess.CalledProcessError as exc:
            details = (exc.stderr or exc.stdout or "").strip()
            label = "automatic subtitles" if auto else "manual subtitles"
            if details:
                errors.append(f"{label}: {details}")
            else:
                errors.append(f"{label}: yt-dlp exited with status {exc.returncode}")
            continue
        if candidates:
            return sorted(candidates, key=lambda p: candidate_score(p, languages))[0]
    if errors:
        message = "Could not download subtitles with yt-dlp. Try a video with captions, pass a local transcript, or transcribe locally."
        raise SystemExit(f"{message}\n" + "\n".join(errors))
    raise SystemExit("No subtitle file was downloaded. Try a video with captions or transcribe locally.")


def clean_text(value: str) -> str:
    value = html.unescape(value)
    value = TAG_RE.sub("", value)
    value = value.replace("\ufeff", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def append_with_overlap(existing: str, addition: str) -> str:
    if not existing:
        return addition
    if existing == addition or existing.endswith(addition):
        return existing
    if addition.startswith(existing):
        return addition
    existing_words = existing.split()
    addition_words = addition.split()
    max_overlap = min(len(existing_words), len(addition_words))
    for overlap in range(max_overlap, 1, -1):
        if existing_words[-overlap:] == addition_words[:overlap]:
            return f"{existing} {' '.join(addition_words[overlap:])}".strip()
    return f"{existing} {addition}".strip()


def normalize_timestamp(value: str) -> tuple[str, float]:
    value = value.strip().replace(",", ".")
    parts = value.split(":")
    seconds = 0.0
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    elif len(parts) == 2:
        hours = 0
        minutes = int(parts[0])
        seconds = float(parts[1])
    else:
        raise ValueError(f"Unsupported timestamp: {value}")
    total_seconds = hours * 3600 + minutes * 60 + seconds
    whole = int(total_seconds)
    return f"{whole // 3600:02d}:{(whole % 3600) // 60:02d}:{whole % 60:02d}", total_seconds


def merge_repeated_lines(lines: list[str]) -> str:
    merged = ""
    for line in lines:
        text = clean_text(line)
        if not text:
            continue
        if text.startswith(("NOTE", "STYLE", "REGION")):
            continue
        merged = append_with_overlap(merged, text)
    return merged.strip()


def parse_subtitle_text(raw: str) -> list[dict[str, object]]:
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    segments: list[dict[str, object]] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        match = TIME_RE.search(line)
        if not match:
            idx += 1
            continue
        timestamp, seconds = normalize_timestamp(match.group("start"))
        idx += 1
        text_lines: list[str] = []
        while idx < len(lines) and lines[idx].strip():
            text_lines.append(lines[idx])
            idx += 1
        text = merge_repeated_lines(text_lines)
        if text:
            segments.append({"timestamp": timestamp, "seconds": seconds, "text": text})
        idx += 1
    return segments


def parse_plain_text(raw: str) -> list[dict[str, object]]:
    segments: list[dict[str, object]] = []
    current_time = "00:00:00"
    current_seconds = 0.0
    current_text: list[str] = []
    saw_timestamp = False

    def flush() -> None:
        nonlocal current_text
        text = merge_repeated_lines(current_text)
        if text:
            segments.append({"timestamp": current_time, "seconds": current_seconds, "text": text})
        current_text = []

    for line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        match = INLINE_TIME_RE.match(stripped)
        if match:
            saw_timestamp = True
            flush()
            current_time, current_seconds = normalize_timestamp(match.group("time"))
            current_text.append(match.group("text"))
        else:
            if saw_timestamp:
                current_text.append(stripped)
    if not saw_timestamp:
        return []
    flush()
    return segments


def add_speaker_fields(segments: list[dict[str, object]]) -> list[dict[str, object]]:
    for segment in segments:
        text = str(segment["text"])
        match = SPEAKER_RE.match(text)
        if match:
            segment["speaker"] = match.group("speaker")
            segment["text"] = match.group("text")
    return segments


def parse_transcript(path: Path) -> list[dict[str, object]]:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    if "-->" in raw:
        segments = parse_subtitle_text(raw)
    else:
        segments = parse_plain_text(raw)
    return add_speaker_fields(segments)


def to_markdown(source: str, segments: list[dict[str, object]]) -> str:
    lines = ["# Transcript", "", f"Source: {source}", f"Segments: {len(segments)}", ""]
    for segment in segments:
        speaker = f" {segment['speaker']}:" if "speaker" in segment else ""
        lines.append(f"- [{segment['timestamp']}]{speaker} {segment['text']}")
    lines.append("")
    return "\n".join(lines)


def to_json(source: str, segments: list[dict[str, object]]) -> str:
    return json.dumps({"source": source, "segments": segments}, ensure_ascii=False, indent=2) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize YouTube subtitles, .vtt, .srt, or timestamped text for video-study-digest."
    )
    parser.add_argument("source", help="Local transcript path or video URL supported by yt-dlp.")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--output", type=Path, help="Output path. Defaults to stdout.")
    parser.add_argument(
        "--languages",
        default="en,zh-CN,zh-TW,zh-Hans,zh-Hant",
        help="yt-dlp subtitle language selector for URL input.",
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        help="Directory for downloaded subtitle files. Defaults to a temporary directory.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source_label = args.source
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if is_url(args.source):
        if args.download_dir:
            transcript_path = download_subtitles(args.source, args.download_dir, args.languages)
        else:
            temp_dir = tempfile.TemporaryDirectory()
            transcript_path = download_subtitles(args.source, Path(temp_dir.name), args.languages)
    else:
        transcript_path = Path(args.source)
        if not transcript_path.exists():
            raise SystemExit(f"Transcript file not found: {transcript_path}")
        source_label = str(transcript_path)

    segments = parse_transcript(transcript_path)
    if not segments:
        raise SystemExit("No timestamped transcript segments found.")

    content = (
        to_json(source_label, segments)
        if args.format == "json"
        else to_markdown(source_label, segments)
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    else:
        sys.stdout.write(content)
    if temp_dir is not None:
        temp_dir.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
