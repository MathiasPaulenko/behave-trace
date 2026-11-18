# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- `TraceFormatter.close()` now flushes the open scenario/feature lifecycle
  when Behave aborts mid-suite without calling `eof()` — interrupted runs no
  longer leave the last feature `untested` with missing steps.
- POST requests with `Transfer-Encoding: chunked` are rejected with 411 —
  the undecoded body would otherwise poison the next request on the same
  keep-alive connection.
- `FileWatcher.start()` now falls back to polling on any watchdog startup
  failure — on Windows a missing directory raised `queue.Empty` instead of
  `OSError` and crashed the watcher.
- `Serializer.save()` retries `os.replace` briefly when Windows file
  indexing or antivirus transiently denies the rename.

## 1.4.1 — 2026-11-18

### Fixed

- Behave statuses outside the canonical set (`error`, `hook_error`,
  `cleanup_error`, `pending`, `executing`, `untested_undefined`, ...) no longer
  collapse into `untested`: errors map to `failed`, `executing` to `running`.
- Steps that Behave marks `skipped` without emitting a `result()` event
  (everything after a failed step) are now flushed into the trace at scenario
  end instead of silently disappearing.
- Duplicate `result()` events for the same step object are deduplicated, and
  per-scenario step state resets between scenarios.
- `Trace.overall_status` reports `running` while any feature is still running
  (running now outranks `passed` for mid-run traces).
- Git remote URLs with embedded credentials (`https://user:token@host/...`)
  are sanitized before being stored in trace environment info.
- File changes that arrive while a UI-triggered re-run is executing are no
  longer dropped: the rerun callback drains the pending-run queue and runs
  once more, matching watch-mode behavior.
- `Serializer.save` writes atomically via a unique temp file + rename, and
  concurrent saves to the same path are serialized (fixes a Windows
  `os.replace` race).
- `attach_network` now parses Selenium CDP performance log entries
  (`driver.get_log("performance")`), extracting the `Network.*` event from the
  nested `message` JSON.
- `format_duration` no longer raises on non-numeric input; it returns `"0ms"`.
- Search highlighting no longer corrupts escaped HTML entities (`&amp;`,
  `&lt;`) when the query matches inside them — marking happens on raw text
  before escaping.
- The viewer now reacts to `scenario_started` SSE events, so the progress
  total updates live instead of only when scenarios complete.
- The `/api/progress` endpoint whitelists SSE event types and clamps negative
  counters.
- Watchdog moves and deletions now trigger re-runs (editors that save via
  rename were ignored), and the polling fallback detects deletions.

### Changed

- `behave-trace run` writes its trace to a per-process temp file
  (`behave-trace-<pid>.json`) instead of a fixed name — no stale traces or
  collisions between concurrent instances.
- `/api/rerun` validates the payload (`filter` enum, non-empty scenario list)
  and returns 400 on misuse instead of running everything.
- POST endpoints check the `Origin` header (localhost only), request bodies
  are size-capped, and `/api/source` enforces an extension allowlist and a
  file size limit.
- Scenario names passed to behave's `--name` are now regex-escaped *and*
  anchored, so "Foo" no longer also matches "Foo bar".
- Exported `STATUS_*` constants, `ALL_STATUSES` and `normalize_status` from
  the package root, matching the already-public `normalize_level`.

## 1.4.0 — 2026-10-05

### Fixed

- `behave-trace run` now uses the scoped formatter class name
  (`behave_trace.formatter:TraceFormatter`), so it works on projects without a
  `[behave.formatters]` registration in `behave.ini`.
- Toggling auto-run during a test run no longer clears the "Running" indicator
  in the viewer (the `state` SSE event now includes the `running` flag).
- Background steps duplicated in `scenario.background` now reflect real
  execution results instead of staying `untested`, and each scenario gets its
  own copy.
- Scenario names passed to `--name` are regex-escaped, so "Re-run failed" and
  "Run selected" work with names containing metacharacters.
- `attach_dom` no longer injects `<base>` before the `<!DOCTYPE>` declaration.
- `attach_screenshot` detects the real MIME type (PNG/JPEG/GIF/WebP) instead of
  always reporting `image/png`.
- The viewer's snapshot diff now bails out on very large snapshots instead of
  freezing the tab (LCS matrix is O(m×n)).
- `formatDuration` in the viewer handles durations ≥ 1 hour.
- Attachments or log lines produced in `after_scenario` no longer leak into the
  next scenario's first step.

### Changed

- Alpine.js is now vendored locally (`assets/js/vendor/`) instead of loaded
  from a CDN — the viewer works offline and without unpinned dependencies.
- Removed the dead `[project.entry-points."behave.formatters"]` section;
  Behave does not discover entry points.
- Added missing CSS classes for `untested`/`running`/`info` states.

## 1.3.1 — 2026-08-06

### Fixed

- Unified author email in package metadata.
- Updated version test for v1.3.1.

## 1.3.0 — 2026-08-05

### Added

- **Port conflict detection**: pre-check port availability before binding the server, raising a clear error instead of hanging on Windows.
- Improved serializer with better error handling and edge-case coverage.
- Enhanced collector with more robust attachment and log flushing.
- Additional test coverage for server API, CLI integration, attachments, and edge cases.

### Fixed

- **Windows port hang**: `ThreadingHTTPServer` could block indefinitely when the port was already in use. Now detected upfront with a `connect_ex` probe.
- Minor fixes in formatter, runner, and watcher for robustness.

### Changed

- Viewer JS improvements for smoother UI interactions.
- CLI app refinements for better error reporting.

## 1.2.1 — 2026-08-04

### Fixed

- `ruff format` issues in `behave_trace/collector.py` and `behave_trace/viewer/server.py`.
- `tests/test_cli.py::TestRunExceptionSafety` now avoids hanging on `signal.pause()` on Linux.

## 1.2.0 — 2026-08-04

### Added

- **Live progress** updates via Server-Sent Events while running Behave from the viewer.
- **Visual DOM diff** with before/after snapshots and highlighted added/removed elements.
- **Collapse/Expand all** buttons for the feature tree.
- **Scenario sorting** by name, duration, or status with persistence in `localStorage`.
- **Feature → Scenario breadcrumb** with clickable feature in the detail panel.
- Filter counters, timeline hover preview, and other UI polish.

## 1.0.0 — 2025-08-03

### Added

- **Trace formatter** (`behave_trace.formatter:TraceFormatter`) — captures Behave
  execution events (features, scenarios, steps, statuses, durations, errors) into
  a structured `Trace` model.
- **Collector** (`Collector`) — accumulates events from Behave's formatter API
  into `Trace`, `Feature`, `Scenario`, `Step` dataclasses with computed stats.
- **Serializer** (`Serializer`) — JSON serialization/deserialization for trace
  files with full round-trip fidelity.
- **Attachment API** (`attach_screenshot`, `attach_dom`, `attach_text`,
  `attach_network`, `log`) — high-level helpers for capturing screenshots,
  DOM snapshots, text snippets, network requests, and log lines from
  `environment.py` hooks.
- **CLI** (`behave-trace`) — `show` subcommand that loads a trace file, starts
  a local HTTP server, and opens the viewer in a browser (Chrome app mode
  preferred, falls back to default browser). `run` subcommand that executes
  Behave with the trace formatter and opens the viewer, with optional
  `--watch` mode for automatic re-execution on file changes.
- **Viewer server** (`ViewerServer`) — stdlib-only `ThreadingHTTPServer` serving
  static assets and `/api/trace` endpoint with gzip compression and path
  traversal protection.
- **Viewer frontend** — single-page application with Alpine.js (CDN, no build
  step), dark theme, Playwright-inspired layout:
  - Header with status badges and duration
  - Sidebar with filters (all / failed / slow), scenario tree, and stats
  - Timeline with colored segments and scrubable cursor
  - Step list with status icons, keywords, durations, and mini-badges
  - Step detail with tabs: Screenshot, Snapshot (before/after), Source,
    Console, Error, Artifacts
  - Filmstrip with screenshot thumbnails
  - Empty state
- **Example project** (`examples/calculator/`) — a real Behave project
  demonstrating screenshots, DOM snapshots, logs, and a failing scenario.
- **E2E tests** — meta Behave suite that runs Behave with `behave-trace`
  formatter on inner test features and verifies the trace JSON structure,
  statuses, artifacts, stats, and environment capture.
- **Unit tests** — 288 tests covering models, collector, formatter, serializer,
  attach API, CLI, server, and utils.
- **CI/CD** — GitHub Actions workflows for lint (ruff), typecheck (mypy),
  test (pytest with coverage + codecov) on Python 3.11-3.13 across
  Ubuntu/Windows/macOS, automated release to PyPI via Trusted Publishing,
  and MkDocs documentation deployment to GitHub Pages.
- **Documentation** — MkDocs Material site with installation, quickstart,
  CLI reference, attachments guide, Python API (mkdocstrings), architecture,
  and contributing guide.
- **Community files** — CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md,
  PR/issue templates, dependabot configuration.
- **Developer tooling** — Makefile, pre-commit hooks, .editorconfig,
  .markdownlint.json, py.typed marker.
