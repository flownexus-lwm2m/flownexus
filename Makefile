# Flownexus Makefile
#
# "checks" and "system-test" run what the CI workflows checks.yml and
# system_test.yml run; the other targets are their single steps.

# Runtime for the image builds, e.g. make leshan-image CONTAINER_RUNTIME=docker
CONTAINER_RUNTIME ?= podman

# Zephyr's own Python requirements, resolved by uv from the Zephyr tree
ZEPHYR_REQS := ../zephyr/scripts
ZEPHYR_UV := uv run --no-project --with-requirements $(ZEPHYR_REQS)/requirements-base.txt

# The system tests need Podman or Docker, the Leshan image and a native_sim binary
SYSTEM_TEST := FLOWNEXUS_RUN_E2E=1 PYTHONPATH=.:server/django \
	uv run --extra test pytest -n 0 --override-ini addopts="" --pyargs

# Build the native_sim binary unless FLOWNEXUS_ZEPHYR_BINARY names one (CI)
SIM_BINARY := $(if $(FLOWNEXUS_ZEPHYR_BINARY),,build-sim)

.PHONY: test-all checks system-test \
	test-django test-unit compliance doc-build doc-html doc-pdf doc-generate deploy-test \
	checkpatch build-sim test-sim leshan-image django-image redis-image \
	test-contract image-smoke-test test-e2e \
	doc run-mock run-mock-multi-site server-build server-run deploy

# --- CI workflows ---

# Run all tests and checks
test-all: checks system-test

# checks.yml: everything that needs only the source checkout
checks: test-unit compliance doc-build deploy-test

# system_test.yml: client checks, images, gateway contract and E2E
system-test: checkpatch build-sim test-sim leshan-image django-image redis-image \
	test-contract image-smoke-test test-e2e

# --- Checks ---

# Run Django tests using uv
test-django:
	cd server/django && uv run --extra test pytest sensordata/tests/ frontend/tests.py

# Run all tests that need only the source checkout
test-unit: test-django
	PYTHONPATH=.:server/django uv run --extra test pytest \
		--pyargs devtools.zephyr.e2e.test_harness -n 0

# Run compliance checks (linting, formatting, git history)
compliance:
	uv run --group dev ruff check .
	uv run --group dev ruff format --check .
	uv run --group dev gitlint --commits "origin/HEAD..HEAD"

# Build the documentation as HTML and PDF
doc-build: doc-html doc-pdf

doc-html: doc-generate
	uv run --group docs sphinx-build -E -W --keep-going -b html doc/source doc/build/html

doc-pdf: doc-generate
	uv run --group docs sphinx-build -M latexpdf doc/source doc/build/pdf

# Generate documentation artifacts (OpenAPI schema, ERD diagram)
doc-generate:
	mkdir -p doc/build/generated
	uv run --group docs python server/django/manage.py graph_models sensordata -o doc/source/images/erd.svg
	uv run --group docs python server/django/manage.py generate_openapi -o doc/build/generated/openapi-schema.yaml

# Lint the deployment and test the rendered nginx config in a container
deploy-test:
	cd deploy/ansible && uv run --only-group deploy ansible-lint
	deploy/ansible/tests/nginx-test

# --- System tests ---

# Run Zephyr checkpatch on the native_sim client
checkpatch:
	perl ../zephyr/scripts/checkpatch.pl --no-tree -f \
		devtools/zephyr/client/src/*.c devtools/zephyr/client/src/*.h

# Build the native_sim binary. -c reconfigures CMake on each build, because
# each uv run creates a new Python and a cached interpreter path goes stale.
build-sim:
	$(ZEPHYR_UV) west build -c \
		-b native_sim/native/64 \
		devtools/zephyr/client \
		-d devtools/zephyr/client/build

# Run the native_sim twister tests
test-sim:
	$(ZEPHYR_UV) \
		--with-requirements $(ZEPHYR_REQS)/requirements-build-test.txt \
		--with-requirements $(ZEPHYR_REQS)/requirements-run-test.txt \
		west twister -T devtools/zephyr/client -p native_sim/native/64 \
		-O devtools/zephyr/twister-out

# Build the Leshan gateway image used by E2E, compose and deploy
leshan-image:
	$(CONTAINER_RUNTIME) build --build-arg REVISION=$$(git rev-parse HEAD) \
		-t localhost/flownexus-leshan:latest \
		-f server/leshan/Containerfile server/leshan

# Build the Django image (application and Celery worker)
django-image:
	$(CONTAINER_RUNTIME) build --build-arg APP_VERSION=$$(git describe --always --dirty --tags) \
		--build-arg REVISION=$$(git rev-parse HEAD) \
		-t localhost/flownexus-django:latest \
		-f server/django/Dockerfile.django .

# Build the Redis image
redis-image:
	$(CONTAINER_RUNTIME) build --build-arg REVISION=$$(git rev-parse HEAD) \
		-t localhost/flownexus-redis:latest \
		-f server/redis/Dockerfile.redis server/redis

# Check the Leshan gateway against the golden files in contract/gateway
test-contract: $(SIM_BINARY)
	$(SYSTEM_TEST) devtools.zephyr.e2e.test_contract

# Run the Redis, Leshan and Django images together and check basic function
image-smoke-test:
	devtools/image-smoke-test

# Run the full-stack End-to-End scenarios
test-e2e: $(SIM_BINARY)
	$(SYSTEM_TEST) devtools.zephyr.e2e.test_scenarios

# --- Development ---

# Serve documentation with live reload
doc: doc-generate
	uv run --group docs sphinx-autobuild doc/source doc/build/html --port 8001 --host 0.0.0.0

# Start a mock simulation session for frontend development (default scenario)
run-mock:
	python3 devtools/mock/run_full_stack.py --fresh

# Start mock environment with multi-site scenario for RBAC testing
run-mock-multi-site:
	python3 devtools/mock/run_full_stack.py --scenario multi-site --fresh

# Build the server containers with the current git version
server-build:
	@APP_VERSION=$$(git describe --always --dirty --tags) podman-compose -f server/compose.yml build

# Run server stack in foreground with persistent data (Ctrl+C to stop)
# Uses --build to rebuild images from the current source.
server-run:
	@echo "Starting flownexus server stack..."
	@podman-compose -f server/compose.yml down 2>/dev/null || true
	@trap 'echo "Shutting down containers..."; podman-compose -f server/compose.yml down; exit 0' INT TERM; \
	APP_VERSION=$$(git describe --always --dirty --tags 2>/dev/null || echo "dev") \
		DJANGO_DB_HOST_PATH=$$(pwd)/server/data \
		FIRMWARE_STORAGE_HOST_PATH=$$(pwd)/server/firmware \
		podman-compose -f server/compose.yml up --build; \
	echo "Shutting down containers..."; \
	podman-compose -f server/compose.yml down

# --- Deployment ---

# Deploy published images with Ansible (normally done by .github/workflows/deploy.yml)
# Usage: make deploy IMAGE_TAG=sha-<short sha>, with deploy/ansible/inventory.yml
deploy:
	@test -f deploy/ansible/inventory.yml || \
		{ echo "Create deploy/ansible/inventory.yml from inventory.example.yml"; exit 1; }
	@test -n "$(IMAGE_TAG)" || { echo "Usage: make deploy IMAGE_TAG=sha-<short sha>"; exit 1; }
	cd deploy/ansible && uv run --only-group deploy ansible-playbook -i inventory.yml \
		-e flownexus_image_tag=$(IMAGE_TAG) --diff site.yml
