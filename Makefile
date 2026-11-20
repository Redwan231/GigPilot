# GigPilot local verify scripts (P0-6). Thin wrappers over the test runners.
# Requires GNU Make. On Windows without make, run the commands under each target directly.
#
#   make backend-test   -> backend pytest suite
#   make fe-test        -> frontend vitest suite
#   make test           -> both

.PHONY: backend-test fe-test test lint

backend-test:
	cd backend && python -m pytest

fe-test:
	cd frontend && npm test

test: backend-test fe-test

lint:
	cd backend && python -m ruff check app && python -m black --check app
	cd frontend && npm run lint
