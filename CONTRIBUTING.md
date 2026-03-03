# Contributing to Monolith to Microservices Demo

We love your input! We want to make contributing to this project as easy and transparent as possible.

## Development Setup

1. **Install Prerequisites**:
   - Python 3.11+
   - Node.js 18+
   - Docker & Docker Compose
   - [pre-commit](https://pre-commit.com/)

2. **Setup Pre-commit Hooks**:
   This repository uses `pre-commit` to enforce code quality locally.
   ```bash
   pip install pre-commit
   pre-commit install
   ```

3. **Running Quality Checks Locally**:
   You can manually run the checks on all files:
   ```bash
   pre-commit run --all-files
   ```

## Pull Request Process

1. Ensure any install or build dependencies are removed before the end of the PR.
2. Update the `README.md` with details of changes to the interface, if applicable.
3. Ensure CI checks (linting, tests, security scans) pass.
4. You may merge the PR in once you have the sign-off of at least one other developer.

## Code Style
- **Python**: We use `ruff` for linting and `black` for formatting.
- **Node.js**: We use `eslint` and `prettier`. 
