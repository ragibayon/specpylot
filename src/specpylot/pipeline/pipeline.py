from __future__ import annotations

"""Single-file pipeline orchestrating annotation, refinement, and coverage."""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from pprint import pprint
from typing import Any

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from specpylot.agents.annotator import AnnotatorAgent
from specpylot.config import PipelineConfig
from specpylot.prompts.prompt_loader import PromptLoader
from specpylot.utils.classify_errors import classify_crosshair_result
from specpylot.utils.crosshair_bundle import build_crosshair_refutation_bundle
from specpylot.utils.crosshair_cover import run_crosshair_cover_pytest
from specpylot.utils.crosshair_logging import log_crosshair_result
from specpylot.utils.exec import run_project_local
from specpylot.utils.fs import fs_safe_name, write_text
from specpylot.utils.term_log import TermLog
from specpylot.utils.utils import find_project_root


def _should_start_refinement(
    *,
    cls: dict,
    ch_result: dict,
    budget_seconds: int,
) -> bool:
    """Return True when a refutation is found quickly enough to justify refinement."""
    if cls.get("status") != "REFUTED":
        return False

    if not cls.get("counterexample"):
        return False

    if bool(ch_result.get("timeout")):
        return False

    runtime_ms = ch_result.get("runtime")
    if runtime_ms is None:
        return False

    try:
        runtime_s = float(runtime_ms) / 1000.0
    except (TypeError, ValueError):
        return False

    return runtime_s <= float(budget_seconds)


class SpecpylotPipeline:
    """Single pipeline orchestrating annotation, refinement, and coverage flows."""

    def __init__(
        self,
        *,
        entry_file: Path,
        target_relpath: str,
        cfg: PipelineConfig = PipelineConfig(),
        temperature: float = 0.0,
    ) -> None:
        """Initialize pipeline configuration and resolve project paths.

        Args:
            entry_file: A path used to locate the project root.
            target_relpath: Target file path relative to the project root.
            cfg: Pipeline configuration object.
            temperature: LLM sampling temperature.
        """
        self.cfg = cfg
        self.temperature = temperature

        project_root = find_project_root(entry_file)
        self.project_root = project_root
        self.prompt_dir = project_root / "src/specpylot/prompts"
        self.examples_dir = project_root / "src/specpylot/prompts/few_shot_examples"
        self.target_path = project_root / target_relpath
        self.target_code = self.target_path.read_text()

    def run(self) -> dict[str, Any]:
        """Run the full pipeline and return a dict of artifacts and metadata.

        Returns:
            dict[str, Any]: Run artifacts, metadata, and output locations.
        """
        ui = TermLog()
        ui.header("Specpylot annotation pipeline")

        self._log_config(ui)
        loader = PromptLoader(self.prompt_dir)
        messages = self._build_messages(ui, loader)

        agent, llm = self._build_agent()
        code_name = Path(self.target_path).stem
        llm_name = fs_safe_name(
            getattr(llm, "model_name", None)
            or getattr(llm, "model", None)
            or "unknown_llm"
        )
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run_id = f"{code_name}_{ts}"

        out_root = Path(self.cfg.out_dir)
        out_run_dir = out_root / run_id
        out_run_dir.mkdir(parents=True, exist_ok=True)

        log_run_dir = None
        if self.cfg.log_dir:
            log_run_dir = Path(self.cfg.log_dir) / run_id
            log_run_dir.mkdir(parents=True, exist_ok=True)
            self._write_messages(log_run_dir / "messages_annotation.json", messages)

        result = self._annotate(ui, agent, messages)
        annotated_relpath = self.target_path.name

        current_code = result.annotated_code
        refined = None
        refine_attempts = 0
        ch_result = {}
        meta = {}
        cls = {}
        bundle = {}

        self._maybe_write_llm_attempts(
            log_run_dir,
            step="annotation",
            raw_attempts=result.raw_attempts,
            annotated_code=current_code,
        )

        while True:
            ch_result, meta, cls, bundle = self._run_crosshair_check(
                ui=ui,
                code_name=code_name,
                llm_name=llm_name,
                ts=ts,
                annotated_relpath=annotated_relpath,
                files={annotated_relpath: current_code},
                log_run_dir=log_run_dir,
            )

            if cls.get("status") == "PASSED":
                ui.ok("CrossHair check passed; stopping refinement loop.")
                break

            refine_started = _should_start_refinement(
                cls=cls,
                ch_result=ch_result,
                budget_seconds=self.cfg.refine_budget_seconds,
            )
            if not refine_started:
                ui.warn("Refinement not triggered; stopping refinement loop.")
                break

            if refine_attempts >= self.cfg.max_refine_attempts:
                ui.warn("Reached max refinement attempts; stopping refinement loop.")
                break

            refined = self._run_refinement(
                ui=ui,
                loader=loader,
                agent=agent,
                annotated_code=current_code,
                bundle=bundle,
                log_run_dir=log_run_dir,
                refine_attempt=refine_attempts + 1,
            )
            refine_attempts += 1
            current_code = refined.annotated_code
            self._maybe_write_llm_attempts(
                log_run_dir,
                step=f"refine_{refine_attempts}",
                raw_attempts=refined.raw_attempts,
                annotated_code=current_code,
            )

        cover_res = {}
        run_dir = (
            Path(meta["run_dir"]) if meta.get("run_dir") else self.project_root / "logs"
        )
        if self.cfg.enable_coverage:
            cover_res, run_dir = self._run_cover(
                ui=ui,
                annotated_relpath=annotated_relpath,
                annotated_code=current_code,
                run_dir=run_dir,
                log_run_dir=log_run_dir,
            )

        self._finalize(
            ui=ui,
            code_name=code_name,
            llm_name=llm_name,
            ts=ts,
            result_code=current_code,
            run_dir=run_dir,
            cls=cls,
            refine_attempts=refine_attempts,
            out_run_dir=out_run_dir,
            cover_res=cover_res,
            llm_info={
                "provider": self.cfg.provider,
                "model": self.cfg.model,
                "temperature": self.temperature,
            },
            log_run_dir=log_run_dir,
            ch_result=ch_result,
            meta=meta,
        )

        return {
            "result": result,
            "refined": refined,
            "refine_attempts": refine_attempts,
            "crosshair": ch_result,
            "crosshair_meta": meta,
            "crosshair_classification": cls,
            "crosshair_bundle": bundle,
            "cover": cover_res,
            "run_dir": str(run_dir),
            "out_dir": str(out_run_dir),
            "log_dir": str(log_run_dir) if log_run_dir else None,
        }

    def _log_config(self, ui: TermLog) -> None:
        ui.kv(
            "Run config",
            {
                "target": str(self.target_path),
                "check_per_condition_timeout": self.cfg.check.per_condition_timeout,
                "check_per_path_timeout": self.cfg.check.per_path_timeout,
                "check_max_uninteresting_iters": self.cfg.check.max_uninteresting_iters,
                "cover_per_condition_timeout": self.cfg.cover.per_condition_timeout,
                "cover_per_path_timeout": self.cfg.cover.per_path_timeout,
                "cover_max_uninteresting_iters": self.cfg.cover.max_uninteresting_iters,
            },
        )

        ui.header("Preparing prompts")
        ui.info(f"Prompts dir: {self.prompt_dir}")
        ui.info(f"Few-shot dir: {self.examples_dir}")
        ui.info(f"Target file: {self.target_path}")

    def _build_messages(self, ui: TermLog, loader: PromptLoader) -> list:
        with ui.step("Building LangChain messages"):
            return loader.build_annotation_messages(
                system_template="system_prompt.jinja2",
                human_template="human_annotate.jinja2",
                target_code=self.target_code,
                few_shot_example_dirs=self.examples_dir,
                max_examples=0,
            )

    def _build_agent(self) -> tuple[AnnotatorAgent, Any]:
        load_dotenv()
        llm = self._build_llm()
        agent = AnnotatorAgent(llm, max_retries=2)
        return agent, llm

    def _build_llm(self) -> Any:
        provider = (self.cfg.provider or "").strip().lower()
        model = self.cfg.model

        if provider == "openai":
            if not os.environ.get("OPENAI_API_KEY"):
                raise ValueError(
                    "OPENAI_API_KEY is not set; required for provider=openai."
                )
            return ChatOpenAI(model=model, temperature=self.temperature)
        if provider == "anthropic":
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise ValueError(
                    "ANTHROPIC_API_KEY is not set; required for provider=anthropic."
                )
            return ChatAnthropic(model=model, temperature=self.temperature)
        if provider == "ollama":
            if not os.environ.get("OLLAMA_BASE_URL"):
                raise ValueError(
                    "OLLAMA_BASE_URL is not set; set it if your Ollama server is not on the default."
                )
            return ChatOllama(model=model, temperature=self.temperature)

        raise ValueError(f"Unknown provider: {self.cfg.provider!r}")

    def _annotate(
        self,
        ui: TermLog,
        agent: AnnotatorAgent,
        messages: list,
    ) -> Any:
        ui.header("Generating annotations")
        with ui.step("Calling LLM annotator"):
            result = agent.annotate(
                messages,
                extra_retry_instruction=(
                    "Ensure the output is wrapped in exactly one <annotated code>...</annotated code> pair."
                ),
            )

        ui.ok(f"Annotation attempts: {result.attempts}")
        ui.kv(
            "Annotation sizes",
            {
                "raw_response_len": len(result.raw_text),
                "annotated_code_len": len(result.annotated_code),
            },
        )
        return result

    def _run_crosshair_check(
        self,
        *,
        ui: TermLog,
        code_name: str,
        llm_name: str,
        ts: str,
        annotated_relpath: str,
        files: dict[str, str],
        log_run_dir: Path | None,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        check_cmd = [
            "crosshair",
            "check",
            "--analysis_kind",
            "icontract",
            "--per_condition_timeout",
            self.cfg.check.per_condition_timeout,
            "--per_path_timeout",
            self.cfg.check.per_path_timeout,
            "--max_uninteresting_iterations",
            self.cfg.check.max_uninteresting_iters,
            "-v",
            annotated_relpath,
        ]

        ui.header("Verifying (CrossHair check)")
        ui.info(" ".join(check_cmd))
        with ui.step("Running crosshair check"):
            ch_result = run_project_local(
                files=files,
                command=check_cmd,
                timeout_seconds=self.cfg.check_timeout_seconds,
                workdir=".",
            )

        log_dir = None
        if log_run_dir:
            log_dir = log_run_dir / "crosshair"
            log_dir.mkdir(parents=True, exist_ok=True)

        if log_dir:
            with ui.step("Logging CrossHair outputs"):
                meta = log_crosshair_result(
                    log_dir=log_dir,
                    target_label=code_name,
                    command=check_cmd,
                    ch_result=ch_result,
                    annotated_code_text=files[annotated_relpath],
                    annotated_code_filename=f"{code_name}_annotated_{llm_name}_{ts}.py",
                )
        else:
            meta = {
                "run_dir": "",
                "summary_path": "",
                "path_tree_stats_last": self._parse_path_tree_stats(
                    ch_result.get("stderr", "") or ""
                ),
                "iterations_last": self._parse_iterations(
                    ch_result.get("stderr", "") or ""
                ),
            }

        cls = classify_crosshair_result(
            stdout=ch_result.get("stdout", "") or "",
            stderr=ch_result.get("stderr", "") or "",
            exit_code=int(ch_result.get("exit_code", -999)),
            path_tree_stats_last=meta.get("path_tree_stats_last"),
            iterations_last=meta.get("iterations_last"),
        )

        bundle = build_crosshair_refutation_bundle(
            stdout=ch_result.get("stdout", "") or "",
            stderr=ch_result.get("stderr", "") or "",
            cls=cls,
            meta=meta,
        )

        ui.kv(
            "CrossHair check summary",
            {
                "status": cls.get("status"),
                "reason": cls.get("reason"),
                "exit_code": ch_result.get("exit_code"),
                "runtime_ms": ch_result.get("runtime"),
                "timeout": ch_result.get("timeout"),
                "iterations_last": meta.get("iterations_last"),
                "path_tree_stats_last": self._filter_path_tree_stats(
                    meta.get("path_tree_stats_last") or {}
                ),
                "run_dir": meta.get("run_dir"),
                "summary_path": meta.get("summary_path"),
            },
        )

        return ch_result, meta, cls, bundle

    @staticmethod
    def _parse_path_tree_stats(stderr_text: str) -> dict[str, int]:
        stats_re = re.compile(r"Path tree stats\s*\{([^}]*)\}")
        matches = list(stats_re.finditer(stderr_text or ""))
        if not matches:
            return {}
        inner = matches[-1].group(1).strip()
        if not inner:
            return {}
        out: dict[str, int] = {}
        for part in inner.split(","):
            part = part.strip()
            if not part or ":" not in part:
                continue
            k, v = part.split(":", 1)
            k = k.strip()
            v = v.strip()
            try:
                out[k] = int(v)
            except ValueError:
                continue
        return out

    @staticmethod
    def _parse_iterations(stderr_text: str) -> int | None:
        iter_re = re.compile(r"Number of iterations:\s*(\d+)")
        matches = list(iter_re.finditer(stderr_text or ""))
        if not matches:
            return None
        return int(matches[-1].group(1))

    @staticmethod
    def _filter_path_tree_stats(stats: dict[str, int]) -> dict[str, int]:
        keep = {"confirmed", "unknown", "refuted", "none"}
        out: dict[str, int] = {}
        for k, v in stats.items():
            if k.lower() in keep:
                out[k] = int(v)
        return out

    def _run_refinement(
        self,
        *,
        ui: TermLog,
        loader: PromptLoader,
        agent: AnnotatorAgent,
        annotated_code: str,
        bundle: dict[str, Any],
        log_run_dir: Path | None,
        refine_attempt: int,
    ) -> Any:
        refine_messages = loader.build_refinement_messages(
            system_template="refinement_system_prompt.jinja2",
            human_template="refinement_human_prompt.jinja2",
            annotated_code=annotated_code,
            crosshair_bundle=bundle,
        )
        if log_run_dir:
            self._write_messages(
                log_run_dir / f"messages_refine_{refine_attempt}.json",
                refine_messages,
            )

        ui.warn("Refinement triggered based on policy.")
        ui.header("Refining annotations")
        with ui.step("Calling LLM refiner"):
            refined = agent.annotate(
                refine_messages,
                extra_retry_instruction=(
                    "Ensure output is wrapped in exactly one <annotated code>...</annotated code> pair."
                ),
            )
        return refined

    def _run_cover(
        self,
        *,
        ui: TermLog,
        annotated_relpath: str,
        annotated_code: str,
        run_dir: Path,
        log_run_dir: Path | None,
    ) -> tuple[dict[str, Any], Path]:
        cover_cmd_prefix = [
            "crosshair",
            "cover",
            "--example_output_format",
            "pytest",
            "--coverage_type",
            "opcode",
            "--per_condition_timeout",
            self.cfg.cover.per_condition_timeout,
            "--per_path_timeout",
            self.cfg.cover.per_path_timeout,
            "--max_uninteresting_iterations",
            self.cfg.cover.max_uninteresting_iters,
            "-v",
        ]

        ui.header("Generating testcases (CrossHair cover -> pytest)")
        ui.info(" ".join(cover_cmd_prefix) + " <TARGET>")
        with ui.step("Running crosshair cover"):
            cover_res = run_crosshair_cover_pytest(
                annotated_relpath=annotated_relpath,
                annotated_code=annotated_code,
                cover_cmd_prefix=cover_cmd_prefix,
                timeout_seconds=self.cfg.cover_timeout_seconds,
            )

        if log_run_dir:
            run_dir.mkdir(parents=True, exist_ok=True)

        cover_stdout = cover_res.get("stdout") or ""
        cover_stderr = cover_res.get("stderr") or ""

        cover_pytest_path = run_dir / "pytest_from_crosshair_cover.py"
        cover_stdout_path = run_dir / "stdout_from_crosshair_cover.txt"
        cover_stderr_path = run_dir / "stderr_from_crosshair_cover.txt"

        with ui.step("Saving cover artifacts"):
            if log_run_dir:
                write_text(cover_stdout_path, cover_stdout)
                write_text(cover_stderr_path, cover_stderr)
                if cover_stdout.strip():
                    write_text(cover_pytest_path, cover_stdout.rstrip() + "\n")
                cover_dir = log_run_dir / "cover"
                cover_dir.mkdir(parents=True, exist_ok=True)
                write_text(cover_dir / "stdout.txt", cover_stdout)
                write_text(cover_dir / "stderr.txt", cover_stderr)
                if cover_stdout.strip():
                    write_text(cover_dir / "test.py", cover_stdout.rstrip() + "\n")

        ui.kv(
            "CrossHair cover summary",
            {
                "exit_code": cover_res.get("exit_code"),
                "runtime_ms": cover_res.get("runtime"),
                "timeout": cover_res.get("timeout"),
                "cover_targets": cover_res.get("cover_targets"),
                "pytest_path": (
                    str(cover_pytest_path) if cover_stdout.strip() else "(none)"
                ),
                "stdout_path": str(cover_stdout_path),
                "stderr_path": str(cover_stderr_path),
            },
        )

        return cover_res, run_dir

    def _finalize(
        self,
        *,
        ui: TermLog,
        code_name: str,
        llm_name: str,
        ts: str,
        result_code: str,
        run_dir: Path,
        refine_attempts: int,
        cls: dict[str, Any],
        out_run_dir: Path,
        cover_res: dict[str, Any],
        llm_info: dict[str, Any],
        log_run_dir: Path | None,
        ch_result: dict[str, Any],
        meta: dict[str, Any],
    ) -> None:
        ui.header("Finalizing")
        ui.info(f"Run dir (source of truth): {run_dir}")

        output_code_path = out_run_dir / f"{code_name}.py"
        write_text(output_code_path, result_code)
        ui.ok(f"Saved annotated code: {output_code_path}")

        cover_test_path = ""
        if cover_res:
            cover_test_path = str(out_run_dir / "test.py")
            write_text(
                Path(cover_test_path), (cover_res.get("stdout") or "").rstrip() + "\n"
            )

        results_path = out_run_dir / "results.json"
        results = {
            "run_id": out_run_dir.name,
            "target": str(self.target_path),
            "provider": llm_info.get("provider"),
            "model": llm_info.get("model"),
            "temperature": llm_info.get("temperature"),
            "refine_attempts": refine_attempts,
            "final_status": cls.get("status"),
            "last_counterexample": cls.get("counterexample") or "",
            "crosshair": {
                "status": cls.get("status"),
                "reason": cls.get("reason"),
                "exit_code": ch_result.get("exit_code"),
                "runtime_ms": ch_result.get("runtime"),
                "timeout": ch_result.get("timeout"),
                "iterations_last": meta.get("iterations_last"),
                "path_tree_stats_last": meta.get("path_tree_stats_last") or {},
            },
            "coverage": {
                "enabled": self.cfg.enable_coverage,
                "exit_code": cover_res.get("exit_code") if cover_res else None,
                "runtime_ms": cover_res.get("runtime") if cover_res else None,
                "timeout": cover_res.get("timeout") if cover_res else None,
                "cover_targets": cover_res.get("cover_targets") if cover_res else None,
            },
            "paths": {
                "annotated_code": str(output_code_path),
                "cover_test": cover_test_path,
                "results_json": str(results_path),
                "log_dir": str(log_run_dir) if log_run_dir else "",
            },
        }
        results_path.write_text(json.dumps(results, indent=2, sort_keys=True))

        ui.kv(
            "Refinement summary",
            {
                "attempts": refine_attempts,
                "final_status": cls.get("status"),
                "last_counterexample": cls.get("counterexample") or "",
            },
        )

    def _write_messages(self, path: Path, messages: list) -> None:
        serial = [
            {"type": m.__class__.__name__, "content": getattr(m, "content", "")}
            for m in messages
        ]
        path.write_text(json.dumps(serial, indent=2))

    def _maybe_write_llm_attempts(
        self,
        log_run_dir: Path | None,
        *,
        step: str,
        raw_attempts: list[str],
        annotated_code: str,
    ) -> None:
        if not log_run_dir:
            return
        step_dir = log_run_dir / step
        step_dir.mkdir(parents=True, exist_ok=True)
        for idx, raw in enumerate(raw_attempts, start=1):
            write_text(step_dir / f"raw_attempt_{idx}.txt", raw)
        write_text(step_dir / "annotated_code.py", annotated_code)
