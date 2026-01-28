# Flownexus Makefile

.PHONY: test-django test-all build-sim test-e2e compliance doc-html doc-pdf

# Run Django tests in an isolated environment using Tox
test-django:
	cd server/django && tox -e unit-tests

# Build Zephyr simulation binaries
build-sim:
	cd simulation && python3 simulate.py -b -n 1

# Run End-to-End tests (Requires Podman)
test-e2e: build-sim
	@echo "Starting backend stack..."
	podman-compose -f server/compose.yml up -d
	@echo "Running simulation..."
	cd simulation && python3 simulate.py -r -l -n 1 &
	@echo "Verifying data..."
	python3 utils/verify_e2e.py
	@echo "Shutting down..."
	podman-compose -f server/compose.yml down
	pkill -f "simulate.py" || true
	pkill -f "ep_.*exe" || true

# Run compliance checks (linting, formatting, git history)
compliance:
	tox -c utils/ci/tox.ini -e compliance

# Build documentation
doc-html:
	cd doc && tox -e html

doc-pdf:
	cd doc && tox -e pdf

# Placeholder for all tests
test-all: test-django test-e2e compliance
