# Setup Guide — AI-Powered Self-Healing Test Automation Framework

## Prerequisites

- **Python 3.10+** (3.12 recommended)
- **Git**
- **pip** (included with Python)

## Installation

### 1. Clone the Repository

```bash
git clone <repo-url>
cd ai-powered-self-healing-framework
```

### 2. Create Virtual Environment

```bash
# Linux/Mac
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
.\venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright Browsers

```bash
playwright install chromium
```

### 5. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and set your API keys:
- `ANTHROPIC_API_KEY` — For Claude LLM (primary)
- `GOOGLE_API_KEY` — For Gemini LLM (fallback)

> **Note**: API keys are optional. The framework uses a MockProvider for demo/testing when no keys are configured.

## Running the Demo

```bash
python run_demo.py
```

This demonstrates the complete self-healing pipeline:
1. Runs a test with correct locators → PASS
2. Mutates the DOM → breaks locators
3. Runs the same test → triggers healing → PASS
4. Generates the healing report

## Running Tests

```bash
# All tests
pytest -v

# Specific test suites
pytest tests/ -v -m smoke      # UI smoke tests
pytest bdd/ -v                  # BDD tests
pytest api_tests/ -v -m api    # API tests
pytest etl_validation/ -v      # ETL tests
pytest performance/ -v         # Performance tests

# With HTML report
pytest -v --html=reports/report.html --self-contained-html
```

## Optional: PostgreSQL

By default, the framework uses SQLite. For PostgreSQL:

1. Install PostgreSQL and create a database
2. Set `DATABASE_URL` in `.env`:
   ```
   DATABASE_URL=postgresql://user:password@localhost:5432/qe_framework
   ```
3. Install psycopg2: `pip install psycopg2-binary`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `playwright install` fails | Run `playwright install --with-deps chromium` |
| Import errors | Ensure venv is activated and dependencies installed |
| Port 8000 in use | Change `DEMO_APP_BASE_URL` in `.env` |
| LLM timeout | Check API key, increase `request_timeout_seconds` in config.yaml |
