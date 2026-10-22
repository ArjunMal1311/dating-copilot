"""Shared test configuration for local-only tests."""

import os

# Importing config must never require a personal provider key during tests.
os.environ["LLM_BACKEND"] = "gateway"
