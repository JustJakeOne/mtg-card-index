#!/usr/bin/env python3
"""Fetch Magic Comprehensive Rules .txt from Wizards; keep the previous file on failure."""

from __future__ import annotations

import argparse
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from common import urlopen, upsert_build_info

RULES_PAGE = "https://magic.wizards.com/en/rules"


def latest_txt_url(html: str) -> str | None:
    found = re.findall(
        r"https://media\.wizards\.com/[^\"'\s<>]+MagicCompRules[^\"'\s<>]+\.txt",
        html,
        flags=re.I,
    )
    if not found:
        found = re.findall(
            r"https://media\.wizards\.com/[^\"']+MagicCompRules[^\"']+\.txt",
            html,
            flags=re.I,
        )
    # HTML may contain spaces in the filename; unescape.
    cleaned = [urllib.parse.unquote(u.replace("&amp;", "&")) for u in found]
    if not cleaned:
        return None
    return sorted(set(cleaned))[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="MagicCompRules.txt")
    args = ap.parse_args()
    dest = Path(args.out)

    try:
        with urlopen(RULES_PAGE, timeout=60) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        url = latest_txt_url(html)
        if not url:
            raise RuntimeError("no MagicCompRules.txt link on rules page")
        # Spaces in Wizards filenames.
        quoted = urllib.parse.quote(url, safe=":/")
        print(f"[rules] GET {quoted}", file=sys.stderr)
        with urlopen(quoted, timeout=120) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        if len(text) < 50_000:
            raise RuntimeError(f"rules file too small ({len(text)} bytes)")
        dest.write_text(text, encoding="utf-8")
        upsert_build_info(
            Path("BUILD_INFO.txt"),
            rules_built_at=datetime.now(timezone.utc).isoformat(),
        )
        print(f"[done] {len(text)} bytes -> {dest}", file=sys.stderr)
    except Exception as exc:
        print(f"[warn] leaving previous Comprehensive Rules in place: {exc}", file=sys.stderr)
        if not dest.exists():
            print("[warn] no previous MagicCompRules.txt", file=sys.stderr)


if __name__ == "__main__":
    main()
