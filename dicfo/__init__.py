"""DICFO: a personal investment analysis engine (analysis, not financial advice)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
SNAPSHOTS = ROOT / "snapshots"
REPORTS = ROOT / "reports"
DISCLAIMER = (
    "This is automated analysis for education and planning, not personalised financial, "
    "tax or legal advice. Markets can fall further than any model expects. Verify rates "
    "and tax rules with a qualified advisor (CPA / CA) before acting."
)
