.PHONY: help test lint fmt run build install clean

PYTHON ?= python3

help: ## Show this help
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-8s\033[0m %s\n", $$1, $$2}'

test: ## Run the test suite
	$(PYTHON) -m pytest

lint: ## Check style and formatting
	ruff check .
	ruff format --check .

fmt: ## Format and auto-fix
	ruff format .
	ruff check --fix .

run: ## Run from the checkout
	./bin/zmkbat

build: ## Build sdist and wheel
	$(PYTHON) -m build

install: ## Install with pipx (falls back to pip --user)
	pipx install . || $(PYTHON) -m pip install --user .

clean: ## Remove build and cache artefacts
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
