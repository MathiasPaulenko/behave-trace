# Calculator Example

A simple Behave project that demonstrates **behave-trace** with:

- Passing scenarios and one that exercises error handling (division by zero)
- Screenshot attachments (via `attach_screenshot`)
- DOM snapshots (via `attach_dom`)
- Log lines (via `log`)

## Run

The `behave.ini` in this directory registers the formatter:

```ini
[behave.formatters]
behave-trace = behave_trace.formatter:TraceFormatter
```

```bash
# From the repository root, with behave-trace installed:
cd examples/calculator

# Run Behave with behave-trace formatter
behave --format behave-trace -o trace.json

# Open the viewer
behave-trace show trace.json
```

## What to look for in the viewer

- **Timeline**: colored segments per step (green = passed, red = failed)
- **Screenshot tab**: placeholder PNG captured after each operation
- **Snapshot tab**: HTML rendering of the calculator display
- **Console tab**: log lines showing entered values and results
- **Console tab**: on the "Divide by zero" scenario, the error logged via `log()`
  (the `ZeroDivisionError` is caught inside the step, so the scenario passes;
  to see a real failure and the **Error** tab, make an expectation fail)
