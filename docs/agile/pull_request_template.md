# Pull Request Template

## Summary
<!-- Brief description of what this PR does and why -->

## Changes
<!-- List of changes made -->
- 
- 
- 

## Type of Change
- [ ] 🐛 Bug fix (non-breaking change that fixes an issue)
- [ ] ✨ New feature (non-breaking change that adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to change)
- [ ] 📝 Documentation update
- [ ] 🔧 Configuration change
- [ ] ♻️ Refactoring (no functional changes)

## How Tested
<!-- Describe the tests you ran to verify your changes -->
- [ ] Unit tests pass: `pytest tests/ -v`
- [ ] BDD tests pass: `pytest bdd/ -v`
- [ ] API tests pass: `pytest api_tests/ -v`
- [ ] ETL tests pass: `pytest etl_validation/ -v`
- [ ] Self-healing demo works: `python run_demo.py`
- [ ] Manual verification: <!-- describe steps -->

## Screenshots / Report Output
<!-- If applicable, add screenshots or report snippets -->

## Linked User Story
<!-- Reference the user story this PR addresses -->
- US-XXX: <!-- Story title -->

## Checklist
- [ ] My code follows the project style guidelines (PEP 8)
- [ ] I have added/updated docstrings
- [ ] I have added/updated tests
- [ ] All existing tests still pass
- [ ] My changes use the shared LLM provider (no ad-hoc LLM calls)
- [ ] I have updated documentation as needed
- [ ] The CI pipeline passes
- [ ] This PR meets the [Definition of Done](docs/agile/definition_of_done.md)
