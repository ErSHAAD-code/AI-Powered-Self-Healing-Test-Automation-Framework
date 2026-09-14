# Definition of Done — AI-Powered Self-Healing Test Automation Framework

All work items (user stories, tasks, bugs) must meet the following criteria before being marked as "Done":

## Code Quality
- [ ] Code follows Python PEP 8 style guidelines
- [ ] All functions and classes have docstrings
- [ ] No hardcoded values — configuration lives in config.yaml or .env
- [ ] All AI features use the shared `LLMProviderFactory` — no ad-hoc LLM calls
- [ ] Type hints on all function signatures

## Testing
- [ ] Unit tests written and passing
- [ ] Integration tests written and passing (where applicable)
- [ ] All existing tests still pass (no regressions)
- [ ] Test markers applied (@smoke, @regression, @api, @etl, @performance)
- [ ] Edge cases covered (empty inputs, error states, timeouts)

## Self-Healing Specific
- [ ] Healing events are logged to SQLite and JSONL audit trail
- [ ] Confidence gate thresholds are respected
- [ ] Cached healings are validated before reuse
- [ ] Healing report reflects the changes

## Documentation
- [ ] README updated if public API changes
- [ ] Architecture doc updated for structural changes
- [ ] Code comments explain "why", not "what"
- [ ] JD-aligned terminology used in docstrings and comments

## Review & Integration
- [ ] Code reviewed by at least one team member
- [ ] PR follows the pull_request_template.md format
- [ ] CI pipeline passes (all jobs green)
- [ ] No security issues (no credentials in code, .env excluded from git)
- [ ] Changes merged to develop branch (or main for releases)
