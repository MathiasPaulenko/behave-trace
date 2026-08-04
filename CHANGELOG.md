# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
