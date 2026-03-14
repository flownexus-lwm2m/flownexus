# Flownexus Makefile

.PHONY: test-django \
	test-all \
	build-sim \
	test-e2e \
	run-mock \
	run-mock-multi-site \
	compliance \
	doc-html \
	doc-pdf \
	doc

# Run Django tests in an isolated environment using Tox
test-django:
	cd server/django && tox -e unit-tests

# Start a mock simulation session for frontend development (default scenario)
run-mock:
	python3 scripts/run_mock_env.py --fresh

# Start mock environment with multi-site scenario for RBAC testing
run-mock-multi-site:
	python3 scripts/run_mock_env.py --scenario multi-site --fresh

# Build Zephyr simulation binaries
build-sim:
	cd simulation && python3 simulate.py --config sim_zephyr.yaml --build

# Run End-to-End tests (Requires Podman)
test-e2e: build-sim
	@echo "Starting backend stack..."
	podman-compose -f server/compose.yml up -d
	@echo "Running simulation..."
	cd simulation && python3 simulate.py --config sim_zephyr.yaml --run --local &
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

# Serve documentation with live reload
doc:
	cd doc && tox -e doc

# Placeholder for all tests
test-all: test-django test-e2e compliance

# Build the server containers with the current git version
server-build:
	@APP_VERSION=$$(git describe --always --dirty --tags) podman-compose -f server/compose.yml build
