"""ProductionBudget — cost estimation model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AssetCost:
    asset_type: str
    quantity: float          # seconds for video/tts, count for images
    unit_cost_usd: float
    provider: str

    @property
    def total_usd(self) -> float:
        return self.quantity * self.unit_cost_usd


@dataclass
class ProductionBudget:
    format: str
    topic: str
    budget_key: str          # matches key in budgets.yaml per_format

    asset_costs: list[AssetCost] = field(default_factory=list)
    free_asset_count: int = 0
    paid_asset_count: int = 0
    generation_attempts: int = 0

    budget_limit_usd: Optional[float] = None
    notes: Optional[str] = None

    def estimated_total_usd(self) -> float:
        return sum(a.total_usd for a in self.asset_costs)

    def within_budget(self) -> bool:
        if self.budget_limit_usd is None:
            return True
        return self.estimated_total_usd() <= self.budget_limit_usd

    def summary(self) -> dict:
        return {
            "format": self.format,
            "topic": self.topic,
            "estimated_cost_usd": round(self.estimated_total_usd(), 4),
            "budget_limit_usd": self.budget_limit_usd,
            "within_budget": self.within_budget(),
            "free_assets": self.free_asset_count,
            "paid_assets": self.paid_asset_count,
            "generation_attempts": self.generation_attempts,
        }
