#!/usr/bin/env python3
"""Record provenance for a registry snapshot already present on disk.

Used when the payload was fetched by a previous run that ended before its
metadata could be written: re-verifies the bytes (gzip stream integrity and
declared size) instead of trusting the filename.

Usage: python3 record_snapshot_metadata.py --input enheter-frozen.csv.gz \
    --metadata registry-snapshot-metadata.json [--expected-bytes N]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

SNAPSHOT_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--expected-bytes", type=int)
    parser.add_argument("--last-modified")
    parser.add_argument("--etag")
    parser.add_argument("--content-disposition")
    args = parser.parse_args()

    path = Path(args.input)
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    if args.expected_bytes is not None and size != args.expected_bytes:
        raise SystemExit(f"Snapshot is {size} bytes, server declared {args.expected_bytes}")
    with gzip.open(path, "rb") as handle:
        while handle.read(1024 * 1024):
            pass

    metadata = {
        "url": SNAPSHOT_URL,
        "verified_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "bytes": size,
        "sha256": digest.hexdigest(),
        "last_modified": args.last_modified,
        "etag": args.etag,
        "content_disposition": args.content_disposition,
        "licence": "Norsk kollektiv lisens for åpne data (NLOD) 2.0",
        "licence_url": "https://lovdata.no/dokument/NL/kapittel/om-aa-publisere",
    }
    target = Path(args.metadata)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
