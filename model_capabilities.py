from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class ModelCapabilities:
    """Capabilities and UI hints for a specific Gemini model."""

    supports_thinking: bool = False
    thinking_min_budget: int = 0
    thinking_max_budget: int = 0
    thinking_divisions: int = 0
    thinking_tooltip: str = "このモデルは thinking 機能をサポートしていません。"
    force_thinking: bool = False

    @property
    def has_slider(self) -> bool:
        """Returns True when the thinking slider should stay enabled."""
        return (
            self.supports_thinking
            and self.thinking_max_budget > 0
            and self.thinking_max_budget >= self.thinking_min_budget
        )


_CAPABILITY_MATRIX: tuple[tuple[str, ModelCapabilities], ...] = (
    (
        "gemini-2.5-pro",
        ModelCapabilities(
            supports_thinking=True,
            thinking_min_budget=128,
            thinking_max_budget=32768,
            thinking_divisions=32,
            thinking_tooltip="思考バジェット (128-32768, Proでは思考無効化不可, -1=自動)",
            force_thinking=True,
        ),
    ),
    (
        "gemini-2.5-flash-lite",
        ModelCapabilities(
            supports_thinking=True,
            thinking_min_budget=0,
            thinking_max_budget=24576,
            thinking_divisions=24,
            thinking_tooltip="思考バジェット (0=無効, 512-24576, -1=自動)",
        ),
    ),
    (
        "gemini-2.5-flash",
        ModelCapabilities(
            supports_thinking=True,
            thinking_min_budget=0,
            thinking_max_budget=24576,
            thinking_divisions=24,
            thinking_tooltip="思考バジェット (0=無効, 1-24576, -1=自動)",
        ),
    ),
    (
        "gemini-2.0-flash-lite",
        ModelCapabilities(
            supports_thinking=True,
            thinking_min_budget=0,
            thinking_max_budget=24576,
            thinking_divisions=24,
            thinking_tooltip="思考バジェット (0=無効, 512-24576, -1=自動)",
        ),
    ),
    (
        "gemini-2.0-flash",
        ModelCapabilities(
            supports_thinking=True,
            thinking_min_budget=0,
            thinking_max_budget=24576,
            thinking_divisions=24,
            thinking_tooltip="思考バジェット (0=無効, 1-24576, -1=自動)",
        ),
    ),
)


@lru_cache(maxsize=None)
def get_model_capabilities(model_name: str | None) -> ModelCapabilities:
    """
    Returns the capability definition for a given model.

    The lookup is case-insensitive and matches when the configured key is included
    in the actual model name (e.g. preview/updated suffixes).
    """
    if not model_name:
        return ModelCapabilities()

    model_lower = model_name.lower()
    for key, profile in _CAPABILITY_MATRIX:
        if key in model_lower:
            return profile
    return ModelCapabilities()


def supports_thinking(model_name: str | None) -> bool:
    """Convenience helper to check thinking support."""
    return get_model_capabilities(model_name).supports_thinking


def clamp_thinking_budget(model_name: str | None, requested_budget: int | float | None) -> int:
    """
    Ensures the requested thinking budget stays within the supported range.

    Returns 0 for unsupported models. When the requested value is None, the minimum
    supported budget is returned so that the UI can fall back gracefully.
    """
    profile = get_model_capabilities(model_name)
    if not profile.supports_thinking:
        return 0

    if requested_budget is None:
        return profile.thinking_min_budget

    try:
        value = int(requested_budget)
    except (TypeError, ValueError):
        value = profile.thinking_min_budget

    if value < profile.thinking_min_budget:
        return profile.thinking_min_budget
    if value > profile.thinking_max_budget:
        return profile.thinking_max_budget
    return value
