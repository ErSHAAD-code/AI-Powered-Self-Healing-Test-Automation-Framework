@smoke
Feature: Login Functionality
  As a QA engineer, I want to verify the login functionality
  so that I can ensure users can authenticate correctly.

  Background:
    Given the user is on the login page

  @smoke
  Scenario: Successful login with valid credentials
    When the user enters username "admin"
    And the user enters password "admin123"
    And the user clicks the login button
    Then the dashboard should be visible
    And the welcome message should contain "admin"

  @smoke
  Scenario: Failed login with invalid credentials
    When the user enters username "invalid_user"
    And the user enters password "wrong_password"
    And the user clicks the login button
    Then the error message should be visible
    And the error message should contain "Invalid"

  @regression
  Scenario Outline: Data-driven login tests
    When the user enters username "<username>"
    And the user enters password "<password>"
    And the user clicks the login button
    Then the dashboard should be visible
    And the displayed username should be "<username>"

    Examples:
      | username    | password     |
      | admin       | admin123     |
      | testuser    | password     |
      | qe_engineer | quality2024  |

  @regression
  Scenario: Logout returns to login page
    When the user enters username "admin"
    And the user enters password "admin123"
    And the user clicks the login button
    And the user clicks the logout button
    Then the login form should be visible
    And the dashboard should not be visible
