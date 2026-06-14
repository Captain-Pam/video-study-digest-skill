#!/usr/bin/env python3
"""Extract video metadata context without treating metadata as transcript evidence."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


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
        "yt-dlp is required for URL metadata extraction. Install it or pass an existing info.json file."
    )


def format_timestamp(seconds: object) -> str | None:
    if seconds is None:
        return None
    try:
        total = int(float(seconds))
    except (TypeError, ValueError):
        return None
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def normalize_upload_date(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    if re.fullmatch(r"\d{8}", value):
        return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"
    return value or None


def trim_text(value: object, limit: int = 6000) -> str | None:
    if not isinstance(value, str):
        return None
    text = re.sub(r"\r\n?", "\n", value).strip()
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n...[truncated]"


def normalize_chapters(info: dict[str, object]) -> list[dict[str, object]]:
    chapters: list[dict[str, object]] = []
    for chapter in info.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        start = chapter.get("start_time")
        end = chapter.get("end_time")
        title = chapter.get("title") or "Untitled chapter"
        chapters.append(
            {
                "title": str(title),
                "start_seconds": start,
                "end_seconds": end,
                "timestamp": format_timestamp(start),
                "end_timestamp": format_timestamp(end),
            }
        )
    return chapters


def normalize_caption_tracks(info: dict[str, object]) -> list[dict[str, object]]:
    tracks: list[dict[str, object]] = []
    for field, kind in (("subtitles", "manual"), ("automatic_captions", "automatic")):
        value = info.get(field)
        if not isinstance(value, dict):
            continue
        for language, entries in value.items():
            if not isinstance(entries, list):
                continue
            formats = sorted(
                {
                    str(entry.get("ext"))
                    for entry in entries
                    if isinstance(entry, dict) and entry.get("ext")
                }
            )
            tracks.append(
                {
                    "language": str(language),
                    "kind": kind,
                    "formats": formats,
                    "track_count": len(entries),
                }
            )
    return sorted(tracks, key=lambda item: (item["kind"] != "manual", item["language"]))


def normalize_context(info: dict[str, object], source: str) -> dict[str, object]:
    duration = info.get("duration")
    metadata = {
        "id": info.get("id"),
        "title": info.get("title"),
        "uploader": info.get("uploader") or info.get("channel"),
        "channel": info.get("channel"),
        "webpage_url": info.get("webpage_url") or source,
        "duration": {
            "seconds": duration,
            "timestamp": format_timestamp(duration),
        },
        "upload_date": normalize_upload_date(info.get("upload_date")),
        "thumbnail": info.get("thumbnail"),
        "categories": info.get("categories") or [],
        "tags": info.get("tags") or [],
    }
    description = trim_text(info.get("description"))
    return {
        "source_type": "metadata",
        "source": source,
        "metadata": metadata,
        "description": description,
        "chapters": normalize_chapters(info),
        "caption_tracks": normalize_caption_tracks(info),
        "source_boundaries": [
            "description is metadata, not transcript evidence",
            "chapters are uploader/platform structure and may not cover every topic",
            "caption track availability does not guarantee transcript text was extracted",
        ],
    }


def extract_with_yt_dlp(url: str) -> dict[str, object]:
    command = yt_dlp_command() + [
        "--skip-download",
        "--dump-single-json",
        "--no-warnings",
        url,
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        message = "Could not extract video metadata with yt-dlp. Pass a local info.json file or continue with transcript only."
        if details:
            message = f"{message}\n{details}"
        raise SystemExit(message) from exc
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit("yt-dlp returned invalid JSON metadata.") from exc


def load_info(source: str) -> tuple[dict[str, object], str]:
    if is_url(source):
        return extract_with_yt_dlp(source), source
    path = Path(source)
    if not path.exists():
        raise SystemExit(f"Metadata file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Metadata file is not valid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise SystemExit("Metadata JSON must be an object.")
    return data, str(path)


def to_markdown(context: dict[str, object]) -> str:
    metadata = context["metadata"]
    lines = [
        "# Source Context",
        "",
        "Metadata can guide triage and chapter mapping, but it is not transcript evidence.",
        "",
        f"- Title: {metadata.get('title') or 'Unknown'}",
        f"- Uploader: {metadata.get('uploader') or 'Unknown'}",
        f"- URL: {metadata.get('webpage_url') or context.get('source')}",
        f"- Duration: {metadata.get('duration', {}).get('timestamp') or 'Unknown'}",
        f"- Upload date: {metadata.get('upload_date') or 'Unknown'}",
        "",
    ]
    if context.get("chapters"):
        lines.append("## Chapters")
        for chapter in context["chapters"]:
            lines.append(f"- [{chapter['timestamp']}] {chapter['title']}")
        lines.append("")
    if context.get("caption_tracks"):
        lines.append("## Caption Tracks")
        for track in context["caption_tracks"]:
            formats = ", ".join(track["formats"]) if track["formats"] else "unknown"
            lines.append(f"- {track['language']} ({track['kind']}): {formats}")
        lines.append("")
    if context.get("description"):
        lines.extend(["## Description", "", str(context["description"]), ""])
    lines.append("## Source Boundaries")
    for boundary in context["source_boundaries"]:
        lines.append(f"- {boundary}")
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract source_context JSON/Markdown from a video URL or yt-dlp info.json."
    )
    parser.add_argument("source", help="Video URL supported by yt-dlp, or an existing info.json file.")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Output path. Defaults to stdout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    info, source = load_info(args.source)
    context = normalize_context(info, source)
    content = (
        to_markdown(context)
        if args.format == "markdown"
        else json.dumps(context, ensure_ascii=False, indent=2) + "\n"
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    else:
        sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
