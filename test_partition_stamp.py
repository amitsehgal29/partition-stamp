"""Tests for partition-stamp. Run: python3 -m unittest"""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date

import partition_stamp


class ParseCalendarDateTests(unittest.TestCase):
    def test_accepts_real_date(self):
        self.assertEqual(
            partition_stamp.parse_calendar_date("2026-10-04"),
            date(2026, 10, 4),
        )

    def test_rejects_impossible_day_without_rollover(self):
        self.assertIsNone(partition_stamp.parse_calendar_date("2026-02-31"))
        self.assertIsNone(partition_stamp.parse_calendar_date("2026-04-31"))
        self.assertIsNone(partition_stamp.parse_calendar_date("2026-13-01"))

    def test_leap_day(self):
        self.assertEqual(
            partition_stamp.parse_calendar_date("2024-02-29"),
            date(2024, 2, 29),
        )
        self.assertIsNone(partition_stamp.parse_calendar_date("2026-02-29"))
        self.assertIsNone(partition_stamp.parse_calendar_date("1900-02-29"))

    def test_requires_exact_yyyy_mm_dd(self):
        self.assertIsNone(partition_stamp.parse_calendar_date("2026-2-01"))
        self.assertIsNone(partition_stamp.parse_calendar_date("04-10-2026"))
        self.assertIsNone(partition_stamp.parse_calendar_date("2026/10/04"))
        self.assertIsNone(partition_stamp.parse_calendar_date(""))


class StampTests(unittest.TestCase):
    TODAY = date(2026, 10, 4)

    def test_hive_path_for_today(self):
        got = partition_stamp.stamp("events", "2026-10-04", 7, self.TODAY)
        self.assertEqual(
            got,
            {
                "table": "events",
                "date": "2026-10-04",
                "partition": "events/dt=2026-10-04",
                "valid": True,
                "future": False,
                "older_than_max_age": False,
                "max_age_days": 7,
            },
        )

    def test_future_date_is_not_older(self):
        got = partition_stamp.stamp("events", "2026-10-05", 0, self.TODAY)
        self.assertEqual(got["partition"], "events/dt=2026-10-05")
        self.assertTrue(got["valid"])
        self.assertTrue(got["future"])
        self.assertFalse(got["older_than_max_age"])

    def test_strictly_older_than_max_age(self):
        # 2026-09-26 is 8 days before 2026-10-04.
        got = partition_stamp.stamp("events", "2026-09-26", 7, self.TODAY)
        self.assertFalse(got["future"])
        self.assertTrue(got["older_than_max_age"])

    def test_age_equal_to_max_age_is_not_older(self):
        # 2026-09-27 is exactly 7 days before 2026-10-04.
        self.assertEqual((self.TODAY - date(2026, 9, 27)).days, 7)
        got = partition_stamp.stamp("events", "2026-09-27", 7, self.TODAY)
        self.assertFalse(got["older_than_max_age"])

    def test_omitted_max_age_leaves_field_null(self):
        got = partition_stamp.stamp("events", "2020-01-01", None, self.TODAY)
        self.assertIsNone(got["max_age_days"])
        self.assertIsNone(got["older_than_max_age"])
        self.assertFalse(got["future"])
        self.assertEqual(got["partition"], "events/dt=2020-01-01")

    def test_invalid_date_does_not_invent_a_partition(self):
        got = partition_stamp.stamp("events", "2026-02-31", 30, self.TODAY)
        self.assertEqual(
            got,
            {
                "table": "events",
                "date": "2026-02-31",
                "partition": None,
                "valid": False,
                "future": None,
                "older_than_max_age": None,
                "max_age_days": 30,
            },
        )

    def test_rejects_unsafe_table_names(self):
        for table in ("", " ", "events/dt", "a\\b", ".", "..", " events"):
            with self.assertRaises(partition_stamp.StampError):
                partition_stamp.stamp(table, "2026-10-04", None, self.TODAY)

    def test_rejects_negative_max_age(self):
        with self.assertRaises(partition_stamp.StampError):
            partition_stamp.stamp("events", "2026-10-04", -1, self.TODAY)


class CliTests(unittest.TestCase):
    def test_sample_invocation(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = partition_stamp.main(
                ["orders", "2026-10-01", "--max-age", "7", "--today", "2026-10-04"]
            )
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["partition"], "orders/dt=2026-10-01")
        self.assertTrue(payload["valid"])
        self.assertFalse(payload["future"])
        self.assertFalse(payload["older_than_max_age"])
        self.assertEqual(payload["max_age_days"], 7)

    def test_invalid_date_still_prints_json(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = partition_stamp.main(
                ["orders", "2026-02-31", "--today", "2026-10-04"]
            )
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["valid"])
        self.assertIsNone(payload["partition"])
        self.assertIsNone(payload["future"])

    def test_bad_today_exits_2(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = partition_stamp.main(
                ["orders", "2026-10-04", "--today", "2026-02-31"]
            )
        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("real calendar date", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
