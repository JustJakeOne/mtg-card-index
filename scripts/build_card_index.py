#!/usr/bin/env python3
"""
Build a compact MTG card index from Scryfall bulk data.

Streams the gzipped JSONL bulk file line by line (constant memory, never loads
the whole file) and collapses every printing down to one row per oracle card,
keeping the cheapest paper USD price seen across printings.

Usage:
    python build_card_index.py --bulk default_cards --out cards.csv
    python build_card_index.py --input local.jsonl.gz --out cards.csv   # offline
"""

import argparse
import csv
import gzip
import json
import sys
import urllib.request
from datetime import datetime, timezone

BULK_INDEX = "https://api.scryfall.com/bulk-data/{}"
UA = "ulamog-card-index/1.0 (deck validation; contact: thegloriousexcess@gmail.com)"

# Layouts that are not real, castable cards and only add noise.
SKIP_LAYOUTS = {
    "token", "double_faced_token", "emblem", "art_series",
    "scheme", "planar", "vanguard", "augment", "host",
}

FIELDNAMES = [
    "name", "front_name", "mana_cost", "cmc", "color_identity",
    "type_line", "layout", "commander_legal", "usd_min", "usd_min_set",
    "oracle_id",
]


def resolve_bulk_uri(bulk_type: str) -> str:
    """Ask Scryfall where today's bulk file lives. URI changes daily."""
    req = urllib.request.Request(
        BULK_INDEX.format(bulk_type), headers={"User-Agent": UA, "Accept": "*/*"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        meta = json.load(resp)
    # Scryfall is retiring plain JSON in favour of JSONL. Prefer JSONL, fall back.
    uri = meta.get("jsonl_download_uri") or meta.get("download_uri")
    if not uri:
        raise SystemExit(f"No download URI in bulk-data object for {bulk_type!r}")
    print(f"[bulk] {bulk_type} updated_at={meta.get('updated_at')} "
          f"size={meta.get('size')} -> {uri}", file=sys.stderr)
    return uri


def open_stream(uri: str):
    if uri.startswith("http"):
        req = urllib.request.Request(uri, headers={"User-Agent": UA})
        return gzip.open(urllib.request.urlopen(req, timeout=300), "rt", encoding="utf-8")
    return gzip.open(uri, "rt", encoding="utf-8") if uri.endswith(".gz") \
        else open(uri, "rt", encoding="utf-8")


def paper_usd(card: dict):
    """Cheapest non-foil paper USD price, or None. Digital printings excluded."""
    if card.get("digital"):
        return None
    if "paper" not in (card.get("games") or []):
        return None
    raw = (card.get("prices") or {}).get("usd")
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def build(stream, out_path: str) -> int:
    index: dict[str, dict] = {}
    seen = 0

    for line in stream:
        line = line.strip().rstrip(",")
        if not line or line in ("[", "]"):
            continue
        try:
            card = json.loads(line)
        except json.JSONDecodeError:
            continue
        if card.get("object") != "card":
            continue
        if card.get("layout") in SKIP_LAYOUTS:
            continue

        seen += 1
        oid = card.get("oracle_id")
        if not oid:
            continue

        name = card.get("name") or ""
        mana_cost = card.get("mana_cost")
        # Split/MDFC cards carry cost on the faces, not the top level.
        if not mana_cost and card.get("card_faces"):
            mana_cost = " // ".join(
                f.get("mana_cost") or "" for f in card["card_faces"]
            ).strip(" /")

        row = index.get(oid)
        if row is None:
            row = {
                "name": name,
                "front_name": name.split(" // ")[0],
                "mana_cost": mana_cost or "",
                "cmc": card.get("cmc") or 0,
                # Sorted so the string is stable and greppable: "" == colorless
                "color_identity": "".join(sorted(card.get("color_identity") or [])),
                "type_line": card.get("type_line") or "",
                "layout": card.get("layout") or "",
                "commander_legal": (card.get("legalities") or {}).get("commander", "unknown"),
                "usd_min": None,
                "usd_min_set": "",
                "oracle_id": oid,
            }
            index[oid] = row

        price = paper_usd(card)
        if price is not None and (row["usd_min"] is None or price < row["usd_min"]):
            row["usd_min"] = price
            row["usd_min_set"] = card.get("set") or ""

    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in sorted(index.values(), key=lambda r: r["name"]):
            row = dict(row)
            row["usd_min"] = "" if row["usd_min"] is None else f"{row['usd_min']:.2f}"
            writer.writerow(row)

    print(f"[done] {seen} printings -> {len(index)} unique cards -> {out_path}",
          file=sys.stderr)
    return len(index)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bulk", default="default_cards",
                    help="Scryfall bulk type: default_cards (per printing, best "
                         "prices) or oracle_cards (smaller, one price)")
    ap.add_argument("--input", help="Local .jsonl/.jsonl.gz instead of downloading")
    ap.add_argument("--out", default="cards.csv")
    ap.add_argument("--min-cards", type=int, default=25000,
                    help="Sanity floor; exit non-zero if fewer rows result")
    args = ap.parse_args()

    uri = args.input or resolve_bulk_uri(args.bulk)
    with open_stream(uri) as stream:
        count = build(stream, args.out)

    if count < args.min_cards:
        print(f"[FAIL] only {count} cards (< {args.min_cards}); refusing to publish",
              file=sys.stderr)
        sys.exit(1)

    with open("BUILD_INFO.txt", "w", encoding="utf-8") as fh:
        fh.write(f"built_at={datetime.now(timezone.utc).isoformat()}\n")
        fh.write(f"source={args.bulk}\ncards={count}\n")


if __name__ == "__main__":
    main()
