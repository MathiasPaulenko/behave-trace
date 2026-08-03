Feature: behave-trace captures execution correctly

  Scenario: A passing step is recorded
    Given a simple passing step
    When the step executes
    Then the trace should contain the step with status "passed"

  Scenario: A failing step is recorded
    Given a simple failing step
    When the step executes and fails
    Then the trace should contain the step with status "failed"

  Scenario: Attachments are captured
    Given a step with a screenshot attachment
    When the step executes
    Then the trace should contain an artifact of type "screenshot"

  Scenario: Stats are calculated correctly
    Given a feature with 3 scenarios
    When the trace is generated
    Then the trace stats should show 3 scenarios
    And the trace stats should show at least 9 steps

  Scenario: Environment is captured
    Given a simple passing step
    When the step executes
    Then the trace should contain environment info with python_version
    And the trace should contain environment info with platform
