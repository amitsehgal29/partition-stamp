#!/usr/bin/env python3
"""Hive partition stamp: validate a calendar date and report freshness as JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date

DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


class StampError(ValueError):
    """User-facing input error that should not produce a stamp."""


def parse_calendar_date(value: str) -> date | None:
    """Return a real calendar date, or None.

    Impossible dates such as 2026-02-31 are rejected. They are not rolled
    forward into March.
    """
    match = DATE_RE.fullmatch(value)
    if match is None:
        return None
    year, month, day = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def stamp(
    table: str,
    date_text: str,
    max_age_days: int | None,
    today: date,
) -> dict:
    """Build the JSON payload for one table/date pair.

    ``older_than_max_age`` is true only when the date is a real calendar
    date whose age in whole days is strictly greater than ``max_age_days``.
    A missing max-age leaves that field null. Future dates are never older.
    """
    if (
        not table
        or table.strip() != table
        or "/" in table
        or "\\" in table
        or table in {".", ".."}
    ):
        raise StampError("table name must be a single non-empty path segment")
    if max_age_days is not None and max_age_days < 0:
        raise StampError("max-age must be zero or a positive number of days")

    parsed = parse_calendar_date(date_text)
    payload: dict = {
        "table": table,
        "date": date_text,
        "partition": None,
        "valid": parsed is not None,
        "future": None,
        "older_than_max_age": None,
        "max_age_days": max_age_days,
    }
    if parsed is None:
        return payload

    payload["partition"] = f"{table}/dt={parsed.isoformat()}"
    payload["future"] = parsed > today
    if max_age_days is not None:
        age_days = (today - parsed).days
        payload["older_than_max_age"] = age_days > max_age_days
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="partition-stamp",
        description=(
            "Print a Hive-style dt partition path and whether the date is "
            "real, in the future, or older than a max age."
        ),
    )
    parser.add_argument("table", help="Table name used as the partition prefix")
    parser.add_argument("date", help="Partition date as YYYY-MM-DD")
    parser.add_argument(
        "--max-age",
        dest="max_age",
        type=int,
        default=None,
        metavar="DAYS",
        help="Set older_than_max_age when age in whole days is greater than DAYS",
    )
    parser.add_argument(
        "--today",
        default=None,
        metavar="YYYY-MM-DD",
        help="Override the local calendar date used for future and age checks",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.today is None:
        today = date.today()
    else:
        today = parse_calendar_date(args.today)
        if today is None:
            print(
                "error: --today must be a real calendar date (YYYY-MM-DD)",
                file=sys.stderr,
            )
            return 2
    try:
        payload = stamp(args.table, args.date, args.max_age, today)
    except StampError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
