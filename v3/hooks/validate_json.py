#!/usr/bin/env python3
"""Validate knowledge entry JSON files.

Usage:
    python hooks/validate_json.py <json_file> [json_file2 ...]
    python hooks/validate_json.py knowledge/articles/*.json
"""

import glob
import json
import re
import sys
from pathlib import Path


REQUIRED_FIELDS: dict[str, type] = {
    "id": str,
    "title": str,
    "source_url": str,
    "summary": str,
    "tags": list,
    "status": str,
}

VALID_STATUSES = {"draft", "review", "published", "archived"}
VALID_AUDIENCES = {"beginner", "intermediate", "advanced"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]+-\d{8}-\d{3}$")
URL_PATTERN = re.compile(r"^https?://")


def validate_entry(entry: object) -> list[str]:
    errors: list[str] = []

    if not isinstance(entry, dict):
        return ["top-level value is not an object"]

    for field, field_type in REQUIRED_FIELDS.items():
        if field not in entry:
            errors.append(f"missing required field: {field}")
        elif not isinstance(entry[field], field_type):
            errors.append(
                f"field '{field}' type mismatch: "
                f"expected {field_type.__name__}, "
                f"got {type(entry[field]).__name__}"
            )

    if errors:
        return errors

    id_val = entry["id"]
    if not ID_PATTERN.match(id_val):
        errors.append(
            f"field 'id' format mismatch: '{id_val}' "
            f"(expected {{source}}-{{YYYYMMDD}}-{{NNN}})"
        )

    source_url = entry["source_url"]
    if not URL_PATTERN.match(source_url):
        errors.append(
            f"field 'source_url' format mismatch: '{source_url}' "
            "(expected http:// or https:// URL)"
        )

    summary = entry["summary"]
    if len(summary) < 20:
        errors.append(
            f"field 'summary' too short: {len(summary)} chars "
            "(minimum 20)"
        )

    if len(entry["tags"]) < 1:
        errors.append("field 'tags' must have at least 1 tag")

    status = entry["status"]
    if status not in VALID_STATUSES:
        errors.append(
            f"field 'status' invalid: '{status}' "
            f"(expected one of {', '.join(sorted(VALID_STATUSES))})"
        )

    if "score" in entry:
        score = entry["score"]
        if not isinstance(score, (int, float)):
            errors.append(
                f"field 'score' type mismatch: "
                f"expected int or float, got {type(score).__name__}"
            )
        elif not 1 <= score <= 10:
            errors.append(
                f"field 'score' out of range: {score} "
                "(expected 1-10)"
            )

    if "audience" in entry:
        audience = entry["audience"]
        if not isinstance(audience, str):
            errors.append(
                f"field 'audience' type mismatch: "
                f"expected str, got {type(audience).__name__}"
            )
        elif audience not in VALID_AUDIENCES:
            errors.append(
                f"field 'audience' invalid: '{audience}' "
                f"(expected one of {', '.join(sorted(VALID_AUDIENCES))})"
            )

    return errors


def validate_file(filepath: Path) -> tuple[int, int, list[str]]:
    file_errors: list[str] = []
    entry_count = 0
    error_count = 0

    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return 0, 1, [f"  invalid JSON: {e}"]

    entries = data if isinstance(data, list) else [data]

    for i, entry in enumerate(entries, 1):
        entry_count += 1
        errs = validate_entry(entry)
        if errs:
            error_count += 1
            file_errors.append(f"  entry #{i}:")
            for err in errs:
                file_errors.append(f"    - {err}")

    return entry_count, error_count, file_errors


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python hooks/validate_json.py <json_file> [json_file2 ...]")
        return 1

    total_files = 0
    total_entries = 0
    total_errors = 0
    any_failed = False

    for pattern in sys.argv[1:]:
        matched = False
        for path_str in sorted(glob.glob(pattern)):
            matched = True
            filepath = Path(path_str)

            if not filepath.is_file():
                continue

            total_files += 1
            entry_count, error_count, errors = validate_file(filepath)
            total_entries += entry_count
            total_errors += error_count

            if errors:
                any_failed = True
                print(f"{filepath}: FAILED")
                for line in errors:
                    print(line)
            else:
                print(f"{filepath}: OK ({entry_count} entries)")

        if not matched:
            print(f"{pattern}: no matching files")

    print()
    print(f"Summary: {total_files} file(s), {total_entries} entry(ies), "
          f"{total_errors} file(s) with errors")

    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
