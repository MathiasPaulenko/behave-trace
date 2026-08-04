# Saucedemo Web Example

A real browser automation example using **Selenium WebDriver** against
[saucedemo.com](https://www.saucedemo.com) — a demo e-commerce site by Sauce Labs.

Demonstrates **behave-trace** with:

- Real screenshots from a headless browser
- DOM snapshots of actual web pages
- Log lines for every step
- Passing and failing scenarios with visual evidence

## Requirements

```bash
pip install selenium behave-trace
```

Selenium 4+ manages its own ChromeDriver, so you just need Chrome installed.

## Run

The `behave.ini` in this directory registers the formatter:

```ini
[behave.formatters]
behave-trace = behave_trace.formatter:TraceFormatter
```

```bash
cd examples/web

# Run Behave with behave-trace formatter
behave --format behave-trace -o trace.json

# Open the viewer
behave-trace show trace.json
```

## What to look for in the viewer

- **Timeline**: colored segments per step (green = passed, red = failed)
- **Screenshot tab**: real browser screenshots of login, products, cart, checkout
- **Snapshot tab**: full HTML of the page at each step, with before/after toggling
- **Console tab**: log lines showing navigation, clicks, and form submissions
- **Error tab**: on failure, the exception details with screenshot and DOM captured
