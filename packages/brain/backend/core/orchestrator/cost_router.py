"""Router costi: locale prima, API cloud solo con budget."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from backend.config import settings

logger = logging.getLogger("JANIS.CostRouter")

TIER_LOCAL = "local"
TIER_CHEAP = "openrouter"
TIER_PREMIUM = "premium"


@dataclass
class CostRouter:
    daily_budget_usd: float = 2.0
    spent_today_usd: float = 0.0
    _state_path: Path = field(default_factory=lambda: Path("data/cost_router.json"))

    def __post_init__(self) -> None:
        if hasattr(settings, "API_DAILY_BUDGET_USD"):
            self.daily_budget_usd = float(getattr(settings, "API_DAILY_BUDGET_USD", 2.0))
        root = Path(settings.JANIS_PROJECT_DIR)
        self._state_path = root / "data" / "cost_router.json"
        self._load()

    def _load(self) -> None:
        if not self._state_path.exists():
            return
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            if data.get("date") == date.today().isoformat():
                self.spent_today_usd = float(data.get("spent_usd", 0))
        except (json.JSONDecodeError, OSError, ValueError):
            pass

    def _save(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps({"date": date.today().isoformat(), "spent_usd": self.spent_today_usd}),
            encoding="utf-8",
        )

    def pick_tier(self, *, require_quality: bool = False, cloud_only: bool = False) -> str:
        if cloud_only:
            return TIER_PREMIUM if self._budget_ok(0.5) else TIER_CHEAP
        if not require_quality:
            return TIER_LOCAL
        if self._budget_ok(0.2):
            return TIER_CHEAP
        return TIER_LOCAL

    def _budget_ok(self, estimate_usd: float) -> bool:
        return (self.spent_today_usd + estimate_usd) <= self.daily_budget_usd

    def record_spend(self, usd: float) -> None:
        self.spent_today_usd += max(0.0, usd)
        self._save()
        logger.info("API spend oggi: $%.4f / $%.2f", self.spent_today_usd, self.daily_budget_usd)

    def status(self) -> dict:
        return {
            "daily_budget_usd": self.daily_budget_usd,
            "spent_today_usd": round(self.spent_today_usd, 4),
            "remaining_usd": round(max(0, self.daily_budget_usd - self.spent_today_usd), 4),
            "default_tier": TIER_LOCAL,
        }


cost_router = CostRouter()
