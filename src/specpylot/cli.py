from __future__ import annotations

"""Command-line entrypoint for Specpylot."""

import argparse
from pathlib import Path

from specpylot.config import CrosshairCheckConfig, CrosshairCoverConfig, PipelineConfig
from specpylot.pipeline.pipeline import SpecpylotPipeline


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        argparse.ArgumentParser: Configured parser for Specpylot CLI.
    """
    parser = argparse.ArgumentParser(prog="specpylot", description="Specpylot pipeline")
    parser.add_argument(
        "--target",
        default="examples/divide.py",
        help="Target file path relative to the project root.",
    )
    parser.add_argument(
        "--out",
        default="out",
        help="Output directory for final artifacts.",
    )
    parser.add_argument(
        "--log",
        default=None,
        help="Log directory for detailed artifacts (messages, stdout/stderr, intermediates).",
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate CrossHair cover tests (disabled by default).",
    )
    parser.add_argument(
        "--provider",
        default="openai",
        help="LLM provider: openai | anthropic | ollama",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o",
        help="Model name for the annotator/refiner.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature for the model.",
    )
    parser.add_argument(
        "--refine",
        type=int,
        default=2,
        help="Maximum number of refinement attempts.",
    )
    parser.add_argument(
        "--refine-budget-seconds",
        type=int,
        default=300,
        help="Max seconds allowed for a refutation to qualify for refinement.",
    )
    parser.add_argument(
        "--check-timeout-seconds",
        type=int,
        default=300,
        help="Overall CrossHair check timeout (seconds).",
    )
    parser.add_argument(
        "--cover-timeout-seconds",
        type=int,
        default=300,
        help="Overall CrossHair cover timeout (seconds).",
    )
    parser.add_argument(
        "--check-per-condition-timeout",
        default="60",
        help="CrossHair check per-condition timeout (seconds).",
    )
    parser.add_argument(
        "--check-per-path-timeout",
        default="5",
        help="CrossHair check per-path timeout (seconds).",
    )
    parser.add_argument(
        "--check-max-uninteresting-iters",
        default="100",
        help="CrossHair check max uninteresting iterations.",
    )
    parser.add_argument(
        "--cover-per-condition-timeout",
        default="60",
        help="CrossHair cover per-condition timeout (seconds).",
    )
    parser.add_argument(
        "--cover-per-path-timeout",
        default="5",
        help="CrossHair cover per-path timeout (seconds).",
    )
    parser.add_argument(
        "--cover-max-uninteresting-iters",
        default="100",
        help="CrossHair cover max uninteresting iterations.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the Specpylot CLI.

    Args:
        argv: Optional list of CLI arguments. If None, uses sys.argv.

    Returns:
        int: Exit code (0 for success).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    cfg = PipelineConfig(
        provider=args.provider,
        model=args.model,
        out_dir=args.out,
        log_dir=args.log,
        enable_coverage=args.coverage,
        refine_budget_seconds=args.refine_budget_seconds,
        max_refine_attempts=args.refine,
        check_timeout_seconds=args.check_timeout_seconds,
        cover_timeout_seconds=args.cover_timeout_seconds,
        check=CrosshairCheckConfig(
            per_condition_timeout=args.check_per_condition_timeout,
            per_path_timeout=args.check_per_path_timeout,
            max_uninteresting_iters=args.check_max_uninteresting_iters,
        ),
        cover=CrosshairCoverConfig(
            per_condition_timeout=args.cover_per_condition_timeout,
            per_path_timeout=args.cover_per_path_timeout,
            max_uninteresting_iters=args.cover_max_uninteresting_iters,
        ),
    )
    pipeline = SpecpylotPipeline(
        entry_file=Path.cwd(),
        target_relpath=args.target,
        cfg=cfg,
        temperature=args.temperature,
    )
    try:
        pipeline.run()
    except ValueError as exc:
        msg = str(exc)
        print(f"ERROR: {msg}")
        if "LLM model not found" in msg:
            print("Hint: verify the --model value matches your provider.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
