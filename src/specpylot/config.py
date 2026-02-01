from __future__ import annotations

"""Dataclasses for pipeline configuration."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CrosshairCheckConfig:
    """Configuration for CrossHair check runs.

    Attributes:
        per_condition_timeout: Timeout per condition in seconds (string for CLI passthrough).
        per_path_timeout: Timeout per path in seconds (string for CLI passthrough).
        max_uninteresting_iters: Max uninteresting iterations (string for CLI passthrough).
    """

    per_condition_timeout: str = "60"
    per_path_timeout: str = "5"
    max_uninteresting_iters: str = "100"


@dataclass(frozen=True)
class CrosshairCoverConfig:
    """Configuration for CrossHair cover runs.

    Attributes:
        per_condition_timeout: Timeout per condition in seconds (string for CLI passthrough).
        per_path_timeout: Timeout per path in seconds (string for CLI passthrough).
        max_uninteresting_iters: Max uninteresting iterations (string for CLI passthrough).
    """

    per_condition_timeout: str = "60"
    per_path_timeout: str = "5"
    max_uninteresting_iters: str = "100"


@dataclass(frozen=True)
class PipelineConfig:
    """Top-level pipeline configuration.

    Attributes:
        provider: LLM provider name (openai, anthropic, ollama).
        model: Model identifier for the provider.
        out_dir: Output directory for final artifacts.
        log_dir: Optional log directory for detailed artifacts.
        enable_coverage: Whether to run CrossHair cover.
        check: CrossHair check configuration.
        cover: CrossHair cover configuration.
        refine_budget_seconds: Max seconds for a refutation to qualify for refinement.
        max_refine_attempts: Maximum number of refinement passes.
        check_timeout_seconds: Overall CrossHair check timeout in seconds.
        cover_timeout_seconds: Overall CrossHair cover timeout in seconds.
    """

    provider: str = "openai"
    model: str = "gpt-4o"
    out_dir: str = "out"
    log_dir: str | None = None
    enable_coverage: bool = False
    check: CrosshairCheckConfig = CrosshairCheckConfig()
    cover: CrosshairCoverConfig = CrosshairCoverConfig()
    refine_budget_seconds: int = 300
    max_refine_attempts: int = 2
    check_timeout_seconds: int = 300
    cover_timeout_seconds: int = 300
