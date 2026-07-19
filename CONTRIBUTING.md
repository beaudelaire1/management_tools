# Contributing

## Ground rules

- The main branch must be protected: all changes go through a reviewed pull request and required CI checks.
- Changes touching billing, taxes, accounting entries, permissions, or retention require an explicit reviewer sign-off.
- No client-specific code, branding, or vocabulary in this repository.
- No secrets, credentials, or real personal data in code, fixtures, or tests.

## Local setup

1. Python 3.13, then `pip install --no-deps -r requirements.lock` and
   `pip install -e . --no-deps --no-build-isolation`.
2. `python manage.py migrate`
3. `python -m pytest`

## Quality gates (all blocking in CI)

- `ruff check .`
- `mypy src`
- `bandit -r src -c pyproject.toml`
- `pip-audit`
- `python manage.py makemigrations --check --dry-run`
- `pytest` with coverage >= 85%

## Commit and release

- Semantic versioning; every release updates CHANGELOG.md.
- Destructive migrations require a backup plan and a rehearsal on a copy.
- Architecture decisions are recorded in docs/adr/.
