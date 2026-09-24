"""Mock providers — no real API calls, no credentials required."""

from __future__ import annotations

from typing import Optional

from .base import GenerationRequest, GenerationResult, ImageProvider, TTSProvider, VideoProvider


class MockVideoProvider(VideoProvider):
    @property
    def name(self) -> str:
        return "mock_video"

    def generate(self, request: GenerationRequest) -> GenerationResult:
        return GenerationResult(
            success=True,
            provider=self.name,
            asset_type="video",
            local_path=f"/mock/video_{hash(request.prompt) % 10000}.mp4",
            duration_seconds=request.duration_seconds or 5.0,
            cost_usd=0.0,
        )

    def is_available(self) -> bool:
        return True


class MockImageProvider(ImageProvider):
    @property
    def name(self) -> str:
        return "mock_image"

    def generate(self, request: GenerationRequest) -> GenerationResult:
        return GenerationResult(
            success=True,
            provider=self.name,
            asset_type="image",
            local_path=f"/mock/image_{hash(request.prompt) % 10000}.png",
            cost_usd=0.0,
        )

    def is_available(self) -> bool:
        return True


class MockTTSProvider(TTSProvider):
    @property
    def name(self) -> str:
        return "mock_tts"

    def synthesize(self, text: str, voice: Optional[str] = None) -> GenerationResult:
        words = len(text.split())
        duration = words / 2.5  # ~150 wpm
        return GenerationResult(
            success=True,
            provider=self.name,
            asset_type="audio",
            local_path=f"/mock/tts_{hash(text) % 10000}.mp3",
            duration_seconds=duration,
            cost_usd=0.0,
        )

    def is_available(self) -> bool:
        return True
