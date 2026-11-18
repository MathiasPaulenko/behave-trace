# Python API

behave-trace can be used as a library for loading, inspecting, and
serializing trace data.

## Public API

```python
import behave_trace
print(behave_trace.__version__)
```

## Attachment helpers

::: behave_trace.attach_screenshot
::: behave_trace.attach_dom
::: behave_trace.attach_text
::: behave_trace.attach_network
::: behave_trace.log

## Trace model

::: behave_trace.models.Trace
::: behave_trace.models.Feature
::: behave_trace.models.Scenario
::: behave_trace.models.Step
::: behave_trace.models.Artifact

## Status and log-level helpers

```python
from behave_trace import STATUS_FAILED, STATUS_PASSED, normalize_status

if step.status == STATUS_FAILED:
    ...
canonical = normalize_status(step.status)  # Behave statuses -> canonical names
```

::: behave_trace.models.STATUS_UNTESTED
::: behave_trace.models.STATUS_RUNNING
::: behave_trace.models.STATUS_PASSED
::: behave_trace.models.STATUS_FAILED
::: behave_trace.models.STATUS_SKIPPED
::: behave_trace.models.STATUS_UNDEFINED
::: behave_trace.models.normalize_status
::: behave_trace.models.normalize_level

## Serializer

::: behave_trace.serializer.Serializer

## Runner

::: behave_trace.runner.BehaveRunner
::: behave_trace.runner.RunResult

## Viewer

::: behave_trace.viewer.server.ViewerServer
::: behave_trace.viewer.browser.open_app
