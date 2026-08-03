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
| `--host`       | `127.0.0.1` | Host to bind the HTTP server.                 |

### Examples

```bash
# Show trace in default browser
behave-trace show trace.json

# Serve on a specific port without opening a browser
behave-trace show trace.json --port 8080 --no-browser

# Serve on all interfaces (for remote access)
behave-trace show trace.json --host 0.0.0.0 --port 8080 --no-browser
```

## `behave-trace --version`

Print the installed version.

```bash
behave-trace --version
```

```text
0.1.0
```

## `python -m behave_trace`

Equivalent to the `behave-trace` CLI entry point.

```bash
python -m behave_trace show trace.json
```

## Behave formatter usage

The formatter is registered automatically when `behave_trace` is imported
(via the `.pth` file on installation). Use it with Behave's `--format` flag:

```bash
# Write trace to a file
behave --format behave-trace -o trace.json

# Also keep the default pretty output
behave --format pretty --format behave-trace -o trace.json
```
