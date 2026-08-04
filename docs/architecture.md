# Architecture

## Overview

behave-trace follows a **two-phase model** inspired by Playwright Trace Viewer:

1. **Capture** — A Behave formatter collects execution events into a structured
   data model.
2. **Visualize** — A local HTTP server serves a single-page application that
   renders the trace.

## Components

### Formatter (`formatter.py`)

`TraceFormatter` implements Behave's formatter protocol. It receives events
like `feature(feature)`, `scenario(scenario)`, `step(step)`, and
`eof()` — and delegates to the collector.

### Collector (`collector.py`)

The `TraceCollector` maps Behave's runtime objects (features, scenarios,
steps) into behave-trace's own data model (`Trace`, `Feature`, `Scenario`,
`Step`). It also collects attachments from the formatter's attachment queue.

### Models (`models.py`)

Frozen dataclasses representing the trace structure:

```text
Trace
 └── Feature
      └── Scenario
           └── Step
                └── Artifact (screenshot, DOM)
```

Each model has a `to_dict()` method for JSON serialization and computed
properties (e.g. `has_screenshot`, `passed_steps`, `overall_status`).

### Serializer (`serializer.py`)

`save_trace(trace, path)` writes the trace to a JSON file.
`load_trace(path)` reads it back.

### Attach (`attach.py`)

Helper functions (`attach_screenshot`, `attach_dom`, `attach_text`,
`attach_network`, `log`) that find the active `TraceFormatter` instance and
enqueue artifacts. The formatter picks them up on the next event.

### Runner (`runner.py`)

`BehaveRunner` executes Behave as a subprocess with the trace formatter,
then loads the resulting trace JSON. Used by the `behave-trace run` CLI
subcommand.

### Watcher (`watcher.py`)

`FileWatcher` monitors `.feature` and `.py` files for changes, debounces
events, and triggers a callback. Uses `watchdog` when available, falls back
to polling. Powers the `--watch` mode.

### Viewer (`viewer/`)

- `server.py` — `ThreadingHTTPServer` serving the SPA and a `/api/trace`
  endpoint.
- `browser.py` — Opens the browser in Chrome app mode (borderless window).

### Assets (`assets/`)

- `index.html` — SPA shell loading Alpine.js from CDN.
- `css/viewer.css` — Dark theme styles.
- `js/viewer.js` — Alpine.js component with trace rendering logic.

### CLI (`cli/`)

`app.py` uses `argparse` with two subcommands:

- **`show`** — loads a trace JSON file, starts the HTTP server, and opens
  the browser.
- **`run`** — executes Behave with the trace formatter, loads the result,
  and opens the viewer. Supports `--watch` for automatic re-execution on
  file changes.

## Data flow

```text
Behave runner
     │
     ▼
TraceFormatter (formatter.py)
     │
     ▼
TraceCollector (collector.py)
     │
     ▼
Trace model (models.py)
     │
     ▼
save_trace() (serializer.py)
     │
     ▼
trace.json
     │
     ├──── behave-trace show (cli/app.py)
     │         │
     │         ▼
     │    HTTP server (viewer/server.py)
     │         │
     │         ▼
     │    Browser SPA (assets/index.html)
     │
     └──── behave-trace run (cli/app.py)
               │
               ▼
          BehaveRunner (runner.py)
               │
               ▼
          trace.json → HTTP server → Browser SPA
```

## Formatter registration

The formatter is registered via the `behave.formatters` entry point in
`pyproject.toml`. Additionally, `behave_trace/__init__.py` attempts manual
registration with Behave's internal formatter registry for compatibility
with Behave 1.3.x, which does not auto-discover entry points.
