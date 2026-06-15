"""Tests for production API log file configuration."""

import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from config.logging_config import build_logging_config


class LoggingConfigTest(SimpleTestCase):
    def test_no_file_handler_when_path_unset(self):
        config = build_logging_config(
            debug=False,
            verbose=False,
            log_path="",
            max_bytes=1024,
            backup_count=3,
            base_dir=Path("/tmp"),
            running_tests=False,
        )
        self.assertEqual(config["loggers"]["issuer"]["handlers"], ["console"])
        self.assertNotIn("issuer_api_file", config["handlers"])

    def test_file_handler_skipped_during_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "issuer-api.log"
            config = build_logging_config(
                debug=False,
                verbose=False,
                log_path=str(log_path),
                max_bytes=1024,
                backup_count=3,
                base_dir=Path(tmp),
                running_tests=True,
            )
            self.assertEqual(config["loggers"]["issuer"]["handlers"], ["console"])

    def test_file_handler_for_project_local_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            log_path = base / "logs" / "issuer-api.log"
            config = build_logging_config(
                debug=False,
                verbose=False,
                log_path=str(log_path),
                max_bytes=1024,
                backup_count=3,
                base_dir=base,
                running_tests=False,
            )
            self.assertIn("issuer_api_file", config["handlers"])
            self.assertIn("issuer_api_file", config["loggers"]["issuer"]["handlers"])
            self.assertEqual(config["handlers"]["issuer_api_file"]["level"], "INFO")
            self.assertEqual(config["handlers"]["issuer_api_file"]["filters"], ["no_exc_info"])
            self.assertTrue(log_path.parent.exists())

    def test_verbose_debug_on_console_only(self):
        config = build_logging_config(
            debug=False,
            verbose=True,
            log_path="",
            max_bytes=1024,
            backup_count=3,
            base_dir=Path("/tmp"),
            running_tests=True,
        )
        self.assertEqual(config["handlers"]["console"]["level"], "DEBUG")
        self.assertEqual(config["loggers"]["issuer"]["level"], "DEBUG")
