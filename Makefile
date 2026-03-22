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

# Run Django tests using uv
test-django:
	cd server/django && uv run --extra test pytest sensordata/tests/ frontend/tests.py

# Start a mock simulation session for frontend development (default scenario)
run-mock:
	python3 devtools/mock/run_full_stack.py --fresh

# Start mock environment with multi-site scenario for RBAC testing
run-mock-multi-site:
	python3 devtools/mock/run_full_stack.py --scenario multi-site --fresh

# Build Zephyr simulation binaries
build-sim:
	cd devtools/zephyr && python3 run.py --config config.yaml --build

# Run End-to-End tests (Requires Podman)
test-e2e: build-sim
	@echo "Starting backend stack..."
	podman-compose -f server/compose.yml up -d
	@echo "Running simulation..."
	cd devtools/zephyr && python3 run.py --config config.yaml --run --local &
	@echo "Verifying data..."
	python3 devtools/zephyr/verify_e2e.py
	@echo "Shutting down..."
	podman-compose -f server/compose.yml down
	pkill -f "run.py" || true
	pkill -f "ep_.*exe" || true

# Run compliance checks (linting, formatting, git history)
compliance:
	uv run --group dev ruff check .
	uv run --group dev ruff format --check .
	uv run --group dev gitlint --commits "origin/HEAD..HEAD"

# Build documentation
doc-html: doc-generate
	cd doc && uv run --group docs sphinx-build -E -W --keep-going -b html source build/html

doc-pdf: doc-generate
	cd doc && uv run --group docs sphinx-build -M latexpdf source build/pdf

# Generate documentation artifacts (OpenAPI schema, ERD diagram)
doc-generate:
	mkdir -p doc/build/generated
	uv run --group docs python server/django/manage.py graph_models sensordata -o doc/source/images/erd.svg
	uv run --group docs python server/django/manage.py generate_openapi -o doc/build/generated/openapi-schema.yaml

# Serve documentation with live reload
doc: doc-generate
	cd doc && uv run --group docs sphinx-autobuild source build/html --port 8001 --host 0.0.0.0

# Placeholder for all tests
test-all: test-django test-e2e compliance

# Build the server containers with the current git version
server-build:
	@APP_VERSION=$$(git describe --always --dirty --tags) podman-compose -f server/compose.yml build
