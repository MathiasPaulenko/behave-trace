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

The `Collector` maps Behave's runtime objects (features, scenarios,
steps) into behave-trace's own data model (`Trace`, `Feature`, `Scenario`,
`Step`). It also collects attachments from the formatter's attachment queue.

### Models (`models.py`)

Dataclasses representing the trace structure:

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

`Serializer.save(trace, path)` writes the trace to a JSON file.
`Serializer.load(path)` reads it back.

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

- `server.py` — `ThreadingHTTPServer` serving the SPA, a `/api/trace`
  endpoint, `/api/run` and `/api/rerun` for triggering executions, and
  `/api/stream` for Server-Sent Events (live progress). Pre-checks port
  availability before binding to avoid hangs on Windows.
- `browser.py` — Opens the browser in Chrome app mode (borderless window).

### Assets (`assets/`)

- `index.html` — SPA shell loading a vendored Alpine.js bundle (no CDN).
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
Collector (collector.py)
     │
     ▼
Trace model (models.py)
     │
     ▼
Serializer.save() (serializer.py)
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

Behave does not auto-discover formatters via entry points. The formatter is
resolved in one of two ways:

- A `[behave.formatters]` section in the project's `behave.ini` (or
  `behave.cfg`, `setup.cfg`) mapping `behave-trace` to the scoped class name.
- The scoped class name directly: `--format behave_trace.formatter:TraceFormatter`
  (this is what `behave-trace run` uses, so it works without registration).

Additionally, `behave_trace/__init__.py` attempts manual registration with
Behave's internal formatter registry (`behave.formatter._registry.register_as`)
whenever the package is imported.
