# Attachments

behave-trace can capture debugging artifacts during test execution: screenshots,
DOM snapshots, and log lines. These are attached to individual steps and
displayed in the viewer's detail tabs.

## Attachment helpers

Import from `behave_trace` in your `environment.py`:

```python
from behave_trace import attach_screenshot, attach_dom, attach_text, attach_network, log
```

### `attach_screenshot(context, data, name)`

Attach a screenshot to the current step.

| Parameter  | Type             | Description                                  |
| ---------- | ---------------- | -------------------------------------------- |
| `context`  | `RuleContext`    | Behave's context object.                     |
| `data`     | `bytes`          | Screenshot data (PNG, JPEG, etc.).           |
| `name`     | `str`            | Filename for the screenshot (e.g. `"after_click.png"`). |

```python
def after_step(context, step):
    attach_screenshot(context, context.driver.get_screenshot_as_png(), name="step.png")
```

The viewer displays screenshots in the filmstrip and the Screenshots tab.

### `attach_dom(context, html, name)`

Attach a DOM snapshot (HTML) to the current step.

| Parameter  | Type             | Description                                  |
| ---------- | ---------------- | -------------------------------------------- |
| `context`  | `RuleContext`    | Behave's context object.                     |
| `html`     | `str`            | HTML content of the DOM snapshot.            |
| `name`     | `str`            | Filename (e.g. `"dom.html"`).                |

```python
def after_step(context, step):
    attach_dom(context, context.driver.page_source, name="dom.html")
```

The viewer renders the HTML in the Snapshot tab with before/after toggling.

### `attach_text(context, text, name)`

Attach a plain text snippet to the current step.

| Parameter  | Type             | Description                                  |
| ---------- | ---------------- | -------------------------------------------- |
| `context`  | `RuleContext`    | Behave's context object.                     |
| `text`     | `str`            | Text content to attach.                      |
| `name`     | `str`            | Filename (e.g. `"note.txt"`).                |

```python
def after_step(context, step):
    attach_text(context, f"Step {step.name} completed", name="note.txt")
```

### `attach_network(context, request_data, name)`

Attach an HTTP request/response as a network artifact to the current step.

| Parameter      | Type             | Description                                  |
| -------------- | ---------------- | -------------------------------------------- |
| `context`      | `RuleContext`    | Behave's context object.                     |
| `request_data` | `Any`            | Dict, Playwright Request/Response, or Selenium log entry. |
| `name`         | `str`            | Artifact name (default: `"network"`).        |

```python
def after_step(context, step):
    attach_network(context, context.response, name="api_call")
```

### `log(context, message, level)`

Attach a log line to the current step.

| Parameter  | Type             | Description                                  |
| ---------- | ---------------- | -------------------------------------------- |
| `context`  | `RuleContext`    | Behave's context object.                     |
| `message`  | `str`            | Log message text.                            |
| `level`    | `str`            | Log level: `"info"`, `"warning"`, or `"error"` (default: `"info"`). |

```python
def after_step(context, step):
    log(context, f"Current URL: {context.driver.current_url}")
```

The viewer shows log lines in the Console tab.

## Typical usage

```python
# features/environment.py
from behave_trace import attach_screenshot, attach_dom, attach_text, log

def after_step(context, step):
    # Always log the current URL
    log(context, f"URL: {context.driver.current_url}")

    # Capture screenshot after every step
    attach_screenshot(context, context.driver.get_screenshot_as_png(), name=f"{step.name}.png")

    # On failure, also capture DOM and error context
    if step.status == "failed":
        attach_dom(context, context.driver.page_source, name="failure_dom.html")
        attach_text(context, str(step.error), name="error.txt")
        log(context, f"Step failed: {step.name}", level="error")
```

## How attachments work

Attachments are stored as `Artifact` objects in the trace model:

```python
@dataclass(slots=True)
class Artifact:
    type: str           # "screenshot", "dom", "text", "network", or "log"
    name: str           # filename
    mime_type: str      # e.g. "image/png", "text/html"
    data_base64: str    # base64-encoded data
    text: str | None    # text content (for DOM/text/network artifacts)
```

The formatter collects artifacts during execution and serializes them into
the trace JSON. The viewer decodes base64 data for display.
