Feature: Saucedemo Shopping Flow
  As a shopper
  I want to browse and purchase products on saucedemo.com
  So that I can complete a purchase end-to-end

  Scenario: Login and add item to cart
    Given I am on the saucedemo login page
    When I log in as "standard_user" with password "secret_sauce"
    Then I should see the products page
    When I add the first product to the cart
    Then the cart badge should show "1" item
    And I take a screenshot of the products page

  Scenario: Complete checkout flow
    Given I am on the saucedemo login page
    When I log in as "standard_user" with password "secret_sauce"
    And I add the first product to the cart
    And I go to the cart
    And I proceed to checkout
    And I fill in checkout info with first name "John" last name "Doe" and zip "12345"
    And I continue to the overview
    Then I should see the checkout overview
    When I finish the order
    Then I should see the order confirmation
