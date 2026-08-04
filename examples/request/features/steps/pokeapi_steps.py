"""Step definitions for PokeAPI example.

Each step that makes an HTTP call attaches the request/response as a
network artifact so it appears in the behave-trace viewer's Network tab.
"""

import json

from behave import given, then, when
from behave_trace import attach_network, attach_text, log


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _attach_response(context, response, name="response"):
    """Attach a requests.Response as a network artifact."""
    try:
        body = response.json()
    except Exception:
        body = response.text

    attach_network(
        context,
        {
            "method": response.request.method if response.request else "GET",
            "url": response.url,
            "status": response.status_code,
            "headers": dict(response.headers),
            "body": response.request.body if response.request else None,
            "response": body,
        },
        name=name,
    )


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------

@given("I have a PokeAPI client")
def step_have_client(context):
    assert context.session is not None, "API session not initialized"
    log(context, f"Client ready, base URL: {context.base_url}")


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------

@when('I request pokemon "{name}"')
def step_request_pokemon(context, name):
    url = f"{context.base_url}/pokemon/{name}"
    log(context, f"GET {url}")
    context.response = context.session.get(url, timeout=10)
    _attach_response(context, context.response, name=f"pokemon_{name}.json")


@when("I request the pokemon list with limit {limit:d}")
def step_request_list(context, limit):
    url = f"{context.base_url}/pokemon?limit={limit}"
    log(context, f"GET {url}")
    context.response = context.session.get(url, timeout=10)
    _attach_response(context, context.response, name="pokemon_list.json")


@when('I request ability "{name}"')
def step_request_ability(context, name):
    url = f"{context.base_url}/ability/{name}"
    log(context, f"GET {url}")
    context.response = context.session.get(url, timeout=10)
    _attach_response(context, context.response, name=f"ability_{name}.json")


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------

@then("the response status should be {status:d}")
def step_check_status(context, status):
    actual = context.response.status_code
    assert actual == status, f"Expected {status}, got {actual}"
    log(context, f"Status {actual} OK")


@then('the pokemon name should be "{name}"')
def step_check_name(context, name):
    data = context.response.json()
    actual = data.get("name", "")
    assert actual == name, f"Expected '{name}', got '{actual}'"
    log(context, f"Pokemon name: {actual}")
    attach_text(context, json.dumps(data, indent=2), name="pokemon_data.json")


@then("the pokemon should have an id greater than 0")
def step_check_id(context):
    data = context.response.json()
    pokemon_id = data.get("id", 0)
    assert pokemon_id > 0, f"Expected id > 0, got {pokemon_id}"
    log(context, f"Pokemon id: {pokemon_id}")


@then("the response should contain an error message")
def step_check_error(context):
    log(context, f"Response body: {context.response.text[:200]}")
    assert context.response.status_code == 404
    log(context, "404 error confirmed")


@then("the list should contain {count:d} pokemon")
def step_check_list_count(context, count):
    data = context.response.json()
    results = data.get("results", [])
    actual = len(results)
    assert actual == count, f"Expected {count} items, got {actual}"
    names = [r["name"] for r in results]
    log(context, f"Pokemon list: {', '.join(names)}")
    attach_text(context, json.dumps(names, indent=2), name="pokemon_names.json")


@then('the ability name should be "{name}"')
def step_check_ability_name(context, name):
    data = context.response.json()
    actual = data.get("name", "")
    assert actual == name, f"Expected '{name}', got '{actual}'"
    log(context, f"Ability name: {actual}")


@then("the ability should have effect entries")
def step_check_effect_entries(context):
    data = context.response.json()
    entries = data.get("effect_entries", [])
    assert len(entries) > 0, "No effect entries found"
    log(context, f"Found {len(entries)} effect entries")
    attach_text(
        context,
        json.dumps(entries, indent=2),
        name="effect_entries.json",
    )
