#!/usr/bin/env python3
"""Sanitize smoke artifacts for public publication.

Brreg role records carry named individuals and website evidence embeds
extracted page text. Public artifacts keep only an allowlist: run metadata,
per-module terminal states, company identity scalars, the declared website,
and counts of what was fetched. Evidence payloads (role records, page
extracts, spans) and their personal names are removed and replaced with
counts. Runs offline.

Usage: python3 sanitize_smoke_artifacts.py --input-envelopes RAW.jsonl \
    --input-profiles RAW.jsonl --output-envelopes SAN.jsonl \
    --output-profiles SAN.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PROFILE_SCALARS = (
    "organisation_number",
    "name",
    "legal_form",
    "employees",
    "bankrupt",
    "liquidating",
    "municipality",
    "municipality_number",
    "industry_code",
    "industry_label",
    "website",
    "evaluation_split",
)
ENVELOPE_SCALARS = (
    "run_id",
    "organisation_number",
    "state",
    "started_at",
    "completed_at",
)


def is_scalar(value: object) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def scalar_submap(value: object) -> dict:
    return {k: v for k, v in value.items() if is_scalar(v)} if isinstance(value, dict) else {}


def summarize_evidence(evidence: object, stats: dict) -> dict:
    """Replace module evidence payloads with states and record counts."""
    summary: dict = {}
    if not isinstance(evidence, dict):
        return summary
    for module, payload in evidence.items():
        if not isinstance(payload, dict):
            continue
        entry = {"state": payload.get("state")}
        value = payload.get("value")
        if isinstance(value, dict):
            inner = {k: v for k, v in value.items() if isinstance(v, list)}
            for name, items in inner.items():
                entry[f"{name}_count"] = len(items)
                stats["records_removed"] += len(items)
            stats["payloads_removed"] += 1
        elif isinstance(value, list):
            entry["record_count"] = len(value)
            stats["records_removed"] += len(value)
            stats["payloads_removed"] += 1
        summary[module] = entry
    return summary


def sanitize_profile(profile: dict, stats: dict) -> dict:
    clean = {k: profile[k] for k in PROFILE_SCALARS if k in profile and is_scalar(profile.get(k))}
    if "modules" in profile:
        clean["modules"] = {
            name: scalar_submap(state) for name, state in profile["modules"].items()
        }
    clean["evidence"] = summarize_evidence(profile.get("evidence"), stats)
    if "run_metrics" in profile:
        clean["run_metrics"] = scalar_submap(profile["run_metrics"])
    return clean


def sanitize_envelope(record: dict, stats: dict) -> dict:
    clean = {k: record[k] for k in ENVELOPE_SCALARS if k in record}
    if "modules" in record:
        clean["modules"] = {
            name: scalar_submap(state) for name, state in record["modules"].items()
        }
    if isinstance(record.get("profile"), dict):
        clean["profile"] = sanitize_profile(record["profile"], stats)
    return clean


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-envelopes", required=True)
    parser.add_argument("--input-profiles", required=True)
    parser.add_argument("--output-envelopes", required=True)
    parser.add_argument("--output-profiles", required=True)
    args = parser.parse_args()

    stats = {"envelopes": 0, "profiles": 0, "payloads_removed": 0, "records_removed": 0}
    jobs = (
        (args.input_envelopes, args.output_envelopes, "envelopes", sanitize_envelope),
        (args.input_profiles, args.output_profiles, "profiles", sanitize_profile),
    )
    for src, dst, label, handler in jobs:
        with Path(src).open(encoding="utf-8") as reader, Path(dst).open("w", encoding="utf-8") as writer:
            for line in reader:
                record = handler(json.loads(line), stats)
                stats[label] += 1
                writer.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
