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

## Serializer

::: behave_trace.serializer.Serializer

## Runner

::: behave_trace.runner.BehaveRunner
::: behave_trace.runner.RunResult

## Viewer

::: behave_trace.viewer.server.ViewerServer
::: behave_trace.viewer.browser.open_app
