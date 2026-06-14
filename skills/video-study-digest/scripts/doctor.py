#!/usr/bin/env python3
"""Check the local environment for video-study-digest."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cache_paths import default_cache_root


def check(name: str, status: str, message: str) -> dict[str, str]:
    return {"name": name, "status": status, "message": message}


def cache_root_check(cache_root: Path) -> dict[str, str]:
    try:
        cache_root.mkdir(parents=True, exist_ok=True)
        probe = cache_root / ".video-study-digest-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        return check("cache-root", "error", f"Cache root is not writable: {cache_root} ({exc})")
    return check("cache-root", "ok", f"Cache root is writable: {cache_root}")


def collect_report(
    cache_root: Path | None = None,
    command_exists=None,
    module_exists=None,
    python_version: tuple[int, int] | None = None,
    check_writable: bool = True,
) -> dict[str, object]:
    command_exists = command_exists or (lambda name: shutil.which(name) is not None)
    module_exists = module_exists or (lambda name: importlib.util.find_spec(name) is not None)
    version = python_version or (sys.version_info.major, sys.version_info.minor)
    root = cache_root or default_cache_root()

    checks: list[dict[str, str]] = []
    if version >= (3, 10):
        checks.append(check("python", "ok", f"Python {version[0]}.{version[1]} is supported."))
    else:
        checks.append(check("python", "error", f"Python {version[0]}.{version[1]} is too old; use Python 3.10+."))

    if command_exists("yt-dlp") or module_exists("yt_dlp"):
        checks.append(check("yt-dlp", "ok", "yt-dlp is available for URL metadata and captions."))
    else:
        checks.append(check("yt-dlp", "warn", "yt-dlp is missing; URL metadata/caption extraction will not work."))

    if module_exists("faster_whisper"):
        checks.append(check("faster-whisper", "ok", "faster-whisper is available for local transcription."))
    else:
        checks.append(check("faster-whisper", "warn", "faster-whisper is missing; audio transcription will not work."))

    if command_exists("ffmpeg"):
        checks.append(check("ffmpeg", "ok", "ffmpeg is available."))
    else:
        checks.append(check("ffmpeg", "warn", "ffmpeg is missing; yt-dlp may have fewer audio format options."))

    if check_writable:
        checks.append(cache_root_check(root))
    else:
        checks.append(check("cache-root", "ok", f"Cache root configured: {root}"))

    if any(item["status"] == "error" for item in checks):
        overall = "error"
    elif any(item["status"] == "warn" for item in checks):
        overall = "warn"
    else:
        overall = "ok"

    return {
        "overall_status": overall,
        "cache_root": str(root),
        "checks": checks,
    }


def to_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Video Study Digest Doctor",
        "",
        f"Overall status: {report['overall_status']}",
        f"Cache root: {report['cache_root']}",
        "",
        "## Checks",
    ]
    for item in report["checks"]:
        lines.append(f"- {item['status'].upper()} {item['name']}: {item['message']}")
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check video-study-digest local dependencies and cache settings.")
    parser.add_argument("--cache-root", type=Path, default=default_cache_root())
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = collect_report(cache_root=args.cache_root)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(to_markdown(report), end="")
    return 1 if report["overall_status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
