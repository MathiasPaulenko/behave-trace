Feature: Simple test feature for integration tests

  Scenario: A passing scenario
    Given a passing step
    When I do something
    Then I expect success

  Scenario: A failing scenario
    Given a passing step
    When I do something that fails
    Then I expect failure
