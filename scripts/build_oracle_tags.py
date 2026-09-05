#!/usr/bin/env python3
"""Scryfall oracle-tags bulk → oracle_tags.csv (oracle_id, tag, weight)."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from pathlib import Path

from common import resolve_bulk_uri, request, upsert_build_info


def iter_bulk(uri: str):
    import urllib.request
    raw = urllib.request.urlopen(request(uri), timeout=300).read()
    if uri.endswith(".gz") or raw[:2] == b"\x1f\x8b":
        text = gzip.decompress(raw).decode("utf-8")
    else:
        text = raw.decode("utf-8")
    text = text.strip()
    if text.startswith("["):
        yield from json.loads(text)
        return
    for line in text.splitlines():
        line = line.strip().rstrip(",")
        if not line or line in "[]":
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="oracle_tags.csv")
    args = ap.parse_args()

    uri = resolve_bulk_uri("oracle-tags")
    rows = []
    for tag in iter_bulk(uri):
        slug = tag.get("slug") or tag.get("label") or ""
        for tagging in tag.get("taggings") or []:
            oid = tagging.get("oracle_id")
            if oid and slug:
                rows.append({
                    "oracle_id": oid,
                    "tag": slug,
                    "weight": tagging.get("weight") or "",
                })

    path = Path(args.out)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["oracle_id", "tag", "weight"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"[done] {len(rows)} tag rows -> {path}", file=sys.stderr)
    if len(rows) < 10000:
        print(f"[FAIL] only {len(rows)} oracle-tag rows; refusing to publish", file=sys.stderr)
        sys.exit(1)
    upsert_build_info(Path("BUILD_INFO.txt"), oracle_tags=len(rows))


if __name__ == "__main__":
    main()
