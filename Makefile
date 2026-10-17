# Flownexus Makefile

.PHONY: test-django \
	test-all \
	build-sim \
	test-sim \
	test-e2e \
	leshan-image \
	django-image \
	redis-image \
	image-smoke-test \
	run-mock \
	run-mock-multi-site \
	compliance \
	checkpatch \
	doc-html \
	doc-pdf \
	doc \
	server-run \
	deploy \
	deploy-test

# Run Django tests using uv
test-django:
	cd server/django && uv run --extra test pytest sensordata/tests/ frontend/tests.py

# Start a mock simulation session for frontend development (default scenario)
run-mock:
	python3 devtools/mock/run_full_stack.py --fresh

# Start mock environment with multi-site scenario for RBAC testing
run-mock-multi-site:
	python3 devtools/mock/run_full_stack.py --scenario multi-site --fresh

# Zephyr's own Python requirements, resolved by uv from the Zephyr tree
ZEPHYR_REQS := ../zephyr/scripts
ZEPHYR_UV := uv run --no-project --with-requirements $(ZEPHYR_REQS)/requirements-base.txt

# Build Zephyr simulation binaries
build-sim:
	$(ZEPHYR_UV) west build \
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
	podman build --build-arg REVISION=$$(git rev-parse HEAD) \
		-t localhost/flownexus-leshan:latest \
		-f server/leshan/Containerfile server/leshan

# Build the Django image (application and Celery worker)
django-image:
	podman build --build-arg APP_VERSION=$$(git describe --always --dirty --tags) \
		--build-arg REVISION=$$(git rev-parse HEAD) \
		-t localhost/flownexus-django:latest \
		-f server/django/Dockerfile.django .

# Build the Redis image
redis-image:
	podman build --build-arg REVISION=$$(git rev-parse HEAD) \
		-t localhost/flownexus-redis:latest \
		-f server/redis/Dockerfile.redis server/redis

# Run the Redis, Leshan and Django images together and check basic function
image-smoke-test:
	devtools/image-smoke-test

# Run End-to-End tests (Requires Podman or Docker, plus a native_sim binary)
test-e2e: build-sim
	FLOWNEXUS_RUN_E2E=1 PYTHONPATH=.:server/django \
		uv run --extra test pytest --pyargs devtools.zephyr.e2e \
		-n 0 --override-ini addopts=""

# Run compliance checks (linting, formatting, git history)
compliance:
	uv run --group dev ruff check .
	uv run --group dev ruff format --check .
	uv run --group dev gitlint --commits "origin/HEAD..HEAD"

# Run Zephyr checkpatch on the native_sim client
checkpatch:
	perl ../zephyr/scripts/checkpatch.pl --no-tree -f \
		devtools/zephyr/client/src/*.c devtools/zephyr/client/src/*.h

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

# Deploy published images with Ansible (normally done by .github/workflows/deploy.yml)
# Usage: make deploy IMAGE_TAG=sha-<short sha>, with deploy/ansible/inventory.yml
deploy:
	@test -f deploy/ansible/inventory.yml || \
		{ echo "Create deploy/ansible/inventory.yml from inventory.example.yml"; exit 1; }
	@test -n "$(IMAGE_TAG)" || { echo "Usage: make deploy IMAGE_TAG=sha-<short sha>"; exit 1; }
	cd deploy/ansible && uv run --only-group deploy ansible-playbook -i inventory.yml \
		-e flownexus_image_tag=$(IMAGE_TAG) --diff site.yml

# Lint the deployment and test the rendered nginx config in a container
deploy-test:
	cd deploy/ansible && uv run --only-group deploy ansible-lint
	deploy/ansible/tests/nginx-test
