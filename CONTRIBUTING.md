# Contributing to behave-trace

Thanks for your interest in contributing! This guide covers setup, common
commands, and the release process.

## Setup

```bash
git clone https://github.com/MathiasPaulenko/behave-trace.git
cd behave-trace
make dev
pre-commit install
```

## Development commands

| Command             | Description                                  |
| ------------------- | -------------------------------------------- |
| `make help`         | Show all available targets.                  |
| `make dev`          | Install with dev extras.                     |
| `make lint`         | Run `ruff check` + `mypy --strict`.          |
| `make lint-fix`     | Auto-fix lint issues.                        |
| `make format`       | Format the code with `ruff format`.          |
| `make format-check` | Verify formatting without changes.           |
| `make test`         | Run the test suite.                          |
| `make test-cov`     | Run tests with coverage (fail under 55%).    |
| `make check`        | Full pre-commit check (lint + format + test).|
| `make build`        | Build sdist + wheel into `dist/`.            |
| `make clean`        | Remove build artifacts and caches.           |

## Pre-PR checklist

Before opening a pull request, make sure all of the following pass:

- [ ] `make check` (runs lint + format-check + test)
- [ ] `make test-cov` passes with >= 55% coverage
- [ ] New behavior is covered by tests
- [ ] `CHANGELOG.md` updated under `[Unreleased]`

## Release process

Releases are automated via the `release.yml` GitHub Actions workflow:

1. Bump the version in `pyproject.toml`.
2. Move the `[Unreleased]` section in `CHANGELOG.md` to the new version.
3. Commit and push to `main`.
4. The workflow detects the version bump, creates a git tag, builds the
   distributions, publishes to PyPI via Trusted Publishing (OIDC), and
   creates a GitHub Release with auto-generated notes.

## Code style

- Python >=3.11, `from __future__ import annotations` in every module.
- `ruff` for linting and formatting (line length 100).
- `mypy --strict` with no errors.
- Public API documented with docstrings.
