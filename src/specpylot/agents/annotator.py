from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage


@dataclass(frozen=True)
class AnnotatorResult:
    """Container for a parsed annotation response."""

    annotated_code: str
    raw_text: str
    raw_attempts: list[str]
    attempts: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class AnnotatorAgent:
    """Prompt-agnostic annotator that enforces the expected wrapper format."""

    def __init__(self, llm: BaseChatModel, *, max_retries: int = 2) -> None:
        """Create an annotator for a given chat model.

        Args:
            llm: LangChain chat model instance.
            max_retries: Number of retries after the first attempt.

        Raises:
            ValueError: If max_retries is negative.
        """
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        self._llm = llm
        self._max_retries = max_retries

    def annotate(
        self,
        messages: Sequence[BaseMessage],
        *,
        extra_retry_instruction: Optional[str] = None,
    ) -> AnnotatorResult:
        """Invoke the model and return parsed annotated code, with retries.

        Args:
            messages: Prepared LangChain messages to send.
            extra_retry_instruction: Optional extra instruction for retry attempts.

        Returns:
            AnnotatorResult: Parsed annotated code and metadata.

        Raises:
            ValueError: If the model never returns a valid annotated response.
        """
        cur_messages: List[BaseMessage] = list(messages)

        last_raw: str = ""
        last_err: Optional[Exception] = None
        raw_attempts: list[str] = []
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0

        total_attempts = 1 + self._max_retries
        for attempt in range(1, total_attempts + 1):
            raw, usage = self._invoke_text(cur_messages)
            last_raw = raw
            raw_attempts.append(raw)
            prompt_tokens += usage.get("prompt_tokens", 0)
            completion_tokens += usage.get("completion_tokens", 0)
            total_tokens += usage.get("total_tokens", 0)

            try:
                # Lazy import so this module doesn't hard-depend on your parser at import time.
                from specpylot.utils.output_parser import (
                    extract_annotated_code,
                )  # noqa: WPS433

                annotated = extract_annotated_code(raw)
                return AnnotatorResult(
                    annotated_code=annotated,
                    raw_text=raw,
                    raw_attempts=raw_attempts,
                    attempts=attempt,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )
            except Exception as e:  # noqa: BLE001
                last_err = e
                if attempt >= total_attempts:
                    break

                cur_messages = self._with_format_fix_message(
                    cur_messages,
                    raw_text=raw,
                    error=e,
                    extra_retry_instruction=extra_retry_instruction,
                )

        raise ValueError(
            "Failed to obtain a valid <annotated code>...</annotated code> response "
            f"after {total_attempts} attempt(s). Last error: {last_err}. "
            f"Last response snippet: {self._snippet(last_raw)}"
        )

    def _invoke_text(self, messages: Sequence[BaseMessage]) -> tuple[str, dict]:
        """Invoke the model and normalize to a stripped content string."""
        try:
            resp = self._llm.invoke(list(messages))
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            lower = msg.lower()
            if "not_found_error" in lower or "model:" in lower or "404" in lower:
                model = (
                    getattr(self._llm, "model_name", None)
                    or getattr(self._llm, "model", None)
                    or "<unknown>"
                )
                raise ValueError(
                    "LLM model not found. Check the --model value for the selected "
                    f"provider. Model: {model}. Original error: {msg}"
                ) from exc
            raise
        usage = self._extract_usage(resp)
        if isinstance(resp, AIMessage):
            return (resp.content or "").strip(), usage
        return (getattr(resp, "content", "") or "").strip(), usage

    def _with_format_fix_message(
        self,
        messages: List[BaseMessage],
        *,
        raw_text: str,
        error: Exception,
        extra_retry_instruction: Optional[str],
    ) -> List[BaseMessage]:
        """Append a format-fix instruction to the message list."""
        instruction_lines = [
            "FORMAT FIX REQUIRED.",
            "Your previous response did not match the required output format.",
            "",
            "Return ONLY a single wrapper and close the tags:",
            "<annotated code>",
            "# icontract annotated code",
            "<full python file content here>",
            "</annotated code>",
            "",
            "Rules:",
            "- No text before <annotated code> or after </annotated code>.",
            "- Output inside the wrapper must be valid Python.",
            "- Do not use Markdown or code fences.",
            "",
            f"Parsing error: {type(error).__name__}: {error}",
            f"Previous response snippet: {self._snippet(raw_text)}",
        ]

        if extra_retry_instruction:
            instruction_lines.extend(
                ["", "Additional constraints:", extra_retry_instruction]
            )

        return [*messages, HumanMessage(content="\n".join(instruction_lines))]

    @staticmethod
    def _snippet(text: str, *, head: int = 100, tail: int = 100) -> str:
        """Return a compact snippet for error messages."""
        if not text:
            return "<empty>"
        if len(text) <= head + tail + 10:
            return repr(text)
        return repr(text[:head] + "\n...\n" + text[-tail:])

    @staticmethod
    def _extract_usage(resp: object) -> dict:
        usage_meta = {}
        if hasattr(resp, "usage_metadata") and isinstance(
            getattr(resp, "usage_metadata"), dict
        ):
            usage_meta = dict(getattr(resp, "usage_metadata"))

        response_meta = {}
        if hasattr(resp, "response_metadata") and isinstance(
            getattr(resp, "response_metadata"), dict
        ):
            response_meta = dict(getattr(resp, "response_metadata"))

        token_usage = {}
        if isinstance(response_meta.get("token_usage"), dict):
            token_usage = dict(response_meta.get("token_usage"))

        provider_usage = {}
        if isinstance(response_meta.get("usage"), dict):
            provider_usage = dict(response_meta.get("usage"))

        # LangChain standard usage_metadata uses input/output/total tokens.
        prompt = usage_meta.get("input_tokens")
        completion = usage_meta.get("output_tokens")
        total = usage_meta.get("total_tokens")

        # OpenAI-style response_metadata.token_usage uses prompt/completion/total tokens.
        if prompt is None:
            prompt = token_usage.get("prompt_tokens")
        if completion is None:
            completion = token_usage.get("completion_tokens")
        if total is None:
            total = token_usage.get("total_tokens")

        # Anthropic-style response_metadata.usage uses input/output tokens.
        if prompt is None:
            prompt = provider_usage.get("input_tokens")
        if completion is None:
            completion = provider_usage.get("output_tokens")
        if prompt is None:
            prompt = provider_usage.get("prompt_tokens")
        if completion is None:
            completion = provider_usage.get("completion_tokens")
        if total is None:
            total = provider_usage.get("total_tokens")

        # Ollama-style response_metadata may include eval counts.
        if prompt is None and isinstance(response_meta.get("prompt_eval_count"), int):
            prompt = response_meta.get("prompt_eval_count")
        if completion is None and isinstance(response_meta.get("eval_count"), int):
            completion = response_meta.get("eval_count")

        if total is None and prompt is not None and completion is not None:
            total = int(prompt) + int(completion)

        return {
            "prompt_tokens": int(prompt or 0),
            "completion_tokens": int(completion or 0),
            "total_tokens": int(total or 0),
        }
