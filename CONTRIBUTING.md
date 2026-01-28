# Contributing to flownexus

Welcome to the flownexus project! We're excited that you're interested in
helping us build a better local-first IoT framework. Whether you're fixing a
bug, improving documentation, or proposing new features, your contributions are
highly valued.

If you have questions, ideas, or find a bug, please feel free to open a
[GitHub Issue](https://github.com/jonasremmert/flownexus/issues) or start a
discussion.

## How to Contribute

### 1. Development Workflow
- Fork the repository and create your branch from `main`.
- If you're adding a new feature, consider opening an issue first to discuss
  the design.
- Ensure your code follows the existing style (see `AGENTS.md` for detailed
  Python/Django conventions).

### 2. Local CI Testing
Before opening a Pull Request, please run the basic CI tests locally. This
helps keep the build green and speeds up the review process.

The project uses a `Makefile` to simplify these checks:

- **Run Django Unit Tests**:
  ```bash
  make test-django
  ```
- **Run Compliance Checks** (Linting, Formatting, Git History):
  ```bash
  make compliance
  ```
- **(Optional) Run End-to-End Tests**:
  If you have Podman installed, you can run the full stack integration tests:
  ```bash
  make test-e2e
  ```

### 3. Commit & PR Requirements
To maintain a clean and legal history, we require the following:

- **Signed-off-by**: Every commit must be signed off to certify compliance with
  the Developer Certificate of Origin (DCO). Use the `-s` or `--signoff` flag:
  ```bash
  git commit --signoff -m "Sensordata: Add validation for composite resources"
  ```
- **Commit Format**: Use the format `Component: Brief description`.
- **Atomic Commits**: Keep commits focused on a single change.

## License

By contributing to flownexus, you agree that your contributions will be
licensed under the project's [Apache License 2.0](LICENSE).

Happy coding!
