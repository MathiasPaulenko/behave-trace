# behave-trace

Trace viewer and step-by-step debugger for [Behave](https://github.com/behave/behave) BDD.

Captures execution data (steps, statuses, durations, screenshots, DOM snapshots, logs)
and visualizes them in a Playwright-inspired web viewer with timeline, filmstrip, and
per-step detail tabs.

## Quickstart

```bash
# 1. Install
pip install behave-trace

# 2. Capture — run Behave with the formatter
behave --format behave-trace -o trace.json

# 3. Visualize — open the viewer
behave-trace show trace.json
```

The viewer opens in your browser at `http://127.0.0.1:<port>` with a dark-themed
SPA showing features, scenarios, steps, screenshots, and errors.

<!-- TODO: add screenshots -->

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
from behave_trace import attach_screenshot, attach_dom, log

def after_step(context, step):
    if step.status == "failed":
        attach_screenshot(context, context.driver, name="failure.png")
        attach_dom(context, context.driver, name="dom.html")
        log(context, f"URL at failure: {context.driver.current_url}")
```

The viewer will show screenshots in the filmstrip and detail tabs, with
before/after DOM snapshot toggling.

## CLI

```bash
# Show trace in browser
behave-trace show trace.json

# Show on specific port, don't open browser
behave-trace show trace.json --port 8080 --no-browser

# Version
behave-trace --version
```

## Development

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Lint
ruff check behave_trace/ tests/
ruff format --check behave_trace/ tests/

# Type check
mypy behave_trace/

# Unit + integration tests
pytest tests/ -v

# E2E tests (meta: Behave testing Behave)
behave tests/e2e/

# Build
python -m build
```

## Project structure

```text
behave_trace/
    __init__.py          # Public API, formatter registration
    __main__.py          # python -m behave_trace entry point
    formatter.py         # Behave formatter (TraceFormatter)
    collector.py         # Event collector → Trace model
    models.py            # Dataclasses: Trace, Feature, Scenario, Step, etc.
    serializer.py        # JSON load/save
    attach.py            # Attachment helpers (screenshot, DOM, log)
    utils.py             # Utilities (format_duration, safe_str)
    cli/
        app.py           # argparse CLI with `show` subcommand
    viewer/
        server.py        # stdlib HTTP server (ThreadingHTTPServer)
        browser.py       # Browser opener (Chrome app mode)
    assets/
        index.html       # SPA shell (Alpine.js from CDN)
        css/viewer.css   # Dark theme styles
        js/viewer.js     # Alpine.js component logic
```

## License

MIT — see [LICENSE](LICENSE).
