# Architecture — AI-Powered Self-Healing Test Automation Framework

## System Overview

The platform is organized into four architectural layers:

### 1. Test Execution Layer
- **UI Tests** — Playwright-based with Page Object Model (POM)
- **BDD Tests** — Gherkin feature files with pytest-bdd step definitions
- **API Tests** — requests + jsonschema (REST Assured equivalent)
- **ETL Tests** — pandas-based source-to-target reconciliation
- **Performance Tests** — JMeter (.jmx) + Locust (Python)

### 2. Core Framework Layer
- **DriverFactory** — Browser lifecycle management (Playwright + Selenium adapter)
- **SmartElement** — Self-healing element wrapper with transparent recovery
- **Page Objects** — BasePage, LoginPage, DashboardPage

### 3. AI Core Layer (Shared LLM Abstraction)
- **LLMProviderFactory** — Singleton factory with Claude primary / Gemini fallback
- **BaseLLMProvider** — Abstract interface with retry logic, JSON extraction
- **Healing Engine** — Orchestrates DOM extraction → LLM call → validation → confidence gate
- **Feature Modules** — Gherkin generation, semantic API validation, ETL anomaly detection, flaky analysis, failure RCA

### 4. Data & Reporting Layer
- **LocatorRepository** — SQLite-backed cache for healed locator mappings
- **JSONL Audit Log** — Append-only healing event trail
- **Unified Report** — Jinja2-templated HTML dashboard aggregating all pillars

## Self-Healing Data Flow

```
Test Locator Failure
       │
       ▼
   SmartElement.find()
       │
       ├── Cache Hit? ──YES──► Use cached healed locator
       │
       NO
       │
       ▼
   DOMContextExtractor
   (trim HTML to ~2000 chars)
       │
       ▼
   LLM Provider (Claude/Gemini/Mock)
   (structured JSON with candidates)
       │
       ▼
   CandidateValidator
   (live browser verification)
       │
       ▼
   ConfidenceGate
       │
       ├── ≥ 0.85 ──► AUTO_HEAL (continue test)
       ├── ≥ 0.60 ──► SUGGEST (fail + log suggestion)
       └── < 0.60 ──► REJECT (normal failure)
       │
       ▼
   LocatorRepository.save()
   (SQLite + JSONL audit log)
```

## Design Decisions

1. **Single LLM abstraction** — Every AI feature goes through `LLMProviderFactory`, ensuring consistent retry logic, fallback behavior, and cost tracking.

2. **Confidence gate** — Three-tier threshold prevents both blind automation (dangerous) and excessive manual review (slow).

3. **Repository-first** — Cache check before LLM call avoids redundant API calls across test runs.

4. **Mock provider** — Framework is fully demonstrable without API keys, making it accessible for evaluation and education.
