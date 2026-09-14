"""
Locust Load Test — Login Endpoint Performance Testing

Defines a Locust user class that simulates login traffic against
the demo application. Used for:
- Performance smoke tests in CI
- Load testing during development
- Regression detection against baselines

Part of the Performance Testing pillar.

Run:
    locust -f performance/locust_login.py --host http://localhost:8000
"""

from locust import HttpUser, task, between


class LoginUser(HttpUser):
    """
    Simulates a user performing login operations.

    Tasks:
    - load_login_page: GET the login page (70% of traffic)
    - attempt_login: POST login credentials (30% of traffic)
    """

    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks

    @task(7)
    def load_login_page(self):
        """Load the login page (simulates page view)."""
        self.client.get("/", name="GET /login")

    @task(3)
    def attempt_login(self):
        """
        Attempt a login via form submission.

        Note: The demo app is client-side only, so this tests
        the static page load. In a real app, this would POST
        to an API endpoint.
        """
        self.client.get(
            "/",
            name="POST /api/login (simulated)",
        )
