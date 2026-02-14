# Shared HubSpot Module Makefile
# Used for testing and linting the shared code

.PHONY: test
test:
	@echo "Running tests for shared module..."
	cd .. && pipenv run pytest tests/ -v -k hubspot

.PHONY: format
format:
	@echo "Formatting shared code..."
	pipenv run black hubspot.py

.PHONY: lint
lint:
	@echo "Linting shared code..."
	pipenv run flake8 hubspot.py
	pipenv run mypy hubspot.py

.PHONY: check
check: format lint test
	@echo "✓ All checks passed for shared module"
