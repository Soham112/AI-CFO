"""Protect personal financial data on the laptop.

* Encryption at rest: profiles and ledgers can be stored encrypted (Fernet/AES).
  The key lives in the OS keychain (Windows Credential Manager / macOS Keychain /
  Linux Secret Service) via `keyring`, or in the DICFO_KEY env var as a fallback.
* Sensitive-ID blocker: refuses to store PAN, Aadhaar, card/account numbers,
  SSNs, passwords, PINs, OTPs. DICFO never needs them.
* File permissions: personal files are made readable by the owner only.
"""
from __future__ import annotations

import os
import re
import stat

from . import ROOT

SERVICE, KEY_NAME = "dicfo", "data-key"
PRIVATE_DIRS = ["profiles", "reports", "snapshots"]
PRIVATE_FILES = [".env"]


class SensitiveDataError(ValueError):
    pass


# ---------- sensitive data scanner ----------
BANNED_KEYS = re.compile(r"(pass(word)?|pin|otp|cvv|secret|token|api_?key|account_?(no|num|number)|"
                         r"ifsc|upi|pan(_?no|_?number)?$|aadha+r|ssn|social_security|demat|dp_?id|"
                         r"client_?id|card_?(no|num|number)|login|username)", re.I)
PATTERNS = {
    "PAN": re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    "Aadhaar": re.compile(r"\b[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}\b"),
    "US SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "IFSC": re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"),
}
CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _luhn(num: str) -> bool:
    d = [int(c) for c in num if c.isdigit()]
    s = sum(d[-1::-2]) + sum(sum(divmod(2 * x, 10)) for x in d[-2::-2])
    return len(d) >= 13 and s % 10 == 0


def scan(obj, path="") -> list[str]:
    """Return a list of problems; empty means clean."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if BANNED_KEYS.search(str(k)) and k not in ("scheme_code",):
                found.append(f"{path}{k}: field name looks like a credential or ID number")
            found += scan(v, f"{path}{k}.")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found += scan(v, f"{path}{i}.")
    elif isinstance(obj, str):
        for name, rx in PATTERNS.items():
            if rx.search(obj):
                found.append(f"{path.rstrip('.')}: looks like a {name}")
        for m in CARD.finditer(obj):
            if _luhn(m.group()):
                found.append(f"{path.rstrip('.')}: looks like a card/account number")
    return found


def assert_clean(obj, where: str):
    problems = scan(obj)
    if problems:
        raise SensitiveDataError(
            f"Refusing to store {where}: it seems to contain sensitive identifiers.\n  - "
            + "\n  - ".join(problems)
            + "\nDICFO never needs PAN, Aadhaar, account/card numbers, passwords or OTPs. Remove them.")


# ---------- encryption ----------
def _keyring():
    try:
        import keyring
        from keyring.backends import fail
        kr = keyring.get_keyring()
        return None if isinstance(kr, fail.Keyring) else keyring
    except Exception:
        return None


def get_key() -> bytes | None:
    if os.environ.get("DICFO_KEY"):
        return os.environ["DICFO_KEY"].encode()
    kr = _keyring()
    if kr:
        k = kr.get_password(SERVICE, KEY_NAME)
        return k.encode() if k else None
    return None


def new_key() -> tuple[bytes, str]:
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    kr = _keyring()
    if kr:
        kr.set_password(SERVICE, KEY_NAME, key.decode())
        return key, "saved in the OS keychain"
    return key, "NO KEYCHAIN FOUND: put this in your .env as DICFO_KEY and keep a copy somewhere safe"


def encrypt(data: bytes, key: bytes | None = None) -> bytes:
    from cryptography.fernet import Fernet
    key = key or get_key()
    if not key:
        raise RuntimeError("No encryption key. Run `python -m dicfo secure init`.")
    return Fernet(key).encrypt(data)


def decrypt(data: bytes, key: bytes | None = None) -> bytes:
    from cryptography.fernet import Fernet, InvalidToken
    key = key or get_key()
    if not key:
        raise RuntimeError("Encrypted data found but no key: check the OS keychain or DICFO_KEY.")
    try:
        return Fernet(key).decrypt(data)
    except InvalidToken:
        raise RuntimeError("Wrong encryption key (or the file was tampered with).") from None


def read_private(path) -> bytes | None:
    """Read <path> or its encrypted twin <path>.enc."""
    enc = path.with_name(path.name + ".enc")
    if enc.exists():
        return decrypt(enc.read_bytes())
    if path.exists():
        return path.read_bytes()
    return None


def write_private(path, data: bytes):
    """Write encrypted if encryption is set up, else plain; always owner-only."""
    enc = path.with_name(path.name + ".enc")
    path.parent.mkdir(parents=True, exist_ok=True)
    if enc.exists() or get_key():
        _atomic(enc, encrypt(data))
        if path.exists():
            shred(path)
    else:
        _atomic(path, data)


def _atomic(path, data: bytes):
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.replace(tmp, path)
    _owner_only(path)


def shred(path):
    """Overwrite then delete (best effort; SSDs may keep old blocks: use full-disk encryption)."""
    try:
        n = path.stat().st_size
        with open(path, "r+b") as f:
            f.write(os.urandom(n))
            f.flush()
            os.fsync(f.fileno())
    finally:
        path.unlink(missing_ok=True)


# ---------- permissions ----------
def _owner_only(p):
    if os.name == "nt":
        return
    try:
        os.chmod(p, 0o700 if p.is_dir() else 0o600)
    except OSError:
        pass


def harden() -> list[str]:
    """Make personal files owner-only. Returns what was fixed."""
    fixed = []
    if os.name == "nt":
        return fixed
    for d in PRIVATE_DIRS:
        p = ROOT / d
        if p.exists():
            for q in [p, *p.rglob("*")]:
                mode = stat.S_IMODE(q.stat().st_mode)
                want = 0o700 if q.is_dir() else 0o600
                if mode & 0o077:
                    os.chmod(q, want)
                    fixed.append(str(q.relative_to(ROOT)))
    for f in PRIVATE_FILES:
        p = ROOT / f
        if p.exists() and stat.S_IMODE(p.stat().st_mode) & 0o077:
            os.chmod(p, 0o600)
            fixed.append(f)
    return fixed


def init():
    """Turn on encryption: create the key, encrypt every profile and ledger, install the git guard."""
    from .config import PROFILES
    key = get_key()
    if key:
        print("Encryption key already set up.")
    else:
        key, where = new_key()
        print(f"Created encryption key ({where}).")
        if "NO KEYCHAIN" in where:
            print(f"\n  DICFO_KEY={key.decode()}\n")
    os.environ["DICFO_KEY"] = key.decode()
    n = 0
    for p in list(PROFILES.glob("*.yaml")) + list(PROFILES.glob("*.csv")):
        if p.name.startswith("example-"):
            continue
        if p.suffix == ".yaml":
            import yaml
            assert_clean(yaml.safe_load(p.read_text()) or {}, p.name)
        write_private(p, p.read_bytes())
        n += 1
    print(f"Encrypted {n} file(s) in profiles/. Plain copies were overwritten and removed.")
    install_git_guard()
    print("Owner-only permissions applied to:", ", ".join(harden()) or "already fine")


def install_git_guard():
    import subprocess
    try:
        subprocess.run(["git", "config", "core.hooksPath", "scripts/hooks"], cwd=ROOT, check=True,
                       capture_output=True)
        print("Git guard on: commits containing personal files or ID numbers will be blocked.")
    except Exception:
        print("Git guard not installed (git not found). Run: git config core.hooksPath scripts/hooks")
