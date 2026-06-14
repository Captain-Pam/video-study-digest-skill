import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "skills" / "video-study-digest" / "scripts" / "video_digest_pipeline.py"


def load_module():
    spec = importlib.util.spec_from_file_location("video_digest_pipeline", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class VideoDigestPipelineTests(unittest.TestCase):
    def test_local_timestamped_transcript_writes_outputs_and_report(self):
        module = load_module()
        sample = """WEBVTT

00:00:01.000 --> 00:00:03.000
Hello from captions.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "sample.vtt"
            output_dir = tmp_path / "out"
            source.write_text(sample, encoding="utf-8")

            result = module.run_pipeline(
                source=str(source),
                output_dir=output_dir,
                transcribe_if_needed=False,
            )

            transcript = output_dir / "transcript.md"
            report = output_dir / "run_report.json"

            self.assertEqual(result["transcript_method"], "local-transcript")
            self.assertTrue(transcript.exists())
            self.assertTrue(report.exists())
            self.assertIn("Hello from captions.", transcript.read_text(encoding="utf-8"))

            report_data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(report_data["transcript_method"], "local-transcript")
            self.assertEqual(report_data["status"], "ok")

    def test_url_caption_temp_directory_uses_cache_root(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cache_root = tmp_path / "cache"
            output_dir = tmp_path / "out"
            captured: dict[str, Path] = {}

            original_write_source_context = module.write_source_context
            original_download_subtitles = module.prepare_transcript.download_subtitles
            original_parse_transcript = module.prepare_transcript.parse_transcript
            try:
                module.write_source_context = lambda _source, _output_dir, _warnings: {}

                def fake_download_subtitles(_source, temp_dir, _languages):
                    captured["temp_dir"] = temp_dir
                    subtitle_path = temp_dir / "captions.vtt"
                    subtitle_path.write_text(
                        "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nCaption text.\n",
                        encoding="utf-8",
                    )
                    return subtitle_path

                module.prepare_transcript.download_subtitles = fake_download_subtitles
                module.prepare_transcript.parse_transcript = lambda _path: [
                    {"timestamp": "00:00:00", "start": 0.0, "end": 1.0, "text": "Caption text."}
                ]

                result = module.run_pipeline(
                    source="https://example.com/watch?v=1",
                    output_dir=output_dir,
                    cache_root=cache_root,
                )
            finally:
                module.write_source_context = original_write_source_context
                module.prepare_transcript.download_subtitles = original_download_subtitles
                module.prepare_transcript.parse_transcript = original_parse_transcript

            self.assertEqual(result["status"], "ok")
            self.assertEqual(captured["temp_dir"].parent, cache_root / "tmp")


if __name__ == "__main__":
    unittest.main()
