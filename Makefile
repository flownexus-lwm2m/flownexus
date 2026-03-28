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
	doc \
	server-run \
	deploy

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
	uv run --group docs sphinx-build -E -W --keep-going -b html doc/source doc/build/html

doc-pdf: doc-generate
	uv run --group docs sphinx-build -M latexpdf doc/source doc/build/pdf

# Generate documentation artifacts (OpenAPI schema, ERD diagram)
doc-generate:
	mkdir -p doc/build/generated
	uv run --group docs python server/django/manage.py graph_models sensordata -o doc/source/images/erd.svg
	uv run --group docs python server/django/manage.py generate_openapi -o doc/build/generated/openapi-schema.yaml

# Serve documentation with live reload
doc: doc-generate
	uv run --group docs sphinx-autobuild doc/source doc/build/html --port 8001 --host 0.0.0.0

# Placeholder for all tests
test-all: test-django test-e2e compliance

# Build the server containers with the current git version
server-build:
	@APP_VERSION=$$(git describe --always --dirty --tags) podman-compose -f server/compose.yml build

# Run server stack in foreground with persistent data (Ctrl+C to stop)
# Uses --build to rebuild images and -v to remove named volumes (e.g. django-venv)
# so that dependency changes in uv.lock are always picked up.
server-run:
	@echo "Starting flownexus server stack..."
	@podman-compose -f server/compose.yml down -v 2>/dev/null || true
	@trap 'echo "Shutting down containers..."; podman-compose -f server/compose.yml down; exit 0' INT TERM; \
	APP_VERSION=$$(git describe --always --dirty --tags 2>/dev/null || echo "dev") \
		DJANGO_DB_HOST_PATH=$$(pwd)/server/data \
		FIRMWARE_STORAGE_HOST_PATH=$$(pwd)/server/firmware \
		podman-compose -f server/compose.yml up --build; \
	echo "Shutting down containers..."; \
	podman-compose -f server/compose.yml down

# Deploy to production server (requires sudo and SSH access)
# This uses systemd Quadlet for persistent rootless containers
deploy:
	@echo "Deploying Flownexus to production..."
	@echo "Usage: make deploy SERVER=flownexus.org USER=flownexus"
	@if [ -z "$(SERVER)" ]; then \
		echo "Error: SERVER variable not set. Example: make deploy SERVER=flownexus.org"; \
		exit 1; \
	fi
	@if [ -z "$(USER)" ]; then \
		USER=flownexus; \
	fi
	@echo "Deploying to $(SERVER) as user $(USER)..."
	ssh $(USER)@$(SERVER) "cd /home/$(USER)/flownexus && git fetch origin && git checkout main && git pull"
	ssh -t $(USER)@$(SERVER) "sudo /home/$(USER)/flownexus/deploy/deploy-flownexus"
	@echo "Deployment complete. View logs with:"
	@echo "  ssh $(USER)@$(SERVER) 'journalctl --user -u flownexus-django -f'"
