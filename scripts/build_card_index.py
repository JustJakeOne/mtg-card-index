#!/usr/bin/env python3
"""
Build cards.csv (one row per oracle card) and printings.csv (one row per printing)
from Scryfall default_cards. Streams the bulk file; does not load it all at once.

cards.csv includes oracle_text / keywords / produced_mana (DeckForge A2).
printings.csv columns match DeckForge design §3.2.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import SKIP_LAYOUTS, resolve_bulk_uri, request, upsert_build_info

CARD_FIELDS = [
    "name", "front_name", "mana_cost", "cmc", "color_identity",
    "type_line", "layout", "commander_legal", "usd_min", "usd_min_set",
    "oracle_id", "oracle_text", "keywords", "produced_mana",
]

PRINTING_FIELDS = [
    "scryfall_id", "oracle_id", "name", "set", "collector_number",
    "usd", "usd_foil", "digital",
]


def open_stream(uri: str):
    if uri.startswith("http"):
        return gzip.open(urllib_urlopen(uri), "rt", encoding="utf-8")
    if uri.endswith(".gz"):
        return gzip.open(uri, "rt", encoding="utf-8")
    return open(uri, "rt", encoding="utf-8")


def urllib_urlopen(uri: str):
    import urllib.request
    return urllib.request.urlopen(request(uri), timeout=300)


def paper_usd(card: dict):
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


def face_join(card: dict, field: str, sep: str) -> str:
    top = card.get(field) or ""
    if top:
        return top
    faces = card.get("card_faces") or []
    if not faces:
        return ""
    return sep.join(f.get(field) or "" for f in faces)


def build(stream, cards_out: str, printings_out: str) -> tuple[int, int]:
    index: dict[str, dict] = {}
    seen = 0
    printings_n = 0
    printings_path = Path(printings_out)
    printings_path.parent.mkdir(parents=True, exist_ok=True)

    with printings_path.open("w", newline="", encoding="utf-8") as pfh:
        pw = csv.DictWriter(pfh, fieldnames=PRINTING_FIELDS)
        pw.writeheader()

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
            oid = card.get("oracle_id") or ""
            name = card.get("name") or ""
            prices = card.get("prices") or {}
            pw.writerow({
                "scryfall_id": card.get("id") or "",
                "oracle_id": oid,
                "name": name,
                "set": card.get("set") or "",
                "collector_number": card.get("collector_number") or "",
                "usd": prices.get("usd") or "",
                "usd_foil": prices.get("usd_foil") or "",
                "digital": "1" if card.get("digital") else "0",
            })
            printings_n += 1

            if not oid:
                continue

            mana_cost = face_join(card, "mana_cost", " // ").strip(" /")
            oracle_text = face_join(card, "oracle_text", "\n//\n").replace("\r\n", "\n")
            type_line = card.get("type_line") or face_join(card, "type_line", " // ")

            row = index.get(oid)
            if row is None:
                index[oid] = {
                    "name": name,
                    "front_name": name.split(" // ")[0],
                    "mana_cost": mana_cost,
                    "cmc": card.get("cmc") or 0,
                    "color_identity": "".join(sorted(card.get("color_identity") or [])),
                    "type_line": type_line,
                    "layout": card.get("layout") or "",
                    "commander_legal": (card.get("legalities") or {}).get("commander", "unknown"),
                    "usd_min": None,
                    "usd_min_set": "",
                    "oracle_id": oid,
                    "oracle_text": oracle_text,
                    "keywords": ";".join(card.get("keywords") or []),
                    "produced_mana": ";".join(card.get("produced_mana") or []),
                }
                row = index[oid]
            elif not row.get("oracle_text") and oracle_text:
                row["oracle_text"] = oracle_text

            price = paper_usd(card)
            if price is not None and (row["usd_min"] is None or price < row["usd_min"]):
                row["usd_min"] = price
                row["usd_min_set"] = card.get("set") or ""

    cards_path = Path(cards_out)
    cards_path.parent.mkdir(parents=True, exist_ok=True)
    with cards_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CARD_FIELDS)
        writer.writeheader()
        for row in sorted(index.values(), key=lambda r: r["name"]):
            out = dict(row)
            out["usd_min"] = "" if out["usd_min"] is None else f"{out['usd_min']:.2f}"
            writer.writerow(out)

    print(
        f"[done] {seen} printings streamed -> {printings_n} printing rows, "
        f"{len(index)} unique cards -> {cards_out}",
        file=sys.stderr,
    )
    return len(index), printings_n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bulk", default="default_cards")
    ap.add_argument("--input", help="Local .jsonl/.jsonl.gz instead of downloading")
    ap.add_argument("--out", default="cards.csv")
    ap.add_argument("--printings-out", default="printings.csv")
    ap.add_argument("--min-cards", type=int, default=25000)
    ap.add_argument("--min-printings", type=int, default=80000)
    args = ap.parse_args()

    uri = args.input or resolve_bulk_uri(args.bulk)
    with open_stream(uri) as stream:
        n_cards, n_printings = build(stream, args.out, args.printings_out)

    if n_cards < args.min_cards:
        print(f"[FAIL] only {n_cards} cards (< {args.min_cards}); refusing to publish",
              file=sys.stderr)
        sys.exit(1)
    if n_printings < args.min_printings:
        print(f"[FAIL] only {n_printings} printings (< {args.min_printings}); refusing",
              file=sys.stderr)
        sys.exit(1)

    upsert_build_info(
        Path("BUILD_INFO.txt"),
        built_at=datetime.now(timezone.utc).isoformat(),
        source=args.bulk,
        cards=n_cards,
        printings=n_printings,
    )


if __name__ == "__main__":
    main()
