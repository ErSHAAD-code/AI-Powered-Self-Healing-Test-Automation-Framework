#!/usr/bin/env python3
"""
run_demo.py — End-to-End Self-Healing Demonstration

This script demonstrates the complete AI-augmented self-healing pipeline:

1. Starts a local HTTP server serving the demo application
2. Runs a Playwright test with CORRECT locators → PASS
3. Programmatically MUTATES the demo app's DOM (simulates UI refactoring)
4. Runs the SAME test with now-BROKEN locators → triggers healing pipeline
5. Shows the healing result: original → healed locator, confidence, reasoning
6. Generates and opens the healing HTML report

Run:
    python run_demo.py

This script requires NO API keys — it uses the MockProvider by default.
Set ANTHROPIC_API_KEY or GOOGLE_API_KEY in .env for real LLM healing.
"""

import os
import sys
import time
import json
import logging
import threading
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from functools import partial

# Force UTF-8 stdout on Windows to avoid cp1252 encoding errors
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from playwright.sync_api import sync_playwright

from core.smart_element import SmartElement, get_healing_events, clear_healing_events
from ai_core.locator_healing.healing_engine import HealingEngine
from ai_core.locator_healing.confidence_gate import HealingDecision
from reporting.healing_report_generator import HealingReportGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("demo")


# =============================================================================
# Terminal Colors
# =============================================================================

class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def print_banner(text: str, color: str = Colors.CYAN):
    """Print a formatted banner."""
    line = "=" * 70
    print(f"\n{color}{Colors.BOLD}{line}")
    print(f"  {text}")
    print(f"{line}{Colors.RESET}\n")


def print_step(step: int, text: str):
    """Print a numbered step."""
    print(f"{Colors.BLUE}{Colors.BOLD}[Step {step}]{Colors.RESET} {text}")


def print_success(text: str):
    print(f"{Colors.GREEN}  [OK] {text}{Colors.RESET}")


def print_warning(text: str):
    print(f"{Colors.YELLOW}  [!!] {text}{Colors.RESET}")


def print_error(text: str):
    print(f"{Colors.RED}  [FAIL] {text}{Colors.RESET}")


def print_info(text: str):
    print(f"{Colors.DIM}  [i] {text}{Colors.RESET}")


# =============================================================================
# Demo Server
# =============================================================================

class QuietHTTPHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def start_server(port: int = 8000) -> HTTPServer:
    """Start the demo app HTTP server."""
    demo_dir = str(PROJECT_ROOT / "demo_app")
    handler = partial(QuietHTTPHandler, directory=demo_dir)
    server = HTTPServer(("localhost", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# =============================================================================
# DOM Mutation Script (injected into the browser)
# =============================================================================

MUTATION_SCRIPT = """
() => {
    // Simulate a UI refactoring by changing element IDs and classes
    // This is exactly what breaks locators in real-world projects

    const mutations = [];

    // 1. Change the login button ID
    const loginBtn = document.getElementById('login-button');
    if (loginBtn) {
        loginBtn.id = 'btn-signin-primary';
        loginBtn.className = 'signin-btn-redesigned';
        mutations.push('login-button → btn-signin-primary');
    }

    // 2. Change the username input ID
    const usernameInput = document.getElementById('username');
    if (usernameInput) {
        usernameInput.id = 'user-email-input';
        usernameInput.className = 'form-input-v2';
        mutations.push('username → user-email-input');
    }

    // 3. Change the password input ID
    const passwordInput = document.getElementById('password');
    if (passwordInput) {
        passwordInput.id = 'user-password-input';
        passwordInput.className = 'form-input-v2';
        mutations.push('password → user-password-input');
    }

    // 4. Change the error message ID
    const errorMsg = document.getElementById('error-message');
    if (errorMsg) {
        errorMsg.id = 'auth-error-banner';
        mutations.push('error-message → auth-error-banner');
    }

    return mutations;
}
"""


# =============================================================================
# Demo Flow
# =============================================================================

def run_demo():
    """Execute the full self-healing demonstration."""

    print_banner("AI-AUGMENTED SELF-HEALING TEST AUTOMATION DEMO")
    print(f"  {Colors.DIM}AI-Powered Self-Healing Test Automation Framework")
    print(f"  Self-Healing Locator Recovery Pipeline{Colors.RESET}\n")

    # ── Step 1: Start demo server ──
    print_step(1, "Starting demo application server...")
    server = start_server(8000)
    print_success("Demo server running at http://localhost:8000")
    time.sleep(0.5)

    # Initialize Playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1280, "height": 720})

    clear_healing_events()
    healing_engine = HealingEngine()

    try:
        # ── Step 2: Run test with CORRECT locators ──
        print_step(2, "Running login test with CORRECT locators...")
        page = context.new_page()
        page.goto("http://localhost:8000")
        page.wait_for_load_state("domcontentloaded")

        # Use correct locators
        page.locator("#username").fill("admin")
        page.locator("#password").fill("admin123")
        page.locator("#login-button").click()

        # Verify login succeeded
        page.wait_for_selector("#dashboard-container.active", timeout=5000)
        welcome = page.locator("#welcome-message").text_content()

        if "admin" in welcome:
            print_success(f"Test PASSED with correct locators")
            print_info(f"Welcome message: '{welcome}'")
        else:
            print_error("Unexpected welcome message")

        page.close()

        # ── Step 3: Mutate the DOM (simulate UI refactoring) ──
        print_step(3, "Mutating DOM to simulate UI refactoring...")
        page = context.new_page()
        page.goto("http://localhost:8000")
        page.wait_for_load_state("domcontentloaded")

        mutations = page.evaluate(MUTATION_SCRIPT)
        for m in mutations:
            print_warning(f"DOM mutation: {m}")

        print_info(f"Applied {len(mutations)} DOM mutations")

        # ── Step 4: Run test with BROKEN locators → triggers healing ──
        print_step(4, "Running login test with BROKEN locators (triggering self-healing)...")

        broken_selectors = [
            ("#username", "css", "Username input field on the login form"),
            ("#password", "css", "Password input field on the login form"),
            ("#login-button", "css", "Login submit button on the login form"),
        ]

        healed_results = []

        for selector, strategy, intent in broken_selectors:
            print(f"\n{Colors.YELLOW}  >> Attempting broken locator: '{selector}'{Colors.RESET}")

            smart = SmartElement(
                page=page,
                selector=selector,
                strategy=strategy,
                intent=intent,
                test_name="demo_self_healing_test",
                healing_engine=healing_engine,
                timeout_ms=2000,
            )

            try:
                locator = smart.find()

                if smart.was_healed:
                    result = smart.healing_result
                    print_success(
                        f"SELF-HEALED: '{selector}' -> '{result.healed_selector}'"
                    )
                    print_info(f"Confidence: {result.confidence:.2f}")
                    print_info(f"Reasoning: {result.reasoning}")
                    print_info(f"Provider: {result.llm_provider} ({result.llm_model})")
                    print_info(f"Decision: {result.decision.value}")

                    healed_results.append(result)

                    # Perform the action
                    if "username" in intent.lower():
                        locator.fill("admin")
                    elif "password" in intent.lower():
                        locator.fill("admin123")
                    elif "button" in intent.lower():
                        locator.click()
                else:
                    print_success(f"Element found without healing: '{selector}'")

            except Exception as e:
                print_error(f"Healing failed for '{selector}': {e}")

        # Verify the healed test completed successfully
        try:
            page.wait_for_selector(".dashboard-container.active", timeout=5000)
            welcome = page.locator("#welcome-message").text_content() or ""
            if "admin" in welcome.lower():
                print(f"\n{Colors.GREEN}{Colors.BOLD}  [OK] TEST PASSED (with self-healed locators!){Colors.RESET}")
            else:
                print_warning("Login may not have completed fully")
        except Exception:
            print_warning("Could not verify dashboard after healing")

        page.close()

        # ── Step 5: Generate healing report ──
        print_step(5, "Generating AI Self-Healing Report...")

        healing_events = get_healing_events()

        report_gen = HealingReportGenerator()
        report_path = report_gen.generate(
            healing_events=healing_events,
            output_filename="healing_report.html",
            open_browser=False,
        )

        print_success(f"Report generated: {report_path}")

        # ── Summary ──
        print_banner("DEMO COMPLETE — SUMMARY", Colors.GREEN)

        print(f"  {Colors.BOLD}Healing Events:{Colors.RESET} {len(healing_events)}")
        for event in healing_events:
            decision = event.get("decision", "unknown")
            color = Colors.GREEN if decision == "auto_heal" else Colors.YELLOW
            print(
                f"  {color}* {event.get('original_selector')} -> "
                f"{event.get('healed_selector')} "
                f"(confidence={event.get('confidence', 0):.2f}, "
                f"decision={decision}){Colors.RESET}"
            )

        print(f"\n  {Colors.BOLD}Report:{Colors.RESET} {Path(report_path).resolve()}")
        print(f"\n  {Colors.DIM}Set ANTHROPIC_API_KEY or GOOGLE_API_KEY in .env")
        print(f"  for real LLM-powered healing instead of mock responses.{Colors.RESET}\n")

    finally:
        context.close()
        browser.close()
        pw.stop()
        server.shutdown()


if __name__ == "__main__":
    run_demo()
