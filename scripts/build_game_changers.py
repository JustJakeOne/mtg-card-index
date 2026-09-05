#!/usr/bin/env python3
"""Scryfall is:gamechanger → game_changers.json (list of oracle names)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from common import urlopen, upsert_build_info

SEARCH = "https://api.scryfall.com/cards/search?q=is%3Agamechanger&unique=cards"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="game_changers.json")
    args = ap.parse_args()

    names: list[str] = []
    url = SEARCH
    while url:
        with urlopen(url, timeout=60) as resp:
            page = json.load(resp)
        for card in page.get("data") or []:
            name = card.get("name")
            if name:
                names.append(name)
        url = page.get("next_page")
        if url:
            time.sleep(0.1)

    names = sorted(set(names))
    Path(args.out).write_text(json.dumps(names, indent=2) + "\n", encoding="utf-8")
    print(f"[done] {len(names)} game changers -> {args.out}", file=sys.stderr)
    if len(names) < 20:
        print("[FAIL] game changer list too small; refusing to publish", file=sys.stderr)
        sys.exit(1)
    upsert_build_info(Path("BUILD_INFO.txt"), game_changers=len(names))


if __name__ == "__main__":
    main()
