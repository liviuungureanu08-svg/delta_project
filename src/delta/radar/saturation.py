"""Saturation classifier — determines SaturationState from evidence."""

from __future__ import annotations

from delta.models.radar import Evidence, SaturationState


class SaturationClassifier:
    """Classifies topic saturation based on evidence signals.

    States (ordered):
      EARLY → EMERGING → ACCELERATING → MAINSTREAM → SATURATED

    Classification is deterministic and config-driven.
    """

    def __init__(self, radar_cfg: dict) -> None:
        sat_cfg = radar_cfg.get("saturation", {})
        upload_vel = sat_cfg.get("upload_velocity_per_day", {})
        self._early_threshold = upload_vel.get("early", 2)
        self._emerging_threshold = upload_vel.get("emerging", 10)
        self._accelerating_threshold = upload_vel.get("accelerating", 30)
        self._mainstream_threshold = upload_vel.get("mainstream", 80)
        self._large_ch_threshold = sat_cfg.get(
            "large_channel_coverage_threshold", 5
        )

    def classify(self, evidence_list: list[Evidence], niche: str) -> SaturationState:
        """Classify saturation for the given evidence set."""
        yt_evidence = [ev for ev in evidence_list if ev.source_type == "youtube"]

        if not yt_evidence:
            return SaturationState.EARLY

        # Count unique channels uploading on this topic
        channel_ids: set[str] = set()
        large_channel_count = 0
        max_baseline = 0

        for ev in yt_evidence:
            p = ev.observed_value
            if not isinstance(p, dict):
                continue
            ch_id = p.get("channel_id", ev.source_id)
            channel_ids.add(ch_id)
            baseline = p.get("channel_baseline_views", 0)
            if baseline > max_baseline:
                max_baseline = baseline
            if baseline >= 30_000:
                large_channel_count += 1

        channel_count = len(channel_ids)

        # Estimate effective daily upload velocity from channel_count / age
        # Use evidence age as proxy for how long topic has been uploading
        # This is approximate — real implementation would use actual upload timestamps
        upload_velocity = self._estimate_upload_velocity(yt_evidence, channel_count)

        return self._state_from_velocity(upload_velocity, large_channel_count)

    def _estimate_upload_velocity(
        self, yt_evidence: list[Evidence], channel_count: int
    ) -> float:
        """Estimate approximate daily video upload velocity for the topic."""
        if not yt_evidence:
            return 0.0

        # Average upload frequency per channel × channel count
        freq_sum = 0.0
        freq_count = 0
        for ev in yt_evidence:
            p = ev.observed_value
            if isinstance(p, dict):
                freq = p.get("channel_upload_frequency_days")
                if freq and freq > 0:
                    freq_sum += 1.0 / freq
                    freq_count += 1

        if freq_count == 0:
            return float(channel_count)  # 1 video per day per channel fallback

        avg_daily_rate = freq_sum / freq_count
        return avg_daily_rate * channel_count

    def _state_from_velocity(
        self, velocity: float, large_channel_count: int
    ) -> SaturationState:
        if velocity <= self._early_threshold:
            state = SaturationState.EARLY
        elif velocity <= self._emerging_threshold:
            state = SaturationState.EMERGING
        elif velocity <= self._accelerating_threshold:
            state = SaturationState.ACCELERATING
        elif velocity <= self._mainstream_threshold:
            state = SaturationState.MAINSTREAM
        else:
            state = SaturationState.SATURATED

        # If many large channels are covering it, escalate saturation one step
        if large_channel_count >= self._large_ch_threshold:
            state = self._escalate(state)

        return state

    @staticmethod
    def _escalate(state: SaturationState) -> SaturationState:
        _next = {
            SaturationState.EARLY: SaturationState.EMERGING,
            SaturationState.EMERGING: SaturationState.ACCELERATING,
            SaturationState.ACCELERATING: SaturationState.MAINSTREAM,
            SaturationState.MAINSTREAM: SaturationState.SATURATED,
            SaturationState.SATURATED: SaturationState.SATURATED,
        }
        return _next[state]
