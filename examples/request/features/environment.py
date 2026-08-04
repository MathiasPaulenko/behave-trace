"""Environment hooks for the PokeAPI example.

Demonstrates how behave-trace captures network artifacts from
``requests`` library responses.
"""

from behave_trace import log


def before_scenario(context, scenario):
    import requests

    context.session = requests.Session()
    context.base_url = "https://pokeapi.co/api/v2"
    log(context, f"API session created for: {scenario.name}")


def after_scenario(context, scenario):
    session = getattr(context, "session", None)
    if session:
        session.close()
        log(context, "API session closed")


def after_step(context, step):
    log(context, f"Step completed: {step.name}")
    if step.status == "failed":
        log(context, f"Step FAILED: {step.name}", level="error")
