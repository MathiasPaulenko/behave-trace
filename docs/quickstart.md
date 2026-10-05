# Quick Start

This guide walks you through capturing a trace and exploring the viewer.

## Capture a trace

From the root of your Behave project (the directory containing `features/`):

```bash
behave --format behave-trace -o trace.json
```

This requires the formatter to be registered first — add a
`[behave.formatters]` section to your `behave.ini` (see
[CLI → Behave formatter usage](cli.md#behave-formatter-usage)) or use the
scoped class name:

```bash
behave --format behave_trace.formatter:TraceFormatter -o trace.json
```

behave-trace will:

1. Collect execution events: features, scenarios, steps, statuses, durations.
2. Capture attachments (screenshots, DOM, logs) from your `environment.py`.
3. Serialize the trace to `trace.json` when the test run completes.

### What you'll see

```text
USING RUNNER: behave.runner:Runner

Trace written to: trace.json
View with: behave-trace show trace.json

1 feature passed, 0 failed, 0 skipped
4 scenarios passed, 0 failed, 0 skipped
20 steps passed, 0 failed, 0 skipped
Took 0min 0.011s
```

## Visualize the trace

```bash
behave-trace show trace.json
```

The viewer opens in your browser at `http://127.0.0.1:<port>` with:

- **Timeline** — colored segments per step (green = passed, red = failed).
- **Filmstrip** — screenshots captured during execution.
- **Detail tabs** — Screenshot, Snapshot (DOM), Source, Console (logs),
  Network, Error, Artifacts.
- **DOM snapshot diff** — switch between before/after, split, and diff views with
  added/removed elements highlighted.
- **Feature tree** — collapse/expand all or sort scenarios by name, duration, or status.
- **Breadcrumb** — "Feature > Scenario" path above the step list; click the feature to
  locate it in the sidebar.
- **Live progress** — updates stream in real time while running Behave from the viewer.
- **Stats** — feature/scenario/step counts, pass/fail breakdown.

### One-step alternative: `behave-trace run`

You can also capture and visualize in a single step:

```bash
behave-trace run features/
```

This runs Behave with the trace formatter, then opens the viewer automatically.
Add `--watch` to re-run on file changes.

## Capture attachments

Add to your `features/environment.py`:

```python
from behave_trace import attach_screenshot, attach_dom, log

def after_step(context, step):
    if step.status == "failed":
        attach_screenshot(context, context.driver, name="failure.png")
        attach_dom(context, context.driver, name="dom.html")
        log(context, f"URL at failure: {context.driver.current_url}")
```

See [Attachments](attachments.md) for the full API.

## Example project

The repository includes a working example at `examples/calculator/`:

```bash
cd examples/calculator
behave --format behave-trace -o trace.json
behave-trace show trace.json
```

The example demonstrates screenshots, DOM snapshots, logs, and an
error-handling scenario (division by zero). To see a failed step, change an
expectation in `calculator.feature` and re-run.

## Next steps

- [CLI](cli.md) — every command, flag, and option.
- [Attachments](attachments.md) — screenshots, DOM snapshots, and logs.
- [Python API](python-api.md) — use behave-trace as a library.
- [Architecture](architecture.md) — internal design and data flow.
- [Contributing](contributing.md) — how to contribute.
