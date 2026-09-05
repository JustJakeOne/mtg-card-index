#!/usr/bin/env python3
"""
Force-push branch `data` as a single commit containing the full artifact set.

Overlays --own files from the current working tree. Restores every other known
artifact from origin/data so a daily job cannot wipe weekly combos (A4).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from common import merge_build_info

KNOWN = [
    "BUILD_INFO.txt",
    "cards.csv.gz",
    "printings.csv.gz",
    "oracle_tags.csv.gz",
    "game_changers.json",
    "combos.jsonl",
    "MagicCompRules.txt",
]


def git(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], check=check)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--own", nargs="+", required=True, help="Files this job produced")
    ap.add_argument("--message", default="")
    args = ap.parse_args()

    root = Path.cwd()
    owned = [Path(p) for p in args.own]
    missing = [p for p in owned if not p.exists()]
    if missing:
        sys.exit(f"owned file(s) missing: {missing}")

    staging = Path(tempfile.mkdtemp(prefix="index-owned-"))
    for path in owned:
        shutil.copy2(path, staging / path.name)

    git(["config", "user.name", "card-index-bot"])
    git(["config", "user.email", "card-index-bot@users.noreply.github.com"])
    git(["fetch", "origin", "data"], check=False)

    has_data = git(["rev-parse", "--verify", "origin/data"], check=False).returncode == 0

    old_info = ""
    if has_data:
        show = subprocess.run(
            ["git", "show", "origin/data:BUILD_INFO.txt"],
            check=False, capture_output=True, text=True,
        )
        if show.returncode == 0:
            old_info = show.stdout

    git(["checkout", "--orphan", "data-tmp"])
    git(["rm", "-rf", "--cached", "."], check=False)

    if has_data:
        for name in KNOWN:
            git(["checkout", "origin/data", "--", name], check=False)

    for path in owned:
        shutil.copy2(staging / path.name, root / path.name)

    new_info_path = root / "BUILD_INFO.txt"
    new_text = new_info_path.read_text(encoding="utf-8") if new_info_path.exists() else ""
    if old_info or new_text:
        new_info_path.write_text(merge_build_info(old_info, new_text), encoding="utf-8")

    to_add = [name for name in KNOWN if (root / name).exists()]
    git(["add", "-f", *to_add])
    msg = args.message or f"card index {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    git(["commit", "-m", msg])
    git(["push", "-f", "origin", "HEAD:data"])
    print(f"[publish] data <- {to_add}", file=sys.stderr)


if __name__ == "__main__":
    main()
