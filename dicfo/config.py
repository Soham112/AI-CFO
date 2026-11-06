import os

import yaml

from . import CONFIG, ROOT

PROFILES = ROOT / "profiles"


def load(name: str) -> dict:
    with open(CONFIG / f"{name}.yaml") as f:
        return yaml.safe_load(f) or {}


def profile_path(name: str | None = None):
    name = name or os.environ.get("DICFO_PROFILE")
    if name:
        return PROFILES / f"{name}.yaml"
    mine = sorted(p for p in PROFILES.glob("*.yaml") if not p.name.startswith("example-"))
    return mine[0] if mine else PROFILES / "example-india-resident.yaml"


def load_profile(name: str | None = None) -> dict:
    with open(profile_path(name)) as f:
        p = yaml.safe_load(f) or {}
    p.setdefault("base_currency", "INR" if p.get("residency") == "India" else "USD")
    p.setdefault("spend_currency", p["base_currency"])
    p.setdefault("tax_residency", p.get("residency"))
    return p


def load_env(path=None):
    """Tiny .env reader so secrets stay out of the code and out of git."""
    path = path or ROOT / ".env"
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
