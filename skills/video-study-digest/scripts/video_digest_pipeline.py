#!/usr/bin/env python3
"""One-command source preparation pipeline for video-study-digest."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cache_paths import default_cache_root
import extract_video_context
import prepare_transcript
import transcribe_audio as transcribe_module


def write_report(output_dir: Path, report: dict[str, object]) -> None:
    report_json = output_dir / "run_report.json"
    report_md = output_dir / "run_report.md"
    report.setdefault("outputs", {})
    report["outputs"]["run_report_json"] = str(report_json)
    report["outputs"]["run_report_markdown"] = str(report_md)
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Video Digest Pipeline Report",
        "",
        f"- Status: {report['status']}",
        f"- Transcript method: {report.get('transcript_method') or 'none'}",
        f"- Source: {report['source']}",
        "",
    ]
    if report.get("outputs"):
        lines.append("## Outputs")
        for name, value in report["outputs"].items():
            lines.append(f"- {name}: {value}")
        lines.append("")
    if report.get("warnings"):
        lines.append("## Warnings")
        for warning in report["warnings"]:
            lines.append(f"- {warning}")
        lines.append("")
    if report.get("errors"):
        lines.append("## Errors")
        for error in report["errors"]:
            lines.append(f"- {error}")
        lines.append("")
    report_md.write_text("\n".join(lines), encoding="utf-8")


def write_transcript_outputs(source: str, segments: list[dict[str, object]], output_dir: Path) -> dict[str, str]:
    markdown_path = output_dir / "transcript.md"
    json_path = output_dir / "transcript.json"
    markdown_path.write_text(prepare_transcript.to_markdown(source, segments), encoding="utf-8")
    json_path.write_text(prepare_transcript.to_json(source, segments), encoding="utf-8")
    return {"transcript_markdown": str(markdown_path), "transcript_json": str(json_path)}


def write_source_context(source: str, output_dir: Path, warnings: list[str]) -> dict[str, str]:
    try:
        info, source_label = extract_video_context.load_info(source)
        context = extract_video_context.normalize_context(info, source_label)
    except SystemExit as exc:
        warnings.append(str(exc))
        return {}
    json_path = output_dir / "source_context.json"
    markdown_path = output_dir / "source_context.md"
    json_path.write_text(json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(extract_video_context.to_markdown(context), encoding="utf-8")
    return {"source_context_json": str(json_path), "source_context_markdown": str(markdown_path)}


def copy_transcription_outputs(cache_root: Path, source: str, output_dir: Path) -> dict[str, str]:
    media_id = transcribe_module.source_id(source)
    transcript_dir = cache_root / "transcripts"
    outputs: dict[str, str] = {}
    for suffix, label in (("md", "transcript_markdown"), ("json", "transcript_json"), ("vtt", "transcript_vtt")):
        source_path = transcript_dir / f"{media_id}.{suffix}"
        if source_path.exists():
            target = output_dir / f"transcript_whisper.{suffix}"
            shutil.copy2(source_path, target)
            outputs[label] = str(target)
    return outputs


def run_pipeline(
    source: str,
    output_dir: Path,
    cache_root: Path | None = None,
    languages: str = "en,zh-CN,zh-TW,zh-Hans,zh-Hant",
    transcribe_if_needed: bool = False,
    model_size: str = "base",
    language: str | None = None,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    root = cache_root or default_cache_root()
    warnings: list[str] = []
    errors: list[str] = []
    outputs: dict[str, str] = {}

    report: dict[str, object] = {
        "source": source,
        "status": "ok",
        "transcript_method": None,
        "cache_root": str(root),
        "outputs": outputs,
        "warnings": warnings,
        "errors": errors,
    }

    if prepare_transcript.is_url(source):
        outputs.update(write_source_context(source, output_dir, warnings))
        try:
            tmp_root = root / "tmp"
            tmp_root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=tmp_root) as tmp:
                subtitle_path = prepare_transcript.download_subtitles(source, Path(tmp), languages)
                segments = prepare_transcript.parse_transcript(subtitle_path)
        except SystemExit as exc:
            warnings.append(f"Caption extraction failed: {exc}")
            if not transcribe_if_needed:
                report["status"] = "blocked"
                errors.append("No transcript available. Re-run with --transcribe-if-needed or provide a local transcript.")
                write_report(output_dir, report)
                return report
            args = [source, "--cache-root", str(root), "--model-size", model_size]
            if language:
                args.extend(["--language", language])
            transcribe_module.main(args)
            copied = copy_transcription_outputs(root, source, output_dir)
            if not copied:
                report["status"] = "error"
                errors.append("Transcription completed but no transcript outputs were found.")
            else:
                report["transcript_method"] = "transcription"
                outputs.update(copied)
            write_report(output_dir, report)
            return report
        if not segments:
            report["status"] = "blocked"
            errors.append("Caption extraction produced no timestamped segments.")
        else:
            report["transcript_method"] = "captions"
            outputs.update(write_transcript_outputs(source, segments, output_dir))
        write_report(output_dir, report)
        return report

    transcript_path = Path(source)
    segments = prepare_transcript.parse_transcript(transcript_path)
    if not segments:
        report["status"] = "blocked"
        errors.append("Local transcript has no timestamped segments.")
    else:
        report["transcript_method"] = "local-transcript"
        outputs.update(write_transcript_outputs(str(transcript_path), segments, output_dir))
    write_report(output_dir, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare source context and transcript artifacts from a URL or transcript.")
    parser.add_argument("source", help="Video URL or local timestamped transcript/subtitle file.")
    parser.add_argument("--output-dir", type=Path, default=Path("video-study-digest-output"))
    parser.add_argument("--cache-root", type=Path, default=default_cache_root())
    parser.add_argument("--languages", default="en,zh-CN,zh-TW,zh-Hans,zh-Hant")
    parser.add_argument("--transcribe-if-needed", action="store_true")
    parser.add_argument("--model-size", default="base")
    parser.add_argument("--language", help="Optional transcription language hint such as en, zh, or ja.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_pipeline(
        source=args.source,
        output_dir=args.output_dir,
        cache_root=args.cache_root,
        languages=args.languages,
        transcribe_if_needed=args.transcribe_if_needed,
        model_size=args.model_size,
        language=args.language,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
