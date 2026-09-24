"""CostController — estimates production costs from a RetentionPlan."""

from __future__ import annotations

from delta.config import budgets_config, providers_config
from delta.models.budget import AssetCost, ProductionBudget
from delta.models.retention import AssetType, RetentionPlan


class CostController:
    def __init__(self) -> None:
        self._budgets = budgets_config()["budgets"]
        self._providers = providers_config()["providers"]

    def estimate(self, retention_plan: RetentionPlan, budget_key: str) -> ProductionBudget:
        budget_cfg = self._budgets["per_format"].get(budget_key)
        if budget_cfg is None:
            raise ValueError(f"Unknown budget key: {budget_key}")

        video_provider_name = self._providers["video"]["default"]
        video_provider_cfg = self._providers["video"]["available"][video_provider_name]
        video_cost_per_sec = video_provider_cfg.get("cost_per_second_usd") or 0.0

        image_provider_name = self._providers["image"]["default"]
        image_provider_cfg = self._providers["image"]["available"][image_provider_name]
        image_cost_per_unit = image_provider_cfg.get("cost_per_image_usd") or 0.0

        asset_costs: list[AssetCost] = []
        free_count = 0
        paid_count = 0

        ai_video_seconds = sum(
            s.duration for s in retention_plan.segments
            if s.asset_type == AssetType.AI_GENERATED_VIDEO
        )
        if ai_video_seconds > 0:
            asset_costs.append(AssetCost(
                asset_type="AI_GENERATED_VIDEO",
                quantity=ai_video_seconds,
                unit_cost_usd=video_cost_per_sec,
                provider=video_provider_name,
            ))
            if video_cost_per_sec > 0:
                paid_count += 1
            else:
                free_count += 1

        generated_image_count = sum(
            1 for s in retention_plan.segments
            if s.asset_type == AssetType.GENERATED_IMAGE
        )
        if generated_image_count > 0:
            asset_costs.append(AssetCost(
                asset_type="GENERATED_IMAGE",
                quantity=generated_image_count,
                unit_cost_usd=image_cost_per_unit,
                provider=image_provider_name,
            ))
            if image_cost_per_unit > 0:
                paid_count += 1
            else:
                free_count += 1

        free_types = {
            AssetType.SCREENSHOT, AssetType.SCREEN_RECORDING, AssetType.STATIC_IMAGE,
            AssetType.TEXT_OVERLAY, AssetType.GRAPHIC, AssetType.CHART,
            AssetType.B_ROLL, AssetType.ZOOM_PAN, AssetType.TRANSITION,
        }
        free_count += sum(1 for s in retention_plan.segments if s.asset_type in free_types)

        return ProductionBudget(
            format=retention_plan.format,
            topic=retention_plan.content_plan_topic,
            budget_key=budget_key,
            asset_costs=asset_costs,
            free_asset_count=free_count,
            paid_asset_count=paid_count,
            generation_attempts=1,
            budget_limit_usd=budget_cfg["max_usd"],
        )
