# behave-trace

**Trace viewer and step-by-step debugger for Behave BDD.**

behave-trace captures execution data from your [Behave](https://github.com/behave/behave)
test runs — steps, statuses, durations, screenshots, DOM snapshots, and logs —
and visualizes them in a Playwright-inspired web viewer with timeline,
filmstrip, and per-step detail tabs.

---

## Why behave-trace?

When a Behave scenario fails, the console output tells you *what* failed but
not *why*. behave-trace gives you:

- **Visual timeline** — see every step, its duration, and status at a glance.
- **Screenshots** — capture browser state at any point during execution.
- **DOM snapshots** — inspect the HTML before and after each step.
- **Logs** — attach custom log lines to any step for debugging context.
- **Error details** — full traceback and error message per failed step.
- **Zero dependencies** — the viewer uses only Python stdlib (no Flask, no
  Node, no build step).

## Features

- **Two-phase model** (like Playwright Trace Viewer): capture during test run,
  visualize afterwards.
- **TraceFormatter** — a Behave formatter that collects execution events into a
  structured `Trace` data model.
- **Attachment helpers** — `attach_screenshot()`, `attach_dom()`,
  `attach_text()`, `attach_network()`, and `log()` for capturing debugging
  artifacts in `environment.py`.
- **Web viewer** — a dark-themed SPA (Alpine.js) served via a local HTTP
  server, with timeline, filmstrip, and detail tabs.
- **CLI** — `behave-trace show trace.json` opens the viewer in your browser.
  `behave-trace run features/` executes Behave with the formatter and opens
  the viewer, with optional `--watch` mode for automatic re-execution.
- **Fully typed** — `mypy --strict` clean, `py.typed` marker included.
- **Minimal runtime dependencies** — only `behave`.
- **Visual DOM diff** — compare before/after DOM snapshots and see added/removed
  elements highlighted in split, diff, or before/after view modes.
- **Feature tree controls** — collapse/expand all or sort scenarios by name, duration,
  or status.
- **Breadcrumb navigation** — "Feature > Scenario" path in the detail panel.
- **Live progress** — Server-Sent Events stream updates while running Behave from the UI.
- **Persistent UI state** — sort order and viewer toggles saved in `localStorage`.

## Quick example

```bash
# 1. Capture — run Behave with the formatter
behave --format behave-trace -o trace.json

# 2. Visualize — open the viewer
behave-trace show trace.json
```

The viewer opens in your browser at `http://127.0.0.1:<port>` with a
dark-themed SPA showing features, scenarios, steps, screenshots, and errors.

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

1. **Capture** — The `TraceFormatter` hooks into Behave's formatter API and
   collects execution events into a `Trace` data model. Attachments are
   captured via helper functions in `environment.py`.

2. **Visualize** — `behave-trace show` loads the trace JSON, starts a local
   HTTP server (stdlib only), and opens the viewer SPA in a browser.
   Alternatively, `behave-trace run` combines both steps: it executes Behave
   with the formatter and opens the viewer automatically.

## Next steps

- [Installation](installation.md) — get behave-trace running in 30 seconds.
- [Quick Start](quickstart.md) — capture a trace and explore the viewer.
- [CLI](cli.md) — every command, flag, and option.
- [Attachments](attachments.md) — screenshots, DOM snapshots, and logs.
- [Python API](python-api.md) — use behave-trace as a library.
- [Architecture](architecture.md) — internal design and data flow.
- [Changelog](changelog.md) — release history.
- [Contributing](contributing.md) — how to contribute.
