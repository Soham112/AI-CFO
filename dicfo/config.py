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
    mine = sorted({p.name.removesuffix(".enc") for p in PROFILES.glob("*.yaml*")
                   if not p.name.startswith("example-") and p.suffix in (".yaml", ".enc")})
    return PROFILES / mine[0] if mine else PROFILES / "example-india-resident.yaml"


def load_profile(name: str | None = None) -> dict:
    from .guardrails import validate_profile
    from .security import assert_clean, read_private
    path = profile_path(name)
    raw = read_private(path)
    if raw is None:
        raise SystemExit(f"No profile at {path}. Run: python -m dicfo onboard --name <name>")
    p = yaml.safe_load(raw) or {}
    assert_clean(p, path.name)
    validate_profile(p)
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
