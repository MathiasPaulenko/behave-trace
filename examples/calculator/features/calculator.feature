Feature: Calculator
  As a user
  I want to use a calculator
  So that I can perform arithmetic operations

  Background:
    Given a calculator

  Scenario: Add two numbers
    Given I enter 5 into the calculator
    And I enter 3 into the calculator
    When I press add
    Then the result should be 8

  Scenario: Subtract two numbers
    Given I enter 10 into the calculator
    And I enter 4 into the calculator
    When I press subtract
    Then the result should be 6

  Scenario: Divide by zero fails
    Given I enter 10 into the calculator
    And I enter 0 into the calculator
    When I press divide
    Then the calculator should show an error

  Scenario: Multiply two numbers
    Given I enter 7 into the calculator
    And I enter 6 into the calculator
    When I press multiply
    Then the result should be 42
