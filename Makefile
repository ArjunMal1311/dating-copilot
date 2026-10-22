.PHONY: check test lint format

PYTHON ?= python

check: lint test

test:
	$(PYTHON) -m pytest

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .
