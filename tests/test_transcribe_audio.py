import importlib.util
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "skills" / "video-study-digest" / "scripts" / "transcribe_audio.py"


def load_module():
    spec = importlib.util.spec_from_file_location("transcribe_audio", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TranscribeAudioTests(unittest.TestCase):
    def test_default_cache_root_is_f_drive(self):
        module = load_module()
        args = module.build_parser().parse_args(["sample.mp3"])
        self.assertEqual(args.cache_root, Path(r"F:\cc_project\CodexMediaCache"))

    def test_ensure_cache_layout_creates_expected_dirs(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            layout = module.ensure_cache_layout(Path(tmp))

            self.assertEqual(set(layout), {"audio", "metadata", "models", "transcripts", "tmp"})
            for path in layout.values():
                self.assertTrue(path.exists())

    def test_format_segments_as_vtt(self):
        module = load_module()
        segments = [
            {"start": 1.2, "end": 3.4, "text": "walk me home"},
            {"start": 65.0, "end": 67.0, "text": "forget it"},
        ]

        content = module.to_vtt(segments)

        self.assertIn("WEBVTT", content)
        self.assertIn("00:00:01.200 --> 00:00:03.400", content)
        self.assertIn("walk me home", content)
        self.assertIn("00:01:05.000 --> 00:01:07.000", content)

    def test_download_audio_uses_audio_only_format_without_video_or_transcode(self):
        module = load_module()
        calls = []
        module.yt_dlp_command = lambda: ["yt-dlp"]

        def fake_run(command, **_kwargs):
            calls.append(command)
            output_template = Path(command[command.index("-o") + 1])
            Path(str(output_template).replace("%(ext)s", "m4a")).write_text("audio", encoding="utf-8")
            return types.SimpleNamespace(returncode=0)

        module.subprocess.run = fake_run
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = module.download_audio(
                "https://example.com/watch?v=abc123",
                Path(tmp),
                "abc123",
            )

        command = calls[0]
        self.assertIn("-f", command)
        self.assertIn("ba[ext=m4a]/ba/bestaudio", command)
        self.assertNotIn("--extract-audio", command)
        self.assertNotIn("--write-video", command)
        self.assertTrue(str(audio_path).endswith("abc123.m4a"))

    def test_missing_faster_whisper_returns_friendly_error(self):
        module = load_module()
        module.importlib.util.find_spec = lambda name: None

        with self.assertRaises(SystemExit) as raised:
            module.ensure_transcriber_available()

        self.assertIn("faster-whisper is required", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
