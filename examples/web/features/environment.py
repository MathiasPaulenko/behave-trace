"""Environment hooks for the saucedemo web example.

Sets up Selenium WebDriver before each scenario, tears it down after.
Captures screenshots, DOM snapshots, and logs via behave-trace attachments.
"""

from __future__ import annotations

from behave_trace import attach_dom, attach_screenshot, log


def before_scenario(context, scenario):
    """Launch a fresh browser for each scenario."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,800")

    context.driver = webdriver.Chrome(options=opts)
    context.driver.implicitly_wait(3)
    log(context, f"Browser launched for scenario: {scenario.name}")


def after_scenario(context, scenario):
    """Close browser."""
    if hasattr(context, "driver"):
        context.driver.quit()


def after_step(context, step):
    """Capture attachments after every step."""
    if not hasattr(context, "driver"):
        return

    log(context, f"Step completed: {step.name}")

    if step.status == "failed":
        attach_screenshot(context, context.driver, name="failure.png")
        attach_dom(context, context.driver, name="failure_dom.html")
        log(context, f"Step FAILED: {step.name}", level="error")
