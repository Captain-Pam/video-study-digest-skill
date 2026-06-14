#!/usr/bin/env python3
"""Download audio-only media when needed and transcribe it with faster-whisper."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse


DEFAULT_CACHE_ROOT = Path(r"F:\cc_project\CodexMediaCache")


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def source_id(value: str) -> str:
    if is_url(value):
        parsed = urlparse(value)
        query_id = parse_qs(parsed.query).get("v", [None])[0]
        if query_id:
            return safe_id(query_id)
        path_parts = [part for part in parsed.path.split("/") if part]
        if path_parts:
            return safe_id(path_parts[-1])
    return safe_id(Path(value).stem)


def safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned or "media"


def ensure_cache_layout(cache_root: Path) -> dict[str, Path]:
    layout = {
        "audio": cache_root / "audio",
        "metadata": cache_root / "metadata",
        "models": cache_root / "models" / "huggingface",
        "transcripts": cache_root / "transcripts",
        "tmp": cache_root / "tmp",
    }
    for path in layout.values():
        path.mkdir(parents=True, exist_ok=True)
    return layout


def yt_dlp_command() -> list[str]:
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]
    if importlib.util.find_spec("yt_dlp"):
        return [sys.executable, "-m", "yt_dlp"]
    raise SystemExit("yt-dlp is required for URL audio extraction.")


def download_audio(url: str, audio_dir: Path, media_id: str) -> Path:
    audio_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(audio_dir / f"{media_id}.%(ext)s")
    preferred = audio_dir / f"{media_id}.m4a"
    if preferred.exists():
        return preferred
    command = yt_dlp_command() + [
        "-f",
        "ba[ext=m4a]/ba/bestaudio",
        "--no-playlist",
        "-o",
        output_template,
        url,
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        message = "Could not download audio with yt-dlp."
        if details:
            message = f"{message}\n{details}"
        raise SystemExit(message) from exc
    if preferred.exists():
        return preferred
    candidates = sorted(audio_dir.glob(f"{media_id}.*"))
    if not candidates:
        raise SystemExit("Audio extraction completed but no audio file was found.")
    return candidates[0]


def ensure_transcriber_available() -> None:
    if importlib.util.find_spec("faster_whisper") is None:
        raise SystemExit(
            "faster-whisper is required for transcription. Install it with: python -m pip install faster-whisper"
        )


def format_vtt_timestamp(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    total_seconds, millis = divmod(milliseconds, 1000)
    minutes, sec = divmod(total_seconds, 60)
    hours, minute = divmod(minutes, 60)
    return f"{hours:02d}:{minute:02d}:{sec:02d}.{millis:03d}"


def format_markdown_timestamp(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def to_vtt(segments: list[dict[str, object]]) -> str:
    lines = ["WEBVTT", ""]
    for index, segment in enumerate(segments, start=1):
        start = float(segment["start"])
        end = float(segment["end"])
        text = str(segment["text"]).strip()
        lines.extend(
            [
                str(index),
                f"{format_vtt_timestamp(start)} --> {format_vtt_timestamp(end)}",
                text,
                "",
            ]
        )
    return "\n".join(lines)


def to_markdown(source: str, segments: list[dict[str, object]]) -> str:
    lines = ["# Transcript", "", f"Source: {source}", f"Segments: {len(segments)}", ""]
    for segment in segments:
        lines.append(f"- [{format_markdown_timestamp(float(segment['start']))}] {segment['text']}")
    lines.append("")
    return "\n".join(lines)


def transcribe_audio(
    audio_path: Path,
    model_size: str,
    language: str | None,
    model_cache_dir: Path,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    ensure_transcriber_available()
    from faster_whisper import WhisperModel

    model = WhisperModel(
        model_size,
        device="cpu",
        compute_type="int8",
        download_root=str(model_cache_dir),
    )
    kwargs = {"vad_filter": True}
    if language:
        kwargs["language"] = language
    segments_iter, info = model.transcribe(str(audio_path), **kwargs)
    segments = [
        {"start": segment.start, "end": segment.end, "text": segment.text.strip()}
        for segment in segments_iter
        if segment.text.strip()
    ]
    metadata = {
        "language": getattr(info, "language", None),
        "language_probability": getattr(info, "language_probability", None),
        "duration": getattr(info, "duration", None),
        "model_size": model_size,
    }
    return segments, metadata


def write_outputs(
    source: str,
    media_id: str,
    audio_path: Path,
    transcript_dir: Path,
    segments: list[dict[str, object]],
    metadata: dict[str, object],
) -> dict[str, str]:
    transcript_dir.mkdir(parents=True, exist_ok=True)
    vtt_path = transcript_dir / f"{media_id}.vtt"
    json_path = transcript_dir / f"{media_id}.json"
    md_path = transcript_dir / f"{media_id}.md"
    vtt_path.write_text(to_vtt(segments), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "source": source,
                "audio_path": str(audio_path),
                "metadata": metadata,
                "segments": segments,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    md_path.write_text(to_markdown(source, segments), encoding="utf-8")
    return {
        "vtt": str(vtt_path),
        "json": str(json_path),
        "markdown": str(md_path),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download audio-only media when needed and transcribe it with faster-whisper."
    )
    parser.add_argument("source", help="Video/audio URL or local media file.")
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--model-size", default="base", help="faster-whisper model size. Default: base.")
    parser.add_argument("--language", help="Optional language hint such as en, zh, or ja.")
    parser.add_argument("--reuse", action="store_true", help="Reuse existing transcript outputs when present.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    media_id = source_id(args.source)
    layout = ensure_cache_layout(args.cache_root)
    vtt_path = layout["transcripts"] / f"{media_id}.vtt"
    if args.reuse and vtt_path.exists():
        print(str(vtt_path))
        return 0
    if is_url(args.source):
        audio_path = download_audio(args.source, layout["audio"], media_id)
    else:
        audio_path = Path(args.source)
        if not audio_path.exists():
            raise SystemExit(f"Local media file not found: {audio_path}")
    segments, metadata = transcribe_audio(audio_path, args.model_size, args.language, layout["models"])
    if not segments:
        raise SystemExit("Transcription produced no text segments.")
    outputs = write_outputs(args.source, media_id, audio_path, layout["transcripts"], segments, metadata)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
