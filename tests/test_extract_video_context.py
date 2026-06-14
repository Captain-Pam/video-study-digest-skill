import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "skills" / "video-study-digest" / "scripts" / "extract_video_context.py"


def load_module():
    spec = importlib.util.spec_from_file_location("extract_video_context", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ExtractVideoContextTests(unittest.TestCase):
    def test_info_json_becomes_source_context(self):
        info = {
            "id": "abc123",
            "title": "How Database Indexes Work",
            "uploader": "Practical Data",
            "channel": "Practical Data Channel",
            "webpage_url": "https://www.youtube.com/watch?v=abc123",
            "duration": 325,
            "upload_date": "20260613",
            "description": "A compact lesson about indexes.\n\n00:38 Table scans\n01:21 B-tree indexes",
            "chapters": [
                {"start_time": 0, "end_time": 38, "title": "Intro"},
                {"start_time": 38, "end_time": 81, "title": "Table scans"},
                {"start_time": 81, "title": "B-tree indexes"},
            ],
            "subtitles": {
                "en": [{"ext": "vtt", "url": "https://example.com/en.vtt"}],
                "zh-Hans": [{"ext": "vtt", "url": "https://example.com/zh.vtt"}],
            },
            "automatic_captions": {
                "en": [{"ext": "vtt", "url": "https://example.com/auto-en.vtt"}],
                "ja": [{"ext": "vtt", "url": "https://example.com/ja.vtt"}],
            },
            "tags": ["database", "sql"],
            "categories": ["Education"],
            "thumbnail": "https://example.com/thumb.jpg",
        }
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "info.json"
            output = Path(tmp) / "source_context.json"
            source.write_text(json.dumps(info), encoding="utf-8")

            subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(source), "--output", str(output)],
                check=True,
            )

            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(data["source_type"], "metadata")
        self.assertEqual(data["metadata"]["title"], "How Database Indexes Work")
        self.assertEqual(data["metadata"]["duration"], {"seconds": 325, "timestamp": "00:05:25"})
        self.assertEqual(data["metadata"]["upload_date"], "2026-06-13")
        self.assertEqual(data["chapters"][1]["timestamp"], "00:00:38")
        self.assertEqual(data["chapters"][2]["end_timestamp"], None)
        self.assertEqual(data["caption_tracks"][0]["language"], "en")
        self.assertEqual(data["caption_tracks"][0]["kind"], "manual")
        self.assertEqual(data["caption_tracks"][2]["kind"], "automatic")
        self.assertIn("description is metadata", data["source_boundaries"][0])

    def test_markdown_output_distinguishes_metadata_from_transcript(self):
        info = {
            "title": "RAG Evaluation",
            "webpage_url": "https://example.com/watch",
            "duration": 60,
            "description": "Speaker says retrieval matters.",
            "chapters": [{"start_time": 0, "title": "Opening"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "info.json"
            output = Path(tmp) / "context.md"
            source.write_text(json.dumps(info), encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    str(source),
                    "--format",
                    "markdown",
                    "--output",
                    str(output),
                ],
                check=True,
            )

            content = output.read_text(encoding="utf-8")

        self.assertIn("# Source Context", content)
        self.assertIn("RAG Evaluation", content)
        self.assertIn("Metadata can guide triage", content)
        self.assertIn("[00:00:00] Opening", content)

    def test_yt_dlp_failure_returns_friendly_error(self):
        module = load_module()
        module.yt_dlp_command = lambda: ["yt-dlp"]
        original_run = module.subprocess.run

        def fail_run(*_args, **_kwargs):
            raise subprocess.CalledProcessError(1, ["yt-dlp"], stderr="blocked")

        try:
            module.subprocess.run = fail_run
            with self.assertRaises(SystemExit) as raised:
                module.extract_with_yt_dlp("https://example.com/video")
        finally:
            module.subprocess.run = original_run

        self.assertIn("Could not extract video metadata", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
