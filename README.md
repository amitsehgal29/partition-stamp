# partition-stamp

Small command-line check for Hive-style daily partitions. Give it a table
name and a `YYYY-MM-DD` date. It prints JSON with the partition path
`table/dt=YYYY-MM-DD`, whether that string is a real calendar date, whether
the date is in the future, and whether it is older than an optional max age
in days.

Impossible dates are invalid. `2026-02-31` is not rewritten as `2026-03-03`.

Uses only the Python standard library.

## Usage

```bash
python3 partition_stamp.py TABLE YYYY-MM-DD [--max-age DAYS] [--today YYYY-MM-DD]
```

`--today` overrides the local calendar date used for the future and age
checks. When it is omitted, the tool uses today's date.

`older_than_max_age` is `true` only when the date is valid and its age in
whole days is **strictly greater** than `--max-age`. A date exactly `N` days
old is not older than a max age of `N`. Future dates are not older. If
`--max-age` is omitted, `older_than_max_age` is `null`.

An invalid date still prints JSON (`valid: false`) and does not invent a
partition path. Bad table names, a negative max age, or an impossible
`--today` exit with status 2.

## Example

Three days before 4 Oct 2026, with a 7-day freshness window:

```bash
python3 partition_stamp.py orders 2026-10-01 --max-age 7 --today 2026-10-04
```

```json
{
  "table": "orders",
  "date": "2026-10-01",
  "partition": "orders/dt=2026-10-01",
  "valid": true,
  "future": false,
  "older_than_max_age": false,
  "max_age_days": 7
}
```

An impossible day:

```bash
python3 partition_stamp.py orders 2026-02-31 --max-age 7 --today 2026-10-04
```

```json
{
  "table": "orders",
  "date": "2026-02-31",
  "partition": null,
  "valid": false,
  "future": null,
  "older_than_max_age": null,
  "max_age_days": 7
}
```

## Tests

```bash
python3 -m unittest
```
