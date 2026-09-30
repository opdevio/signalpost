# Signalpost

An agent that builds company profiles from Norwegian public data and reports
what it found with the evidence behind each claim. For each company it reads
the registry snapshot and the live Brreg endpoints for financials, roles,
group relationships and locations, then checks the company's own website.
Every claim carries the source URL and content hash that supports it. Where
something could not be checked, the record says so instead of guessing.

This repository is our entry for Builderr Signalpost Round 1.

## Evaluate it

One command, from an empty folder, pinned to the submitted commit
`c26d4a85f68db9e2327ed12ed0132576434c892a`. It needs git, Python 3.12+ and
network access (the run fetches Brreg and company websites live). It clones
the repository at that commit, creates an empty virtual environment, runs
only the declared install step (`pip install -r requirements.txt`), then
runs the 100-company smoke test; the run takes a few minutes and writes
`smoke-report.json` plus the per-company envelopes and profiles inside the
clone.

```bash
git clone https://github.com/opdevio/signalpost.git signalpost && cd signalpost && git checkout --detach c26d4a85f68db9e2327ed12ed0132576434c892a && python3 -m venv .venv && .venv/bin/pip install --no-cache-dir -r requirements.txt && .venv/bin/python3 scripts/run_competition_batch.py --organisations data/smoke-100-organisations.jsonl --bulk data/smoke-100-snapshot.csv.gz --output smoke-envelopes.jsonl --profiles-output smoke-profiles.jsonl --report smoke-report.json --run-id evaluator-smoke --expected-count 100 --workers 8
```

`artifacts/smoke-report.json` is the report from our own run of that command
at the pinned commit: 100/100 terminal envelopes, zero silent drops,
validation passed, 441 requests, 1.89 MB, p50 597 ms / p95 782 ms, about
72 s wall with 8 workers.

## The smoke slice

The 100 companies are a deterministic sample (seed 20260825) of active
companies with 2025 financial statements in the Brreg snapshot, drawn with
the same sampler that builds the project's larger evaluation splits. The
frozen 100-row registry slice and the 100 organisation numbers live in
`data/`, so the smoke test needs no registry download. Their provenance —
snapshot URL, byte size, SHA-256, date, and the slice hash — is in the
metadata files beside them.

## Models, APIs, licences

- **No LLM or ML model.** All logic is deterministic code over structured
  registry data and HTML parsing.
- **APIs:** Brreg (the Norwegian registry) open data and public company
  websites, fetched over plain HTTPS. No API keys, no paid tiers.
- **Data licence:** the registry snapshot is the Norwegian Central Coordinating
  Register for Business Entities, made available under the Norwegian Licence
  for Open Data (NLOD 2.0). Company websites are read to check publicly
  published facts and are not redistributed: profiles store URLs and content
  hashes, not page copies.
- **Dependencies:** permissive open-source Python packages, pinned with hashes
  in `requirements.txt`.

## Cost per official batch

**$0.00.** No paid model and no paid API is used. Brreg open data is free and
requires no key, so a full 1,000-company official batch is expected to cost
nothing in third-party fees. The smoke run above makes about 4.4 requests per
company; a 1,000-company batch extrapolates to roughly 4,400 requests and
19 MB, in the low tens of minutes with 8 workers.

## Repository layout

- `src/norway_company_agent/` — the agent.
- `scripts/` — batch runner, snapshot fetch and slice builder.
- `data/` — frozen smoke slice and provenance metadata.
- `artifacts/` — committed output of the smoke run.
- `tests/` — unit tests (`python -m unittest discover tests` inside the venv).
- `OUTPUT_CONTRACT.md` — the per-company JSON envelope the agent must emit.

Agent name: Signalpost. Contact: hello@opdevio.xyz.
