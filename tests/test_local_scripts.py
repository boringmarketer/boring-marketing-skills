"""Unit tests for local-business helper scripts: call_log.py, page_facts.py, site_check.py."""
import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load_module(rel_path, mod_name):
    spec = importlib.util.spec_from_file_location(mod_name, ROOT / rel_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


call_log = load_module("skills/speed-to-lead/scripts/call_log.py", "bms_call_log")
call_log_inc = load_module("skills/ads-incrementality-check/scripts/call_log.py", "bms_call_log_inc")
page_facts = load_module("skills/first-screen-check/scripts/page_facts.py", "bms_page_facts")
site_check = load_module("skills/find-local-clients/scripts/site_check.py", "bms_site_check")


class CallLogTests(unittest.TestCase):
    def test_copies_are_in_sync(self):
        a = (ROOT / "skills/speed-to-lead/scripts/call_log.py").read_text(encoding="utf-8")
        b = (ROOT / "skills/ads-incrementality-check/scripts/call_log.py").read_text(encoding="utf-8")
        self.assertEqual(a, b)

    def test_parse_hours_wrap_around_sun_thu(self):
        hours = call_log.parse_hours("Sun-Thu 08:00-17:00")
        # Sun=6, Mon=0, Tue=1, Wed=2, Thu=3; Fri=4, Sat=5 off
        self.assertEqual(set(hours.keys()), {6, 0, 1, 2, 3})
        # Sunday 10:00 is in hours; Friday 10:00 is after hours
        self.assertTrue(call_log.in_hours(datetime(2026, 11, 22, 10, 0), hours))
        self.assertFalse(call_log.in_hours(datetime(2026, 11, 20, 10, 0), hours))

    def test_in_hours_overnight_shift(self):
        hours = call_log.parse_hours("Mon-Fri 22:00-06:00")
        # Monday 23:30 is in hours; Tuesday 03:00 (from Monday shift) is in hours
        self.assertTrue(call_log.in_hours(datetime(2026, 11, 23, 23, 30), hours))
        self.assertTrue(call_log.in_hours(datetime(2026, 11, 24, 3, 0), hours))
        # Saturday 03:00 (from Friday night shift) is in hours; Saturday 23:00 is out
        self.assertTrue(call_log.in_hours(datetime(2026, 11, 28, 3, 0), hours))
        self.assertFalse(call_log.in_hours(datetime(2026, 11, 28, 23, 0), hours))
        # Monday 12:00 is out
        self.assertFalse(call_log.in_hours(datetime(2026, 11, 23, 12, 0), hours))

    def test_internal_calls_not_classified_as_inbound(self):
        csv_body = (
            "started_at,direction,status,duration,from,to\n"
            "2026-11-22 09:00:00,inbound,answered,65,+12145550101,+12145550000\n"
            "2026-11-22 09:05:00,internal,missed,0,101,102\n"
            "2026-11-22 09:10:00,outbound,answered,40,+12145550000,+12145550101\n"
        )
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "calls.csv"
            p.write_text(csv_body, encoding="utf-8")
            args = mock.Mock(
                time_col=None, direction_col=None, status_col=None, duration_col=None,
                from_col=None, to_col=None, party_col=None, line_col=None,
                exclude=None, line=None, utc_offset=0,
            )
            with redirect_stdout(io.StringIO()):
                rows = call_log.load(str(p), args)
            inbound = [r for r in rows if r["inbound"]]
            self.assertEqual(len(inbound), 1)
            self.assertEqual(inbound[0]["num"], "2145550101")

    def test_digits_preserves_international_e164(self):
        self.assertEqual(call_log.digits("+1 (214) 555-0199"), "2145550199")
        self.assertEqual(call_log.digits("214-555-0199"), "2145550199")
        self.assertEqual(call_log.digits("+966 50 123 4567"), "966501234567")
        self.assertEqual(call_log.digits("+971 50 123 4567"), "971501234567")
        self.assertNotEqual(
            call_log.digits("+966 50 123 4567"),
            call_log.digits("+971 50 123 4567"),
        )


class PhoneAndImageChecksTests(unittest.TestCase):
    def test_phone_regex_matches_us_and_international(self):
        samples = [
            "Call (214) 555-0199 now",
            "Call +966 50 123 4567 today",
            "Dubai office: +971 4 123 4567",
            "London: +44 20 7946 0958",
        ]
        for s in samples:
            with self.subTest(sample=s):
                self.assertIsNotNone(site_check.PHONE_RE.search(s))
                self.assertIsNotNone(page_facts.PHONE_RE.search(s))

    def test_image_kb_handles_malformed_content_length(self):
        def fake_fetch(url, method="GET", timeout=25):
            if method == "HEAD":
                return 200, url, {"Content-Length": "1024, 1024"}, b"", []
            return 200, url, {}, b"x" * 4096, []

        with mock.patch.object(page_facts, "fetch", side_effect=fake_fetch):
            self.assertEqual(page_facts.image_kb("https://example.com/a.webp"), "4 KB")


if __name__ == "__main__":
    unittest.main()
