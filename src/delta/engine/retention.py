"""RetentionBuilder — generates a RetentionPlan from a ContentPlan."""

from __future__ import annotations

from delta.config import retention_config
from delta.models.content_plan import ContentPlan
from delta.models.retention import AssetType, RetentionPlan, TimelineSegment


_PREMIUM_TYPES = {AssetType.AI_GENERATED_VIDEO}

_ASSET_SEQUENCE_SHORT = [
    AssetType.TEXT_OVERLAY,
    AssetType.SCREENSHOT,
    AssetType.ZOOM_PAN,
    AssetType.GRAPHIC,
    AssetType.AI_GENERATED_VIDEO,
    AssetType.TEXT_OVERLAY,
    AssetType.CHART,
]

_ASSET_SEQUENCE_LONG = [
    AssetType.SCREEN_RECORDING,
    AssetType.SCREENSHOT,
    AssetType.CHART,
    AssetType.GRAPHIC,
    AssetType.GENERATED_IMAGE,
    AssetType.B_ROLL,
    AssetType.TEXT_OVERLAY,
    AssetType.ZOOM_PAN,
    AssetType.AI_GENERATED_VIDEO,
    AssetType.SCREENSHOT,
]


class RetentionBuilder:
    def __init__(self) -> None:
        self._cfg = retention_config()["retention"]

    def build(self, plan: ContentPlan) -> RetentionPlan:
        duration = plan.target_duration_seconds or plan.total_duration() or 60
        sequence = _ASSET_SEQUENCE_SHORT if plan.format == "SHORT" else _ASSET_SEQUENCE_LONG

        segments = self._generate_segments(plan, duration, sequence)

        rp = RetentionPlan(
            content_plan_topic=plan.topic,
            format=plan.format,
            total_duration_seconds=float(duration),
            segments=segments,
        )
        return rp

    def _generate_segments(
        self,
        plan: ContentPlan,
        duration: int,
        sequence: list[AssetType],
    ) -> list[TimelineSegment]:
        pacing = self._cfg["pacing"]
        hook_window = pacing["hook_window_seconds"]
        hook_interval = pacing["hook_change_interval_seconds"]
        body_interval = pacing["body_change_interval_seconds"]

        segments: list[TimelineSegment] = []
        cursor = 0.0
        seq_idx = 0

        def next_asset() -> AssetType:
            nonlocal seq_idx
            asset = sequence[seq_idx % len(sequence)]
            seq_idx += 1
            return asset

        while cursor < min(hook_window, duration):
            asset = next_asset()
            end = min(cursor + hook_interval, min(hook_window, duration))
            segments.append(TimelineSegment(
                start_second=cursor,
                end_second=end,
                asset_type=asset,
                description=f"Hook visual: {asset.value}",
                is_premium=asset in _PREMIUM_TYPES,
            ))
            cursor = end

        while cursor < duration:
            asset = next_asset()
            end = min(cursor + body_interval, duration)
            segments.append(TimelineSegment(
                start_second=cursor,
                end_second=end,
                asset_type=asset,
                description=f"Body visual: {asset.value}",
                is_premium=asset in _PREMIUM_TYPES,
            ))
            cursor = end

        return segments
