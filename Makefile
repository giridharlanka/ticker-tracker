.PHONY: install setup run test lint clean typecheck

PYTHON ?= python3
VENV ?= .venv
PIP = $(VENV)/bin/pip
PY = $(VENV)/bin/python

install:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -U pip
	$(PIP) install -e ".[dev,web]"

setup:
	$(PY) -m ticker_tracker.main --setup

run:
	$(PY) -m ticker_tracker.main

test:
	$(PY) -m pytest -q --cov=ticker_tracker --cov-report=term-missing

lint:
	$(VENV)/bin/ruff check ticker_tracker tests main.py
	$(VENV)/bin/ruff format --check ticker_tracker tests main.py

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true

typecheck:
	$(VENV)/bin/mypy ticker_tracker
