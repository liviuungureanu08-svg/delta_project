"""Configuration loader for Kronos."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


def _load(filename: str) -> dict[str, Any]:
    path = _CONFIG_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=None)
def channel_config() -> dict[str, Any]:
    return _load("channel.yaml")


@lru_cache(maxsize=None)
def budgets_config() -> dict[str, Any]:
    return _load("budgets.yaml")


@lru_cache(maxsize=None)
def providers_config() -> dict[str, Any]:
    return _load("providers.yaml")


@lru_cache(maxsize=None)
def scoring_config() -> dict[str, Any]:
    return _load("scoring.yaml")


@lru_cache(maxsize=None)
def retention_config() -> dict[str, Any]:
    return _load("retention.yaml")


def reload_all() -> None:
    """Clear all cached config (useful for tests)."""
    channel_config.cache_clear()
    budgets_config.cache_clear()
    providers_config.cache_clear()
    scoring_config.cache_clear()
    retention_config.cache_clear()
