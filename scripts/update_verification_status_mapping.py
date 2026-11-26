"""Propose additions to the shipped identificationVerificationStatus mapping.

Runs a GBIF SQL download listing every distinct identificationVerificationStatus
value with its number of records, classifies the values that are not yet in
dashboard/verification_status_classification.json with simple rules, appends
them to that file and writes a Markdown summary meant as a pull request body.
A human reviews the result: the rules are a first draft, not the decision.

Existing entries are never changed or removed. New values the rules consider
verified are always added; new unverified values only when they have at least
--min-count records (anything missing from the file already counts as
unverified, so the long tail of one-off junk values is left out).

Standard library only, so it runs in a GitHub Action without installing the
project. Usage:

    # Full run (needs GBIF_DOWNLOAD_USERNAME / GBIF_DOWNLOAD_PASSWORD):
    python scripts/update_verification_status_mapping.py --body-file body.md
    # Reuse an existing download, or a zip already on disk:
    python scripts/update_verification_status_mapping.py --download-key 0026928-260208012135463
    python scripts/update_verification_status_mapping.py --zip 0026928-260208012135463.zip
"""

import argparse
import base64
import csv
import io
import json
import os
import re
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

MAPPING_PATH = (
    Path(__file__).resolve().parent.parent
    / "dashboard"
    / "verification_status_classification.json"
)
GBIF_DOWNLOAD_API = "https://api.gbif.org/v1/occurrence/download"
FAILED_DOWNLOAD_STATUSES = {"FAILED", "KILLED", "CANCELLED", "FILE_ERASED"}
# Longest list per section in the PR body (GitHub caps bodies at 65536 chars);
# the full list is always in the diff.
MAX_LISTED = 150

# Rules from riparias/gbif-alert#43, which produced the initial mapping.
# Case-insensitive, anchored at the start so "not validated" is not caught
# by "^validated".
VERIFIED_PATTERNS = [
    r"^accepted",
    r"^approved",
    r"^valid$",
    r"^validated",
    r"^verified",
    r"^confirmed",
    r"^certain",
    r"^highly probable$",
    r"^probably correct$",
    r"^probable, high degree of reliability$",
    r"^need not be validated$",
    r"^reported by expert$",
    r"^automatic validation$",
    r"^validatedby",
    r"^verificado",
    r"^provjereno",  # Croatian: verified
    r"^sighting certified$",
    r"^specimen certified$",
    r"^certified",
]
# Exceptions: NOT verified despite matching a pattern above.
NOT_VERIFIED_PATTERNS = [
    r"^semi automatic validation based on the expertise of the observer$",
    r"^accepted \(plausible\)$",  # Waarnemingen.be, decided in #522
]


def is_verified(status: str) -> bool:
    """Draft verdict for one status value (the reviewer has the last word)."""
    s = status.strip()
    if any(re.search(p, s, re.IGNORECASE) for p in NOT_VERIFIED_PATTERNS):
        return False
    return any(re.search(p, s, re.IGNORECASE) for p in VERIFIED_PATTERNS)


def build_sql(continent: str | None) -> str:
    where = f"WHERE continent = '{continent}' " if continent else ""
    return (
        'SELECT "identificationverificationstatus", COUNT(*) FROM occurrence '
        f'{where}GROUP BY "identificationverificationstatus"'
    )


def _gbif_request(
    url: str, data: bytes | None = None, auth: tuple[str, str] | None = None
) -> bytes:
    request = urllib.request.Request(url, data=data)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if auth is not None:
        token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        request.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read()


def request_download(sql: str, username: str, password: str) -> str:
    """Submit the SQL download, return its key."""
    body = json.dumps({"sendNotification": False, "format": "SQL_TSV_ZIP", "sql": sql})
    return (
        _gbif_request(
            f"{GBIF_DOWNLOAD_API}/request", body.encode(), (username, password)
        )
        .decode()
        .strip()
    )


def wait_for_download(key: str, timeout_s: float, poll_s: float = 120) -> None:
    """Poll until the download succeeded; raise if it failed or took too long."""
    deadline = time.monotonic() + timeout_s
    while True:
        status = json.loads(_gbif_request(f"{GBIF_DOWNLOAD_API}/{key}"))["status"]
        print(f"GBIF download {key}: {status}", file=sys.stderr)
        if status == "SUCCEEDED":
            return
        if status in FAILED_DOWNLOAD_STATUSES:
            raise RuntimeError(f"GBIF download {key} ended with status {status}")
        if time.monotonic() > deadline:
            raise TimeoutError(f"GBIF download {key} still {status} after timeout")
        time.sleep(poll_s)


def read_counts(zip_bytes: bytes) -> dict[str, int]:
    """Parse the download's TSV into {status value: number of records}."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        (name,) = [n for n in archive.namelist() if not n.endswith("/")]
        text = archive.read(name).decode("utf-8")
    # QUOTE_NONE: values are raw publisher strings, quotes in them are literal
    reader = csv.reader(io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE)
    next(reader)  # header
    return {row[0]: int(row[1]) for row in reader if len(row) >= 2}


def propose(
    existing: list[dict], counts: dict[str, int], min_count: int
) -> tuple[list[dict], int]:
    """New entries to append (verified first, then by record count) and the
    number of new values left out because they are below min_count."""
    known = {entry["key"] for entry in existing}
    added: list[dict] = []
    skipped = 0
    for status, count in counts.items():
        if status in known:
            continue
        verified = is_verified(status)
        if verified or count >= min_count:
            added.append({"key": status, "verified": verified})
        else:
            skipped += 1
    added.sort(key=lambda e: (not e["verified"], -counts[e["key"]], e["key"]))
    return added, skipped


def pr_body(
    added: list[dict], counts: dict[str, int], skipped: int, min_count: int, source: str
) -> str:
    def section(title: str, entries: list[dict]) -> list[str]:
        lines = [f"### {title} ({len(entries)})", ""]
        lines += [
            f"- `{e['key']}` ({counts[e['key']]} records)" for e in entries[:MAX_LISTED]
        ]
        if len(entries) > MAX_LISTED:
            lines.append(f"- ... and {len(entries) - MAX_LISTED} more, see the diff")
        return lines + [""]

    verified = [e for e in added if e["verified"]]
    unverified = [e for e in added if not e["verified"]]
    return "\n".join(
        [
            f"New `identificationVerificationStatus` values from {source}, "
            "classified by the rules in "
            "`scripts/update_verification_status_mapping.py`.",
            "",
            "Please review before merging (edit the JSON on this branch to "
            'change a verdict). A wrong "verified" puts unverified records in '
            "verified-only alerts; a missed one (often a non-English value) "
            "hides verified records from them.",
            "",
            *section("Proposed as verified - check each one", verified),
            *section(
                "Proposed as unverified - skim for missed verified values", unverified
            ),
            f"{skipped} other new values have fewer than {min_count} records "
            "and were left out (they count as unverified).",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--download-key", help="reuse this GBIF download")
    source.add_argument("--zip", type=Path, help="read this downloaded zip")
    parser.add_argument("--continent", help="e.g. EUROPE (default: whole world)")
    parser.add_argument("--min-count", type=int, default=10)
    parser.add_argument("--timeout-hours", type=float, default=5)
    parser.add_argument("--body-file", type=Path, help="write the PR body here")
    args = parser.parse_args()

    if args.zip:
        zip_bytes, origin = args.zip.read_bytes(), f"`{args.zip.name}`"
    else:
        key = args.download_key
        if key is None:
            key = request_download(
                build_sql(args.continent),
                os.environ["GBIF_DOWNLOAD_USERNAME"],
                os.environ["GBIF_DOWNLOAD_PASSWORD"],
            )
            print(f"Requested GBIF download {key}", file=sys.stderr)
        wait_for_download(key, args.timeout_hours * 3600)
        zip_bytes = _gbif_request(f"{GBIF_DOWNLOAD_API}/request/{key}.zip")
        origin = (
            f"GBIF download [{key}](https://www.gbif.org/occurrence/download/{key})"
        )

    counts = read_counts(zip_bytes)
    existing = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    added, skipped = propose(existing, counts, args.min_count)
    print(
        f"{len(counts)} distinct values, {len(added)} added "
        f"({sum(e['verified'] for e in added)} verified), {skipped} below "
        f"--min-count {args.min_count}",
        file=sys.stderr,
    )
    if added:
        # Same formatting as the existing file, so the diff only shows additions
        MAPPING_PATH.write_text(
            json.dumps(existing + added, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    if args.body_file:
        args.body_file.write_text(
            pr_body(added, counts, skipped, args.min_count, origin), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
