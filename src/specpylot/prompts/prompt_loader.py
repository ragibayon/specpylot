from __future__ import annotations

"""Prompt loading and LangChain message construction utilities."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Mapping, Optional, Union

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


@dataclass(frozen=True)
class FewShotExample:
    """A single few-shot example pair (input file -> annotated output file).

    Attributes:
        example_input: Raw Python source of the example input file.
        example_output: Raw Python source of the example annotated output file.
        name: Human-readable name for the example (typically the folder name).
    """

    example_input: str
    example_output: str
    name: str


class PromptLoader:
    """Loads and renders prompt templates and builds LangChain messages.

    This loader supports:
      - Jinja2 templates for system/human prompts (e.g., system_prompt.jinja2,
        human_annotate.jinja2).
      - Optional few-shot examples stored as folders:
            prompts/few_shot_examples/<name>/input.py
            prompts/few_shot_examples/<name>/output.py

    The message builder produces a message sequence:
      1) System message (rendered system template)
      2) Zero or more few-shot pairs (Human example input, AI example output)
      3) Human message for the target code (rendered human template)

    Few-shot examples are optional. If no examples are provided, the builder emits
    only the system and target human messages.

    Notes:
        - This class is intentionally "dumb IO": it reads files and renders templates.
        - Validation is minimal; the output format enforcement should live in an output
          parser downstream.
    """

    def __init__(self, prompt_dir: Path) -> None:
        """Initialize the loader with a prompt directory.

        Args:
            prompt_dir: Directory containing prompt templates and optional few-shot
                examples.
        """
        self.prompt_dir = prompt_dir
        self._env = Environment(
            loader=FileSystemLoader(str(prompt_dir)),
            undefined=StrictUndefined,
            autoescape=False,
            keep_trailing_newline=True,
        )

    def read_text(self, rel_path: str) -> str:
        """Read a plain text file under the prompt directory.

        Args:
            rel_path: Path relative to prompt_dir.

        Returns:
            File contents as a string.
        """
        return (self.prompt_dir / rel_path).read_text()

    def render(self, template_rel_path: str, **vars: Any) -> str:
        """Render a Jinja2 template under the prompt directory.

        Args:
            template_rel_path: Template path relative to prompt_dir.
            **vars: Variables passed to the Jinja2 template.

        Returns:
            Rendered template text.
        """
        template = self._env.get_template(template_rel_path)
        return template.render(**vars)

    def load_system_prompt(
        self, system_template: str = "system_prompt.jinja2", **vars: Any
    ) -> str:
        """Load and render the system prompt template.

        Args:
            system_template: Relative template file name under prompt_dir.
            **vars: Variables passed to the template.

        Returns:
            Rendered system prompt.
        """
        return self.render(system_template, **vars)

    def load_human_prompt(
        self, human_template: str = "human_annotate.jinja2", **vars: Any
    ) -> str:
        """Load and render the human prompt template.

        Args:
            human_template: Relative template file name under prompt_dir.
            **vars: Variables passed to the template.

        Returns:
            Rendered human prompt.
        """
        return self.render(human_template, **vars)

    def load_few_shot_example_dir(self, example_dir: Path) -> FewShotExample:
        """Load a single few-shot example from a directory.

        The directory must contain:
          - input.py
          - output.py

        Args:
            example_dir: Absolute or resolved path to the example directory.

        Returns:
            A FewShotExample loaded from the directory.

        Raises:
            FileNotFoundError: If input.py or output.py is missing.
        """
        in_path = example_dir / "input.py"
        out_path = example_dir / "output.py"
        if not in_path.exists():
            raise FileNotFoundError(f"Missing input.py: {in_path}")
        if not out_path.exists():
            raise FileNotFoundError(f"Missing output.py: {out_path}")

        return FewShotExample(
            name=example_dir.name,
            example_input=in_path.read_text(),
            example_output=out_path.read_text(),
        )

    def load_few_shot_examples_from_parent(
        self, parent_dir: Path
    ) -> List[FewShotExample]:
        """Discover and load all few-shot examples under a parent directory.

        Each example is a subdirectory under parent_dir containing both input.py and
        output.py. Non-directories are ignored. Subdirectories missing either file
        are ignored.

        Args:
            parent_dir: Directory containing example subdirectories.

        Returns:
            A list of FewShotExample objects. Empty if no valid examples exist.
        """
        if not parent_dir.exists() or not parent_dir.is_dir():
            return []

        examples: List[FewShotExample] = []
        for d in sorted(parent_dir.iterdir()):
            if not d.is_dir():
                continue
            if (d / "input.py").exists() and (d / "output.py").exists():
                examples.append(self.load_few_shot_example_dir(d))
        return examples

    def load_few_shot_examples(
        self, src: Optional[Union[List[str], Path]]
    ) -> List[FewShotExample]:
        """Load few-shot examples from a parent directory or a list of folders.

        Two modes are supported:
          - Path mode: `src` is a Path to a parent directory. The loader discovers
            valid example subdirectories (each containing input.py and output.py).
          - List mode: `src` is a list of relative directories (relative to prompt_dir).
            Each directory must contain input.py and output.py, otherwise an error
            is raised.

        Args:
            src: Either:
                - None (no examples),
                - a Path to a parent directory containing example subdirectories, or
                - a list of relative directories (under prompt_dir) that each contain
                  input.py and output.py.

        Returns:
            A list of loaded few-shot examples. Empty if src is None or no valid
            examples exist (Path mode).

        Raises:
            FileNotFoundError: If list mode is used and any listed directory is missing.
        """
        if src is None:
            return []

        if isinstance(src, Path):
            return self.load_few_shot_examples_from_parent(src)

        rel_dirs: List[str] = src
        if not rel_dirs:
            return []

        examples: List[FewShotExample] = []
        for rel in rel_dirs:
            d = self.prompt_dir / rel
            if not d.exists() or not d.is_dir():
                raise FileNotFoundError(f"Few-shot example dir not found: {d}")
            examples.append(self.load_few_shot_example_dir(d))
        return examples

    def build_annotation_messages(
        self,
        *,
        system_template: str,
        human_template: str,
        target_code: str,
        few_shot_example_dirs: Optional[Union[List[str], Path]] = None,
        max_examples: int = 1,
        system_vars: Optional[dict[str, Any]] = None,
    ) -> List:
        """Build the message sequence for the annotation request.

        Message order:
          1) System message (rendered system template)
          2) Few-shot examples (0..N):
             - Human: example input wrapped in <CODE> ... </CODE>
             - AI: example annotated output wrapped in <annotated code> ... </annotated code>
          3) Human message: the target prompt (rendered human template with `code=target_code`)

        Args:
            system_template: Relative path to the system Jinja template under prompt_dir.
            human_template: Relative path to the human Jinja template under prompt_dir.
            target_code: Raw Python source to be annotated.
            few_shot_example_dirs: Optional few-shot source:
                - None: no examples
                - Path: parent directory containing example subfolders
                - List[str]: relative example folder paths under prompt_dir
            max_examples: Maximum number of few-shot examples to include. Use 0 to
                disable examples even if available. Must be >= 0.
            system_vars: Optional variables for rendering the system template.

        Returns:
            A list of LangChain messages: SystemMessage, optional Human/AI pairs, and
            final HumanMessage.

        Raises:
            ValueError: If max_examples < 0.
        """
        if max_examples < 0:
            raise ValueError("max_examples must be >= 0")

        system_vars = system_vars or {}

        system_text = self.load_system_prompt(system_template, **system_vars)
        human_text = self.load_human_prompt(human_template, code=target_code)

        examples = self.load_few_shot_examples(few_shot_example_dirs)
        examples = examples[:max_examples]

        msgs: List = [SystemMessage(content=system_text)]

        for ex in examples:
            msgs.append(
                HumanMessage(
                    content=(
                        f"EXAMPLE INPUT FILE ({ex.name}):\n"
                        "<CODE>\n"
                        f"{ex.example_input}\n"
                        "</CODE>"
                    )
                )
            )
            msgs.append(
                AIMessage(
                    content=(
                        "<annotated code>\n"
                        "# icontract annotated code\n"
                        f"{ex.example_output.rstrip()}\n"
                        "</annotated code>"
                    )
                )
            )

        msgs.append(HumanMessage(content=human_text))
        return msgs

    def build_refinement_messages(
        self,
        *,
        system_template: str,
        human_template: str,
        annotated_code: str,
        crosshair_bundle: Mapping[str, Any],
        few_shot_example_dirs: Optional[Union[List[str], Path]] = None,
        max_examples: int = 0,
        system_vars: Optional[dict[str, Any]] = None,
        extra_human_vars: Optional[dict[str, Any]] = None,
    ) -> List:
        """Build the message sequence for refinement.

        Message order:
          1) System message (rendered system template)
          2) Few-shot examples (0..N):
             - Human: EXAMPLE INPUT (annotated code + crosshair bundle)
             - AI: EXAMPLE OUTPUT (refined annotated code)
          3) Human message: refinement prompt (rendered human template with annotated_code + crosshair_bundle)

        Notes:
          - The human_template should refer to variables:
              - annotated_code
              - crosshair_bundle
            plus any `extra_human_vars` you pass in.
          - Few-shot examples reuse the same folder schema:
              prompts/few_shot_examples/<name>/input.py
              prompts/few_shot_examples/<name>/output.py
            Here, input.py should be the "before/refute" annotated code,
            and output.py should be the "after/fixed" annotated code.

        Args:
            system_template: Relative system Jinja template under prompt_dir.
            human_template: Relative human Jinja template under prompt_dir.
            annotated_code: Current annotated code to be refined.
            crosshair_bundle: Dict-like evidence bundle from CrossHair.
            few_shot_example_dirs: Optional examples source (None | Path | List[str]).
            max_examples: Max examples to include (>=0).
            system_vars: Variables for rendering the system template.
            extra_human_vars: Extra variables for rendering the human template.

        Returns:
            List of LangChain messages.

        Raises:
            ValueError: If max_examples < 0.
        """
        if max_examples < 0:
            raise ValueError("max_examples must be >= 0")

        system_vars = system_vars or {}
        extra_human_vars = extra_human_vars or {}

        system_text = self.load_system_prompt(system_template, **system_vars)

        # Render the human refinement prompt with evidence + code
        human_text = self.load_human_prompt(
            human_template,
            annotated_code=annotated_code,
            crosshair_bundle=dict(crosshair_bundle),
            **extra_human_vars,
        )

        # Few-shot examples (optional)
        examples = self.load_few_shot_examples(few_shot_example_dirs)
        examples = examples[:max_examples]

        msgs: List = [SystemMessage(content=system_text)]

        for ex in examples:
            # In refinement few-shot, ex.example_input should already be annotated code
            # that needs fixing; ex.example_output is the corrected annotated code.
            msgs.append(
                HumanMessage(
                    content=(
                        f"EXAMPLE (REFINEMENT) INPUT ({ex.name}):\n"
                        "CrossHair evidence: (example-specific; see below)\n"
                        "<CODE>\n"
                        f"{ex.example_input}\n"
                        "</CODE>\n\n"
                        "Note: This is a refinement example; the assistant must update contracts "
                        "to remove CrossHair refutation."
                    )
                )
            )
            msgs.append(
                AIMessage(
                    content=(
                        "<annotated code>\n"
                        "# icontract refined code\n"
                        f"{ex.example_output.rstrip()}\n"
                        "</annotated code>"
                    )
                )
            )

        msgs.append(HumanMessage(content=human_text))
        return msgs
