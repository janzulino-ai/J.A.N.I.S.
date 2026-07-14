"""Tech Scout — discovery tecnologie OSS/API."""
from backend.core.tech_scout.discover import discover_all, discover_github, discover_pypi, load_watchlist
from backend.core.tech_scout.classifier import classify_candidate
from backend.core.tech_scout.sandbox import run_sandbox_test
from backend.core.tech_scout.verifier import verify_candidate
from backend.core.tech_scout.promote import promote_candidate

__all__ = [
    "discover_all",
    "discover_github",
    "discover_pypi",
    "load_watchlist",
    "classify_candidate",
    "run_sandbox_test",
    "verify_candidate",
    "promote_candidate",
]
