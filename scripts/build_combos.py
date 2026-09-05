#!/usr/bin/env python3
"""
Mirror Commander Spellbook variants from their published dump (one GET).

Do not paginate /variants/. Their OpenAPI forbids exporting the catalog that way
and that is what 429s laptops. Dump:
  https://json.commanderspellbook.com/variants.json.gz

Filter combos against cards.csv Commander legality (Spellbook ignores the banlist).
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import urlopen, upsert_build_info

DUMP = "https://json.commanderspellbook.com/variants.json.gz"
CARDS_RAW = "https://raw.githubusercontent.com/JustJakeOne/mtg-card-index/data/cards.csv.gz"


def load_legal_names(cards_path: Path) -> set[str]:
    opener = gzip.open if str(cards_path).endswith(".gz") else open
    legal: set[str] = set()
    with opener(cards_path, "rt", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if (row.get("commander_legal") or "").lower() == "legal":
                name = (row.get("name") or "").strip()
                if name:
                    legal.add(name.casefold())
                    legal.add(name.split(" // ")[0].strip().casefold())
    return legal


def variant_names(variant: dict) -> list[str]:
    names = []
    for use in variant.get("uses") or []:
        if not isinstance(use, dict):
            continue
        card = use.get("card")
        if isinstance(card, dict) and card.get("name"):
            names.append(card["name"])
        elif use.get("name"):
            names.append(use["name"])
    return names


def variant_results(variant: dict) -> list[str]:
    out = []
    for prod in variant.get("produces") or []:
        if not isinstance(prod, dict):
            continue
        feat = prod.get("feature")
        if isinstance(feat, dict) and feat.get("name"):
            out.append(feat["name"])
        elif prod.get("name"):
            out.append(prod["name"])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", default="cards.csv.gz")
    ap.add_argument("--out", default="combos.jsonl")
    ap.add_argument("--dump", default=DUMP)
    args = ap.parse_args()

    cards_path = Path(args.cards)
    if not cards_path.exists():
        print(f"[cards] {cards_path} missing; downloading {CARDS_RAW}", file=sys.stderr)
        with urlopen(CARDS_RAW, timeout=120) as resp:
            cards_path.write_bytes(resp.read())

    legal = load_legal_names(cards_path)
    if len(legal) < 20000:
        print(f"[FAIL] only {len(legal)} legal names from {cards_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[dump] GET {args.dump}", file=sys.stderr)
    with urlopen(args.dump, timeout=180) as resp:
        raw = resp.read()
    if raw[:2] == b"\x1f\x8b":
        payload = json.loads(gzip.decompress(raw).decode("utf-8"))
    else:
        payload = json.loads(raw.decode("utf-8"))

    if isinstance(payload, dict):
        variants = payload.get("variants") or []
        stamp = payload.get("timestamp") or ""
        version = payload.get("version") or ""
    elif isinstance(payload, list):
        variants = payload
        stamp = ""
        version = ""
    else:
        raise SystemExit(f"Unexpected dump shape: {type(payload)}")

    written = 0
    skipped_illegal = 0
    out_path = Path(args.out)
    with out_path.open("w", encoding="utf-8") as fh:
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            names = variant_names(variant)
            if not names:
                continue
            if any(n.casefold() not in legal for n in names):
                skipped_illegal += 1
                continue
            rec = {
                "combo_id": variant.get("id"),
                "card_names": names,
                "color_identity": variant.get("identity") or "",
                "results": variant_results(variant),
                "prerequisites": variant.get("easyPrerequisites") or "",
                "bracket_class": variant.get("bracketTag") or "",
                "spoiler": bool(variant.get("spoiler")),
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1

    print(
        f"[done] {written} combos ({skipped_illegal} dropped as illegal) "
        f"from {len(variants)} variants dump={stamp} version={version} -> {out_path}",
        file=sys.stderr,
    )
    if written < 1000:
        print("[FAIL] combo count too small; refusing to publish", file=sys.stderr)
        sys.exit(1)
    upsert_build_info(
        Path("BUILD_INFO.txt"),
        combos_built_at=datetime.now(timezone.utc).isoformat(),
        combos=written,
        combos_source=f"variants.json.gz {stamp} {version}".strip(),
    )


if __name__ == "__main__":
    main()
