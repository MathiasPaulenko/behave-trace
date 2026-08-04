# behave-trace API Example — PokeAPI

This example demonstrates **behave-trace** with REST API testing using the
[`requests`](https://docs.python-requests.org/) library against the public
[PokeAPI](https://pokeapi.co/).

## What it shows

- **Network artifacts** — each HTTP request/response is captured and shown in
  the viewer's **Network** tab (method, URL, status, headers, body, response).
- **Text artifacts** — JSON response bodies are attached as text for easy
  inspection in the **Artifacts** tab.
- **Logs** — every step logs contextual messages visible in the **Console** tab.

## Requirements

```bash
pip install requests behave behave-trace
```

## Run

```bash
cd examples/request
behave --format behave-trace -o trace.json
```

## View the trace

```bash
behave-trace show trace.json
```

Then open the URL shown in your browser. Select a scenario, click a step, and
switch to the **Network** tab to inspect the HTTP request and response.

## Scenarios

| Scenario | Description |
| --- | --- |
| Fetch a known Pokemon | GET `/pokemon/pikachu` — verifies 200, name, id |
| Search for a non-existent Pokemon | GET `/pokemon/agumon` — verifies 404 |
| List first generation Pokemon | GET `/pokemon?limit=5` — verifies list count |
| Fetch ability details | GET `/ability/static` — verifies ability data |
