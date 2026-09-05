#!/usr/bin/env python3
"""Shared HTTP and BUILD_INFO helpers for the public index jobs."""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

UA = "mtg-card-index/2.0 (https://github.com/JustJakeOne/mtg-card-index; contact: thegloriousexcess@gmail.com)"
BULK_INDEX = "https://api.scryfall.com/bulk-data/{}"

SKIP_LAYOUTS = {
    "token", "double_faced_token", "emblem", "art_series",
    "scheme", "planar", "vanguard", "augment", "host",
}

INFO_ORDER = [
    "built_at", "source", "cards", "printings", "oracle_tags", "game_changers",
    "combos_built_at", "combos", "combos_source", "rules_built_at",
]


def request(url: str, timeout: int = 120) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})


def urlopen(url: str, timeout: int = 120):
    return urllib.request.urlopen(request(url), timeout=timeout)


def resolve_bulk_uri(bulk_type: str) -> str:
    with urlopen(BULK_INDEX.format(bulk_type), timeout=60) as resp:
        meta = json.load(resp)
    uri = meta.get("jsonl_download_uri") or meta.get("download_uri")
    if not uri:
        raise SystemExit(f"No download URI in bulk-data object for {bulk_type!r}")
    print(
        f"[bulk] {bulk_type} updated_at={meta.get('updated_at')} "
        f"size={meta.get('size')} -> {uri}",
        file=sys.stderr,
    )
    return uri


def parse_build_info(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, val = line.split("=", 1)
            out[key.strip()] = val.strip()
    return out


def format_build_info(data: dict[str, str]) -> str:
    lines = []
    seen: set[str] = set()
    for key in INFO_ORDER:
        if key in data:
            lines.append(f"{key}={data[key]}")
            seen.add(key)
    for key in sorted(data):
        if key not in seen:
            lines.append(f"{key}={data[key]}")
    return "\n".join(lines) + "\n"


def upsert_build_info(path: Path, **fields: object) -> None:
    data: dict[str, str] = {}
    if path.exists():
        data = parse_build_info(path.read_text(encoding="utf-8"))
    for key, val in fields.items():
        if val is not None:
            data[key] = str(val)
    path.write_text(format_build_info(data), encoding="utf-8")


def merge_build_info(old_text: str, new_text: str) -> str:
    merged = parse_build_info(old_text)
    merged.update(parse_build_info(new_text))
    return format_build_info(merged)
