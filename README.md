# behave-trace

[![CI](https://github.com/MathiasPaulenko/behave-trace/actions/workflows/ci.yml/badge.svg)](https://github.com/MathiasPaulenko/behave-trace/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/behave-trace.svg)](https://pypi.org/project/behave-trace/)
[![Python versions](https://img.shields.io/pypi/pyversions/behave-trace.svg)](https://pypi.org/project/behave-trace/)
[![License: MIT](https://img.shields.io/pypi/l/behave-trace.svg)](https://github.com/MathiasPaulenko/behave-trace/blob/main/LICENSE)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v0.json)](https://github.com/astral-sh/ruff)

Trace viewer and step-by-step debugger for [Behave](https://github.com/behave/behave) BDD.

Captures execution data (steps, statuses, durations, screenshots, DOM snapshots, logs)
and visualizes them in a Playwright-inspired web viewer with timeline, filmstrip, and
per-step detail tabs.

## Quickstart

```bash
# 1. Install
pip install behave-trace

# 2. Register the formatter — add to behave.ini in your project root:
#    [behave.formatters]
#    behave-trace = behave_trace.formatter:TraceFormatter

# 3. Capture — run Behave with the formatter
behave --format behave-trace -o trace.json

# 4. Visualize — open the viewer
behave-trace show trace.json
```

The viewer opens in your browser at `http://127.0.0.1:<port>` with a dark-themed
SPA showing features, scenarios, steps, screenshots, and errors.

## How it works

```text
┌──────────┐     ┌──────────────┐     ┌───────────┐     ┌──────────────┐
│  Behave  │────▶│  Formatter   │────▶│  Serializer │────▶│  trace.json  │
│  runner  │     │  (collector) │     │  (JSON)    │     │              │
└──────────┘     └──────────────┘     └───────────┘     └──────┬───────┘
                                                            │
                   ┌────────────────────────────────────────┘
                   ▼
            ┌──────────────┐     ┌──────────────────┐
            │  behave-trace │────▶│  Browser SPA     │
            │  show         │     │  (Alpine.js)     │
            │  (HTTP server)│     │  Dark theme      │
            └──────────────┘     └──────────────────┘
```

**Two-phase model** (like Playwright Trace Viewer):

1. **Capture** — The `TraceFormatter` hooks into Behave's formatter API and
   collects execution events into a `Trace` data model. Attachments (screenshots,
   DOM, logs) are captured via `attach_screenshot()`, `attach_dom()`, and `log()`
   helpers in `environment.py`.

2. **Visualize** — `behave-trace show` loads the trace JSON, starts a local HTTP
   server (stdlib only, no dependencies), and opens the viewer SPA in a browser.

## Capturing attachments

Add to your `environment.py`:

```python
from behave_trace import attach_screenshot, attach_dom, attach_text, attach_network, log

def after_step(context, step):
    # Log the current URL after every step
    log(context, f"URL: {context.driver.current_url}")

    if step.status == "failed":
        attach_screenshot(context, context.driver, name="failure.png")
        attach_dom(context, context.driver, name="dom.html")
        log(context, f"Step failed: {step.name}", level="error")
```

The viewer will show screenshots in the filmstrip and detail tabs, with
before/after DOM snapshot toggling. See the
[attachments guide](https://mathiaspaulenko.github.io/behave-trace/attachments/) for the full API.

## CLI

```bash
# Show trace in browser
behave-trace show trace.json

# Show on specific port, don't open browser
behave-trace show trace.json --port 8080 --no-browser

# Run behave with the trace formatter, then open the viewer
behave-trace run features/

# Run with tags and watch mode
behave-trace run features/ --tags @smoke --watch

# Version
behave-trace --version
```

## Development

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Or use the Makefile shortcut
make dev

# Lint
ruff check .
ruff format --check .

# Type check
mypy --strict behave_trace

# Run tests
pytest tests/ -v

# E2E tests (meta: Behave testing Behave)
behave tests/e2e/

# Build
python -m build
```

## Requirements

- Python **3.11+** (tested on 3.11, 3.12, 3.13)
- `behave >= 1.2.6` (installed automatically)
- No other runtime dependencies (viewer uses only Python stdlib)

## Project structure

```text
behave_trace/
    __init__.py          # Public API, formatter registration
    __main__.py          # python -m behave_trace entry point
    formatter.py         # Behave formatter (TraceFormatter)
    collector.py         # Event collector → Trace model
    models.py            # Dataclasses: Trace, Feature, Scenario, Step, etc.
    serializer.py        # JSON load/save
    attach.py            # Attachment helpers (screenshot, DOM, text, network, log)
    runner.py            # Behave runner (subprocess wrapper)
    watcher.py           # File watcher for --watch mode
    utils.py             # Utilities (format_duration, safe_str)
    cli/
        app.py           # argparse CLI with `show` and `run` subcommands
    viewer/
        server.py        # stdlib HTTP server (ThreadingHTTPServer)
        browser.py       # Browser opener (Chrome app mode)
    assets/
        index.html       # SPA shell (Alpine.js from CDN)
        css/viewer.css   # Dark theme styles
        js/viewer.js     # Alpine.js component logic
```

## Documentation

Full documentation is available at
[mathiaspaulenko.github.io/behave-trace](https://mathiaspaulenko.github.io/behave-trace/).

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for setup,
commands, and the release process.

## License

MIT — see [LICENSE](LICENSE).
