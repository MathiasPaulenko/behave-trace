"""Step definitions for the saucedemo web example.

Automates https://www.saucedemo.com using Selenium WebDriver.
Demonstrates behave-trace attachments: screenshots, DOM snapshots, and logs.
"""

from __future__ import annotations

from behave import given, then, when  # type: ignore[import-not-found]
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC  # noqa: N812
from selenium.webdriver.support.ui import WebDriverWait

from behave_trace import attach_dom, attach_screenshot, log

BASE_URL = "https://www.saucedemo.com"


@given("I am on the saucedemo login page")
def step_on_login_page(context):
    context.driver.get(BASE_URL)
    WebDriverWait(context.driver, 5).until(EC.presence_of_element_located((By.ID, "login-button")))
    log(context, f"Navigated to {BASE_URL}")
    attach_screenshot(context, context.driver, name="login_page.png")


@when('I log in as "{username}" with password "{password}"')
def step_login(context, username, password):
    context.driver.find_element(By.ID, "user-name").send_keys(username)
    context.driver.find_element(By.ID, "password").send_keys(password)
    context.driver.find_element(By.ID, "login-button").click()
    log(context, f"Logged in as {username}")


@then("I should see the products page")
def step_see_products(context):
    WebDriverWait(context.driver, 5).until(
        EC.presence_of_element_located((By.CLASS_NAME, "inventory_list"))
    )
    title = context.driver.find_element(By.CLASS_NAME, "title").text
    assert "Products" in title, f"Expected Products page, got: {title}"
    log(context, f"Products page loaded: {title}")
    attach_screenshot(context, context.driver, name="products_page.png")
    attach_dom(context, context.driver, name="products_dom.html")


@when("I add the first product to the cart")
def step_add_first_product(context):
    add_buttons = context.driver.find_elements(By.CSS_SELECTOR, "button[data-test^='add-to-cart']")
    assert add_buttons, "No add-to-cart buttons found"
    add_buttons[0].click()
    product_name = context.driver.find_element(By.CSS_SELECTOR, ".inventory_item_name").text
    context.added_product = product_name
    log(context, f"Added product: {product_name}")
    attach_screenshot(context, context.driver, name="item_added.png")


@then('the cart badge should show "{count}" item')
def step_cart_badge(context, count):
    badge = context.driver.find_element(By.CLASS_NAME, "shopping_cart_badge")
    assert badge.text == count, f"Expected cart badge '{count}', got '{badge.text}'"
    log(context, f"Cart badge shows: {badge.text}")


@when("I go to the cart")
def step_go_to_cart(context):
    context.driver.find_element(By.CLASS_NAME, "shopping_cart_link").click()
    WebDriverWait(context.driver, 5).until(
        EC.presence_of_element_located((By.CLASS_NAME, "cart_list"))
    )
    log(context, "Navigated to cart")
    attach_screenshot(context, context.driver, name="cart.png")


@when("I proceed to checkout")
def step_proceed_to_checkout(context):
    context.driver.find_element(By.ID, "checkout").click()
    WebDriverWait(context.driver, 5).until(EC.presence_of_element_located((By.ID, "first-name")))
    log(context, "On checkout form")


@when('I fill in checkout info with first name "{first}" last name "{last}" and zip "{zip}"')
def step_fill_checkout(context, first, last, zip):
    context.driver.find_element(By.ID, "first-name").send_keys(first)
    context.driver.find_element(By.ID, "last-name").send_keys(last)
    context.driver.find_element(By.ID, "postal-code").send_keys(zip)
    context.driver.find_element(By.ID, "continue").click()
    log(context, f"Checkout info submitted: {first} {last}, {zip}")


@when("I continue to the overview")
def step_continue_to_overview(context):
    WebDriverWait(context.driver, 5).until(
        EC.presence_of_element_located((By.CLASS_NAME, "checkout_summary_container"))
    )
    log(context, "On checkout overview")


@then("I should see the checkout overview")
def step_see_overview(context):
    summary = context.driver.find_element(By.CLASS_NAME, "checkout_summary_container")
    assert summary.is_displayed(), "Checkout overview not visible"
    log(context, "Checkout overview visible")
    attach_screenshot(context, context.driver, name="checkout_overview.png")
    attach_dom(context, context.driver, name="overview_dom.html")


@when("I finish the order")
def step_finish_order(context):
    context.driver.find_element(By.ID, "finish").click()
    log(context, "Clicked finish")


@then("I should see the order confirmation")
def step_order_confirmation(context):
    WebDriverWait(context.driver, 5).until(
        EC.presence_of_element_located((By.CLASS_NAME, "checkout_complete_container"))
    )
    header = context.driver.find_element(By.CSS_SELECTOR, ".checkout_complete_container h2").text
    assert "Thank you" in header, f"Expected order confirmation, got: {header}"
    log(context, f"Order confirmed: {header}")
    attach_screenshot(context, context.driver, name="order_complete.png")
    attach_dom(context, context.driver, name="confirmation_dom.html")


@then("I take a screenshot of the products page")
def step_screenshot_products(context):
    attach_screenshot(context, context.driver, name="products_screenshot.png")
    attach_dom(context, context.driver, name="products_snapshot.html")
    log(context, "Screenshot and DOM snapshot captured")
