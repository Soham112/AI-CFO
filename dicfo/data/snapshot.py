"""Load, save and merge snapshots.

A snapshot is plain JSON so that either the live fetcher OR Claude (via a skill,
using web search) can produce one. `overrides` merge on top of live data, which
is how a skill injects facts the APIs missed (e.g. today's RBI decision) and its
own judgement on news (`drivers`).
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import SNAPSHOTS


def deep_merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        elif isinstance(v, list) and isinstance(out.get(k), list) and k == "news":
            out[k] = out[k] + v
        else:
            out[k] = v
    return out


def load(path: str | Path) -> dict:
    with open(path) as f:
        return json.load(f)


def save(snap: dict, name: str | None = None) -> Path:
    SNAPSHOTS.mkdir(exist_ok=True)
    name = name or f"snapshot-{snap.get('as_of', 'unknown')[:10]}.json"
    p = SNAPSHOTS / name
    with open(p, "w") as f:
        json.dump(snap, f, indent=2, default=str)
    return p


def latest() -> Path | None:
    files = sorted(SNAPSHOTS.glob("snapshot-*.json"))
    return files[-1] if files else None
