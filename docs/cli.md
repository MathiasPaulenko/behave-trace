# CLI Reference

## `behave-trace show`

Open the trace viewer in a browser.

```bash
behave-trace show <trace.json> [options]
```

### Options

| Flag           | Default  | Description                                      |
| -------------- | -------- | ------------------------------------------------ |
| `--port`       | `0`      | Port to serve on (0 = auto-select free port).    |
| `--no-browser` | `false`  | Don't open a browser automatically.              |

### Examples

```bash
# Show trace in default browser
behave-trace show trace.json

# Serve on a specific port without opening a browser
behave-trace show trace.json --port 8080 --no-browser
```

!!! note
    If the specified port is already in use, behave-trace prints a clear error
    message instead of hanging. Use `--port 0` (the default) to let the OS
    pick a free port automatically.

## `behave-trace run`

Run Behave with the trace formatter, then open the viewer.

```bash
behave-trace run [features_dir] [options]
```

### Options

| Flag           | Default  | Description                                      |
| -------------- | -------- | ------------------------------------------------ |
| `--port`       | `0`      | Port to serve on (0 = auto-select free port).    |
| `--no-browser` | `false`  | Don't open a browser automatically.              |
| `--tags`       | `None`   | Tag expression to pass to behave (e.g. `@smoke`).|
| `--watch`      | `false`  | Watch for file changes and re-run tests.         |

!!! note
    `--watch` uses [`watchdog`](https://github.com/gorakhargosh/watchdog) when
    available for efficient event-driven notifications. Without `watchdog`,
    it falls back to polling. Install with `pip install behave-trace[watch]`.

### Examples

```bash
# Run behave and open the viewer
behave-trace run features/

# Run with tags and watch mode
behave-trace run features/ --tags @smoke --watch

# Run without opening a browser
behave-trace run features/ --no-browser
```

## `behave-trace --version`

Print the installed version.

```bash
behave-trace --version
```

```text
1.3.0
```

## `python -m behave_trace`

Equivalent to the `behave-trace` CLI entry point.

```bash
python -m behave_trace show trace.json
```

## Behave formatter usage

Behave 1.3.x does not auto-discover formatters via entry points. Register the
formatter in a `behave.ini` (or `behave.cfg`, `setup.cfg`) file in your project
root:

```ini
[behave.formatters]
behave-trace = behave_trace.formatter:TraceFormatter
```

Then use it with Behave's `--format` flag:

```bash
# Write trace to a file
behave --format behave-trace -o trace.json

# Also keep the default pretty output
behave --format pretty --format behave-trace -o trace.json
```

Alternatively, you can use the scoped class name directly without registration:

```bash
behave --format behave_trace.formatter:TraceFormatter -o trace.json
```
