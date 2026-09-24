"""Abstract provider interfaces — business logic depends only on these."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class GenerationRequest:
    prompt: str
    duration_seconds: Optional[float] = None   # for video/tts
    width: Optional[int] = None
    height: Optional[int] = None
    style: Optional[str] = None


@dataclass
class GenerationResult:
    success: bool
    provider: str
    asset_type: str
    local_path: Optional[str] = None
    duration_seconds: Optional[float] = None
    cost_usd: float = 0.0
    error: Optional[str] = None


class VideoProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def generate(self, request: GenerationRequest) -> GenerationResult: ...

    @abstractmethod
    def is_available(self) -> bool: ...


class ImageProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def generate(self, request: GenerationRequest) -> GenerationResult: ...

    @abstractmethod
    def is_available(self) -> bool: ...


class TTSProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def synthesize(self, text: str, voice: Optional[str] = None) -> GenerationResult: ...

    @abstractmethod
    def is_available(self) -> bool: ...
