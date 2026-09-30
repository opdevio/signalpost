#!/usr/bin/env python3
"""Freeze a reproducible local test slice out of a full Brreg entity snapshot.

Selects companies with the same deterministic sampler the entry uses, then
writes three artifacts so the slice can be replayed without the full
snapshot:

  * a mini snapshot carrying exactly the selected registry rows, in the
    source CSV dialect (this is what ``run_competition_batch.py --bulk`` reads);
  * the organisation-number input list, carrying the sampler's split labels;
  * selection metadata, including the source snapshot checksum.

Usage:
  python3 build_local_slice.py --snapshot enheter-frozen.csv.gz \
      --count 100 --snapshot-dir data --prefix smoke-100
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from norway_company_agent.sampling import (  # noqa: E402
    deterministic_financial_filer_sample,
    iter_bulk,
    normalize_row,
)

LATEST_YEAR = "2025"
SEED = 20260825


def sniff_dialect(text: str) -> csv.Dialect:
    return csv.Sniffer().sniff(text[:8192], delimiters=";,\t")


def source_header(path: Path) -> tuple[list[str], csv.Dialect]:
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(8192)
        handle.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        return next(csv.reader(handle, dialect=dialect)), dialect


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True, help="Full entity snapshot .csv.gz")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--snapshot-dir", required=True, help="Directory for the written slice")
    parser.add_argument("--prefix", default="smoke")
    parser.add_argument("--latest-year", default=LATEST_YEAR)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    source = Path(args.snapshot)
    snapshot_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    selected, selection_metadata = deterministic_financial_filer_sample(
        source,
        args.count,
        latest_year=args.latest_year,
        seed=args.seed,
    )
    if len(selected) != args.count:
        raise SystemExit(f"Sampler returned {len(selected)} rows, expected {args.count}")
    wanted = {item["organisation_number"] for item in selected}

    header, dialect = source_header(source)
    raw_rows: dict[str, list[str]] = {}
    with gzip.open(source, "rt", encoding="utf-8-sig", newline="") as handle:
        handle.readline()
        for row in csv.reader(handle, dialect=dialect):
            if not row:
                continue
            org = "".join(character for character in row[0] if character.isdigit())
            if org in wanted and org not in raw_rows:
                raw_rows[org] = row
                if len(raw_rows) == len(wanted):
                    break
    missing = sorted(wanted - set(raw_rows))
    if missing:
        raise SystemExit(f"Selected organisations absent from snapshot: {missing[:10]}")

    outdir = Path(args.snapshot_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    slice_path = outdir / f"{args.prefix}-snapshot.csv.gz"
    stream = io.StringIO()
    writer = csv.writer(stream, dialect=dialect)
    writer.writerow(header)
    for item in selected:
        writer.writerow(raw_rows[item["organisation_number"]])
    with gzip.open(slice_path, "wt", encoding="utf-8-sig", newline="") as handle:
        handle.write(stream.getvalue())

    # The slice is only usable if the reader sees the same registry rows the
    # source produced, so compare before publishing anything.
    replayed = {item["organisation_number"]: item for item in iter_bulk(slice_path)}
    if set(replayed) != wanted:
        raise SystemExit("Replayed slice membership differs from the selection")
    for item in selected:
        if replayed[item["organisation_number"]]["raw"] != normalize_row(
            dict(zip(header, raw_rows[item["organisation_number"]], strict=True))
        )["raw"]:
            raise SystemExit(
                f"Replayed row differs from source row for {item['organisation_number']}"
            )

    orgs_path = outdir / f"{args.prefix}-organisations.jsonl"
    with orgs_path.open("w", encoding="utf-8") as handle:
        for item in selected:
            handle.write(
                json.dumps(
                    {
                        "organisation_number": item["organisation_number"],
                        "evaluation_split": item["evaluation_split"],
                        "sample_slice": item["sample_slice"],
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )

    metadata = {
        "source_snapshot_sha256": snapshot_sha256,
        "slice_sha256": hashlib.sha256(slice_path.read_bytes()).hexdigest(),
        "rows": len(selected),
        "columns": len(header),
        "selection": selection_metadata,
    }
    metadata_path = outdir / f"{args.prefix}-slice-metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in metadata.items() if k != "financial_stratum_counts"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
