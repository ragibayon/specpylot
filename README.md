## Specpylot: Python Specification Generation using Large Language Models

Specpylot annotates Python code with icontract contracts, validates them with CrossHair, and optionally refines the contracts. It can also generate pytest stubs via CrossHair cover when enabled.

### DOI
This artifact is also published in Zenodo: DOI
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.8271853.svg)]([https://doi.org/10.5281/zenodo.8271853](https://doi.org/10.5281/zenodo.19491112))



### Tool demo

<a href="https://youtu.be/Kaz4Bvb93ro">
  <img src="https://img.youtube.com/vi/Kaz4Bvb93ro/hqdefault.jpg" alt="Specpylot tool demo video" width="640">
</a>

### Requirements

- Python 3.12+
- An LLM provider and credentials:
  - OpenAI: `OPENAI_API_KEY`
  - Anthropic: `ANTHROPIC_API_KEY`
  - Ollama: local server (optionally set `OLLAMA_BASE_URL`)

You can copy the example environment file and edit it:

```bash
cp .example-env .env
```

Specpylot loads `.env` automatically on startup (via `python-dotenv`). If a key is not found in `.env`, it falls back to environment variables.

### Installation

Using `uv` (recommended):

```bash
uv add .
```

Or with `pip`:

```bash
pip install -e .
```

### Clone, install, run (local)

```bash
git clone https://github.com/ragibayon/specpylot.git
cd specpylot
uv add .
```

Run an example:

```bash
specpylot --target examples/divide.py
```

### Docker from GitHub (example)

```bash
git clone https://github.com/ragibayon/specpylot.git
cd specpylot
docker build -t specpylot .
docker run --rm -e OPENAI_API_KEY=... specpylot --target examples/divide.py
```

By default, Docker writes outputs inside the container. To access outputs on your host, mount a local directory:

```bash
docker run --rm \
  -e OPENAI_API_KEY=... \
  -v "$PWD/out:/app/out" \
  specpylot --target examples/divide.py
```

With coverage enabled:

```bash
docker run --rm \
  -e OPENAI_API_KEY=... \
  -v "$PWD/out:/app/out" \
  specpylot --target examples/divide.py --coverage
```

With logs enabled:

```bash
docker run --rm \
  -e OPENAI_API_KEY=... \
  -v "$PWD/out:/app/out" \
  -v "$PWD/logs:/app/logs" \
  specpylot --target examples/divide.py --coverage --log /app/logs
```

### Quick start

Annotate the example:

```bash
specpylot --target examples/divide.py
```

This writes outputs to `./out/<target>_<timestamp>/`:

- `<target>.py` (final annotated code)
- `test.py` (coverage output, if enabled)
- `results.json` (summary metadata and paths)

### CLI usage

```bash
specpylot \
  --target examples/divide.py \
  --provider openai \
  --model gpt-4o \
  --refine 2 \
  --out out \
  --log logs \
  --coverage
```

#### Options

- `--target`: Path to the input file, relative to the project root.
- `--provider`: `openai` | `anthropic` | `ollama`
- `--model`: Provider model name.
- `--temperature`: Model sampling temperature.
- `--refine`: Max refinement attempts (default 2).
- `--refine-budget-seconds`: Max seconds for a refutation to qualify for refinement (default 300).
- `--out`: Output directory (default `./out`).
- `--log`: Log directory for detailed artifacts (optional).
- `--coverage`: Enable CrossHair cover (disabled by default).
- `--check-timeout-seconds`: Overall CrossHair check timeout (default 300).
- `--cover-timeout-seconds`: Overall CrossHair cover timeout (default 300).
- `--check-per-condition-timeout`: Check per-condition timeout (default 60).
- `--check-per-path-timeout`: Check per-path timeout (default 5).
- `--check-max-uninteresting-iters`: Check max uninteresting iterations (default 100).
- `--cover-per-condition-timeout`: Cover per-condition timeout (default 60).
- `--cover-per-path-timeout`: Cover per-path timeout (default 5).
- `--cover-max-uninteresting-iters`: Cover max uninteresting iterations (default 100).

### Configuration Defaults

| Setting | Default | Description |
| --- | --- | --- |
| provider | `openai` | LLM provider |
| model | `gpt-4o` | Model name |
| temperature | `0.0` | Sampling temperature |
| refine | `2` | Max refinement attempts |
| refine_budget_seconds | `300` | Refine only if refuted within this time |
| out | `./out` | Output directory |
| log | `(none)` | Log directory (disabled if not set) |
| coverage | `false` | Enable CrossHair cover |
| check_timeout_seconds | `300` | Overall CrossHair check timeout |
| cover_timeout_seconds | `300` | Overall CrossHair cover timeout |
| check_per_condition_timeout | `60` | Check per-condition timeout |
| check_per_path_timeout | `5` | Check per-path timeout |
| check_max_uninteresting_iters | `100` | Check max uninteresting iterations |
| cover_per_condition_timeout | `60` | Cover per-condition timeout |
| cover_per_path_timeout | `5` | Cover per-path timeout |
| cover_max_uninteresting_iters | `100` | Cover max uninteresting iterations |

### Providers

#### OpenAI

```bash
export OPENAI_API_KEY=...
specpylot --provider openai --model gpt-4o --target examples/divide.py
```

#### Anthropic

```bash
export ANTHROPIC_API_KEY=...
specpylot --provider anthropic --model claude-3-5-sonnet-20240620 --target examples/divide.py
```

#### Ollama

```bash
# optional: export OLLAMA_BASE_URL=http://localhost:11434
specpylot --provider ollama --model llama3:8b --target examples/divide.py
```

### Output layout

Each run creates a folder:

```shell
out/<target>_<timestamp>/
  <target>.py
  test.py              # only if --coverage
  results.json
```

If `--log` is provided, a matching log folder is created with:

- Messages sent to the LLM (`messages_annotation.json`, `messages_refine_*.json`)
- Raw LLM responses per attempt (`raw_attempt_*.txt`)
- Intermediate annotated code per step
- CrossHair check stdout/stderr and summary
- CrossHair cover stdout/stderr and generated tests

### Limitations

- CrossHair may return INCONCLUSIVE (UNKNOWN paths), especially for complex loops or tight preconditions.
- Contracts that are too strict or solver-unfriendly can lead to "Unable to meet precondition" behavior.
- LLM-generated contracts are best-effort; always review before relying on them.
- Cover generation can be slow on large functions; enable `--coverage` only when needed.
- Some local LLMs (e.g., Ollama models) may not reliably follow the required output format
  (`<annotated code>` wrapper and `# icontract annotated code` header). If that happens,
  try a stronger model, increase retries, or use OpenAI/Anthropic providers.

### Docker

Build and run:

```bash
docker build -t specpylot .
docker run --rm -e OPENAI_API_KEY=... specpylot --target examples/divide.py
```

The container includes all files under `examples/`.

## Associated publication

For more details, please refer to the associated conference paper:

```bibtex
@inproceedings{ayon2026specpylot,
  author    = {Ragib Shahariar Ayon and Shibbir Ahmed},
  title     = {SpecPylot: Python Specification Generation using Large Language Models},
  booktitle = {Proceedings of the 34th ACM Joint European Software Engineering Conference and Symposium on the Foundations of Software Engineering (FSE Companion '26)},
  year      = {2026},
  location  = {Montreal, QC, Canada},
  publisher = {ACM},
  address   = {New York, NY, USA},
  pages     = {1--5},
  doi       = {10.1145/3803437.3806427},
  url       = {https://doi.org/10.1145/3803437.3806427}
}
```
