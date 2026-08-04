Feature: PokeAPI exploration
  As a developer testing REST APIs
  I want to query the PokeAPI
  So that I can verify behave-trace captures network artifacts

  Scenario: Fetch a known Pokemon
    Given I have a PokeAPI client
    When I request pokemon "pikachu"
    Then the response status should be 200
    And the pokemon name should be "pikachu"
    And the pokemon should have an id greater than 0

  Scenario: Search for a non-existent Pokemon
    Given I have a PokeAPI client
    When I request pokemon "agumon"
    Then the response status should be 404
    And the response should contain an error message

  Scenario: List first generation Pokemon
    Given I have a PokeAPI client
    When I request the pokemon list with limit 5
    Then the response status should be 200
    And the list should contain 5 pokemon

  Scenario: Fetch ability details
    Given I have a PokeAPI client
    When I request ability "static"
    Then the response status should be 200
    And the ability name should be "static"
    And the ability should have effect entries
