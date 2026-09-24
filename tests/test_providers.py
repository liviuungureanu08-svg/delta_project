"""Tests for provider abstraction."""

import pytest
from delta.providers import MockImageProvider, MockTTSProvider, MockVideoProvider
from delta.providers.base import GenerationRequest


def test_mock_video_provider_available():
    p = MockVideoProvider()
    assert p.is_available()
    assert p.name == "mock_video"


def test_mock_video_generates_result():
    p = MockVideoProvider()
    req = GenerationRequest(prompt="flying drone over city", duration_seconds=5.0)
    result = p.generate(req)
    assert result.success
    assert result.cost_usd == 0.0
    assert result.duration_seconds == 5.0
    assert result.local_path is not None


def test_mock_image_provider_available():
    p = MockImageProvider()
    assert p.is_available()
    assert p.name == "mock_image"


def test_mock_image_generates_result():
    p = MockImageProvider()
    req = GenerationRequest(prompt="futuristic robot")
    result = p.generate(req)
    assert result.success
    assert result.cost_usd == 0.0
    assert result.local_path is not None


def test_mock_tts_synthesizes():
    p = MockTTSProvider()
    result = p.synthesize("Hello world this is a test sentence with multiple words.")
    assert result.success
    assert result.cost_usd == 0.0
    assert result.duration_seconds > 0
