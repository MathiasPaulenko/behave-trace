# Installation

## Requirements

- Python **3.11** or newer (tested on 3.11, 3.12, and 3.13)
- `behave >= 1.2.6` (installed automatically as a dependency)

behave-trace has **minimal runtime dependencies** — only `behave`. The viewer
uses only Python stdlib (`http.server`, `json`, `pathlib`). It is pure Python,
fully typed (`mypy --strict` clean), and works on Linux, macOS, and Windows.

### Optional extras

| Extra | Install command | Description |
| ----- | --------------- | ----------- |
| `dev` | `pip install behave-trace[dev]` | pytest, ruff, mypy, build, pre-commit |
| `docs` | `pip install behave-trace[docs]` | mkdocs, mkdocs-material, mkdocstrings |
| `watch` | `pip install behave-trace[watch]` | watchdog for `--watch` mode |

## From PyPI

The recommended way to install behave-trace:

```bash
pip install behave-trace
```

To upgrade:

```bash
pip install --upgrade behave-trace
```

### With pipx (isolated environment)

```bash
pipx install behave-trace
```

### With uv

```bash
uv pip install behave-trace
```

## From source

```bash
git clone https://github.com/MathiasPaulenko/behave-trace.git
cd behave-trace
pip install .
```

## Development install

For contributors who want to run tests, linting, and pre-commit hooks:

```bash
git clone https://github.com/MathiasPaulenko/behave-trace.git
cd behave-trace
pip install -e ".[dev]"
pre-commit install
```

The `[dev]` extra installs `pytest`, `pytest-cov`, `pytest-timeout`, `ruff`,
`mypy`, `build`, and `pre-commit`.

## Verify the installation

```bash
behave-trace --version
```

```text
1.3.0
```

You can also verify the Python API is importable:

```bash
python -c "import behave_trace; print(behave_trace.__version__)"
```

## Uninstall

```bash
pip uninstall behave-trace
```
