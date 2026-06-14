import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "skills" / "video-study-digest" / "scripts" / "doctor.py"


def load_module():
    spec = importlib.util.spec_from_file_location("doctor", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class DoctorTests(unittest.TestCase):
    def test_doctor_reports_missing_optional_tools_without_failing(self):
        module = load_module()
        report = module.collect_report(
            cache_root=Path("/tmp/video-study"),
            command_exists=lambda _name: False,
            module_exists=lambda _name: False,
            python_version=(3, 11),
            check_writable=False,
        )

        statuses = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual(statuses["python"], "ok")
        self.assertEqual(statuses["yt-dlp"], "warn")
        self.assertEqual(statuses["faster-whisper"], "warn")
        self.assertEqual(report["overall_status"], "warn")

    def test_doctor_checks_cache_root_writable(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            report = module.collect_report(
                cache_root=Path(tmp),
                command_exists=lambda _name: True,
                module_exists=lambda _name: True,
                python_version=(3, 11),
                check_writable=True,
            )

        statuses = {item["name"]: item["status"] for item in report["checks"]}
        self.assertEqual(statuses["cache-root"], "ok")
        self.assertEqual(report["overall_status"], "ok")


if __name__ == "__main__":
    unittest.main()
