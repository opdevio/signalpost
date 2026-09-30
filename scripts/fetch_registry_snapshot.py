#!/usr/bin/env python3
"""Download the frozen Brreg entity snapshot used to build a local test slice.

Writes the payload and a metadata record describing exactly what was fetched,
so a later run can prove which snapshot a slice was drawn from.

Usage: python3 fetch_registry_snapshot.py --output /out/enheter-frozen.csv.gz
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SNAPSHOT_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv"
USER_AGENT = "builderr-signalpost-poc/0.1 (+https://builderr.ai)"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="Destination .csv.gz path")
    parser.add_argument("--metadata", help="Optional destination metadata JSON path")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    digest = hashlib.sha256()
    size = 0
    started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    request = urllib.request.Request(SNAPSHOT_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=args.timeout) as response:
        headers = {key.lower(): value for key, value in response.headers.items()}
        with temporary.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                digest.update(chunk)
                handle.write(chunk)
                size += len(chunk)
    completed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    temporary.replace(destination)

    # Read the whole stream through the gzip decoder: a truncated download must
    # not be handed to the sampler as if it were a complete snapshot.
    with gzip.open(destination, "rb") as handle:
        while handle.read(1024 * 1024):
            pass

    metadata = {
        "url": SNAPSHOT_URL,
        "started_at": started_at,
        "completed_at": completed_at,
        "bytes": size,
        "sha256": digest.hexdigest(),
        "content_type": headers.get("content-type"),
        "last_modified": headers.get("last-modified"),
        "etag": headers.get("etag"),
        "content_disposition": headers.get("content-disposition"),
        "licence": "Norsk kollektiv lisens for åpne data (NLOD) 2.0",
        "licence_url": "https://lovdata.no/dokument/NL/kapittel/om-aa-publisere",
    }
    if args.metadata:
        target = Path(args.metadata)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
