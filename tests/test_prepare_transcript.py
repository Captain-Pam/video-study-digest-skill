import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "skills" / "video-study-digest" / "scripts" / "prepare_transcript.py"


def load_module():
    spec = importlib.util.spec_from_file_location("prepare_transcript", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PrepareTranscriptTests(unittest.TestCase):
    def test_srt_input_becomes_markdown_with_timestamps(self):
        sample = """1
00:00:01,000 --> 00:00:04,500
Indexes help databases avoid scanning every row.

2
00:00:04,500 --> 00:00:08,000
But every write must also update the index.
"""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.srt"
            output = Path(tmp) / "normalized.md"
            source.write_text(sample, encoding="utf-8")

            subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(source), "--output", str(output)],
                check=True,
            )

            content = output.read_text(encoding="utf-8")

        self.assertIn("# Transcript", content)
        self.assertIn("- [00:00:01] Indexes help databases avoid scanning every row.", content)
        self.assertIn("- [00:00:04] But every write must also update the index.", content)

    def test_vtt_input_can_emit_json_segments(self):
        sample = """WEBVTT

00:00:01.000 --> 00:00:03.000
Retrieval recall measures whether the right evidence was found.

00:00:03.000 --> 00:00:05.000
Faithfulness measures whether the answer stays grounded.
"""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.vtt"
            output = Path(tmp) / "segments.json"
            source.write_text(sample, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    str(source),
                    "--format",
                    "json",
                    "--output",
                    str(output),
                ],
                check=True,
            )

            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(data["source"], str(source))
        self.assertEqual(data["segments"][0]["timestamp"], "00:00:01")
        self.assertEqual(data["segments"][1]["text"], "Faithfulness measures whether the answer stays grounded.")

    def test_overlapping_caption_lines_are_merged(self):
        sample = """WEBVTT

00:00:01.000 --> 00:00:04.000
A table scan checks
table scan checks every row
"""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.vtt"
            output = Path(tmp) / "segments.json"
            source.write_text(sample, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    str(source),
                    "--format",
                    "json",
                    "--output",
                    str(output),
                ],
                check=True,
            )

            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(data["segments"][0]["text"], "A table scan checks every row")

    def test_untimestamped_text_fails_instead_of_faking_timestamp(self):
        sample = "This is a rough note without a timestamp."
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "notes.txt"
            source.write_text(sample, encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(source)],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No timestamped transcript segments found", result.stderr)

    def test_default_subtitle_languages_do_not_request_all_languages(self):
        module = load_module()
        args = module.build_parser().parse_args(["https://example.com/video"])
        self.assertNotIn("all", args.languages.split(","))
        self.assertNotIn("*", args.languages)

    def test_download_subtitles_prefers_manual_subtitles_before_auto(self):
        module = load_module()
        calls = []
        module.yt_dlp_command = lambda: ["yt-dlp"]
        original_run = module.subprocess.run

        def fake_run(command, **_kwargs):
            calls.append(command)
            self.assertIn("--write-subs", command)
            self.assertNotIn("--write-auto-subs", command)
            output_template = Path(command[command.index("-o") + 1])
            Path(str(output_template).replace("%(title).200B", "sample").replace("%(ext)s", "en.vtt")).write_text(
                "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nhello\n",
                encoding="utf-8",
            )

        try:
            module.subprocess.run = fake_run
            with tempfile.TemporaryDirectory() as tmp:
                subtitle_path = module.download_subtitles("https://example.com/video", Path(tmp), "en,zh-CN")
        finally:
            module.subprocess.run = original_run

        self.assertEqual(len(calls), 1)
        self.assertEqual(subtitle_path.suffix, ".vtt")

    def test_yt_dlp_failure_returns_friendly_error(self):
        module = load_module()
        module.yt_dlp_command = lambda: ["yt-dlp"]
        original_run = module.subprocess.run

        def fail_run(*_args, **_kwargs):
            raise subprocess.CalledProcessError(1, ["yt-dlp"], stderr="blocked")

        try:
            module.subprocess.run = fail_run
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(SystemExit) as raised:
                    module.download_subtitles("https://example.com/video", Path(tmp), "en.*")
        finally:
            module.subprocess.run = original_run

        self.assertIn("Could not download subtitles", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
