# Modular Brix

Neutral, installable Django building blocks for management, finance, and steering systems.

## Project status

This repository is a **pre-release domain foundation**, not a complete ERP and not production-ready accounting
software. The implemented bricks provide models, migrations, transactional services, invariants, and tests. Most
server-rendered interfaces, APIs, asynchronous tasks, external adapters, and regulated accounting capabilities are
still to be built.

Implemented baselines:

- Foundation: F01-F12
- Management: G01-G05
- Finance: C01-C03
- Steering: P01-P09 and P13

Not started:

- Operations and workforce management: G06-G15 and P10-P12
- Expenses, supplier accounting, banking, general and analytical accounting, tax, fixed assets, closing,
  electronic invoicing, and FEC: C04-C15

The exact implemented scope and explicit limits are maintained in `docs/spec_traceability.md` and each brick's
README.

## Architecture

- Python 3.13 and Django 5.2 LTS
- PostgreSQL as the production and integration-test database
- modular monolith under the neutral `modular_brix` namespace
- explicit transactional services for business commands
- organization-bound permissions and data scopes
- PostgreSQL triggers for append-only audit events and immutable issued financial documents
- server-rendered UI as the target; no mandatory SPA or CDN

Client projects install the package and activate only the Django applications they need in `INSTALLED_APPS`.
`example_project` is the integration host used by migrations and tests; it currently exposes Django admin and a
health endpoint, not a complete demonstration application.

## Reproducible local setup

Create and activate a Python 3.13 virtual environment, then run:

```bash
python -m pip install --no-deps -r requirements.lock
python -m pip install -e . --no-deps --no-build-isolation
python manage.py migrate
pytest -q
```

The lock file is the installation source used by CI. `pyproject.toml` declares supported dependency ranges; it is
not the reproducible installation source.

## Quality commands

```bash
ruff check .
mypy src
bandit -r src -c pyproject.toml
pip-audit --skip-editable
python manage.py makemigrations --check --dry-run
python manage.py check
pytest -q
```

CI also migrates an empty PostgreSQL 16 database and executes Django's production deployment checks.

## Security and compliance boundary

All business data must be attached to an organization. Permission checks require the target organization and may
also require an establishment, team, or object scope. Issued invoices and their lines, and sent quote versions and
their lines, are protected against direct PostgreSQL mutation.

The repository contains no client branding or studio-specific runtime marks. French tax, invoice, accounting,
retention, electronic invoicing, and FEC requirements remain subject to documented legal and professional
validation before any production use.
