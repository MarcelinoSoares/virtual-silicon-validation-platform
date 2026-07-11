.PHONY: install test test-unit test-integration test-system test-performance \
        lint typecheck coverage report clean docker-build docker-test docker-api \
        seed validate

PYTHON := python
PIP := pip
PYTEST := pytest
RUFF := ruff
MYPY := mypy

install:
	$(PIP) install -e ".[dev]"

install-dev:
	$(PIP) install -e ".[dev]"

test:
	$(PYTEST) tests/ -v --tb=short

test-unit:
	$(PYTEST) tests/unit/ -v -m unit --tb=short

test-integration:
	$(PYTEST) tests/integration/ -v -m integration --tb=short

test-system:
	$(PYTEST) tests/system/ -v -m system --tb=short

test-performance:
	$(PYTEST) tests/performance/ -v -m performance --tb=short

test-memory:
	$(PYTEST) tests/ -v -m memory --tb=short

test-protocol:
	$(PYTEST) tests/ -v -m protocol --tb=short

test-fault:
	$(PYTEST) tests/ -v -m fault --tb=short

coverage:
	$(PYTEST) tests/ --cov=virtual_silicon --cov-report=html:reports/coverage --cov-report=term-missing

lint:
	$(RUFF) check src/ tests/

lint-fix:
	$(RUFF) check src/ tests/ --fix

typecheck:
	$(MYPY) src/virtual_silicon/

format:
	$(RUFF) format src/ tests/

seed:
	$(PYTHON) scripts/seed_database.py

validate:
	$(PYTHON) scripts/run_validation.py

report:
	$(PYTHON) scripts/generate_report.py

api:
	uvicorn virtual_silicon.api.main:app --reload --host 0.0.0.0 --port 8000

docker-build:
	docker compose build

docker-test:
	docker compose run --rm test

docker-api:
	docker compose up api

docker-validate:
	docker compose run --rm validate

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov
	rm -rf reports/charts reports/coverage
	rm -f virtual_silicon*.db

ci:
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) test
	$(MAKE) coverage
