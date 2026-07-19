from datetime import date

import pytest
from django.template.loader import render_to_string

from modular_brix.foundation.data_transfer.services import apply_import, create_import_job, run_export
from modular_brix.foundation.organizations.models import Organization
from modular_brix.foundation.organizations.services import create_organization_with_default_establishment
from modular_brix.foundation.reference_data.models import TaxCode
from modular_brix.foundation.reference_data.services import current_tax_code, load_initial_reference_data
from modular_brix.ui.services import save_table_preference, save_view


def _make_org(suffix: str):
    return create_organization_with_default_establishment(
        slug=f"org-{suffix}",
        legal_name=f"Org {suffix}",
        legal_identifier=f"RDT-{suffix}",
        country_code="FR",
    )


@pytest.mark.django_db
def test_reference_data_initial_load_is_reproducible() -> None:
    counts_first = load_initial_reference_data()
    counts_second = load_initial_reference_data()
    assert counts_first == counts_second
    assert counts_first["tax_codes"] == 4


@pytest.mark.django_db
def test_expired_tax_code_not_proposed_but_history_readable() -> None:
    load_initial_reference_data()
    expired = TaxCode.objects.get(code="fr-standard")
    expired.valid_to = date(2020, 12, 31)
    expired.save(update_fields=["valid_to"])

    assert current_tax_code(code="fr-standard", on_date=date(2026, 1, 1)) is None
    assert current_tax_code(code="fr-standard", on_date=date(2020, 6, 1)) is not None
    assert TaxCode.objects.filter(code="fr-standard").exists()  # history stays readable


@pytest.mark.django_db
def test_import_all_or_nothing_rejects_without_writing() -> None:
    org = _make_org("import-aon")
    applied: list[dict] = []

    job = create_import_job(
        organization_id=str(org.id),
        label="tiers",
        rows=[{"name": "Alpha"}, {"name": ""}, {"name": "Gamma"}],
        all_or_nothing=True,
    )
    result = apply_import(
        job_id=str(job.id),
        validator=lambda payload: "name is required" if not payload.get("name") else None,
        applier=lambda payload: applied.append(payload),
    )

    assert result.status == "rejected"
    assert applied == []  # nothing written
    statuses = list(result.rows.order_by("row_number").values_list("status", "error"))
    assert statuses == [("skipped", ""), ("invalid", "name is required"), ("skipped", "")]  # row-by-row report


@pytest.mark.django_db
def test_import_partial_mode_applies_valid_rows() -> None:
    org = _make_org("import-partial")
    applied: list[dict] = []

    job = create_import_job(
        organization_id=str(org.id),
        label="tiers",
        rows=[{"name": "Alpha"}, {"name": ""}],
        all_or_nothing=False,
    )
    result = apply_import(
        job_id=str(job.id),
        validator=lambda payload: "name is required" if not payload.get("name") else None,
        applier=lambda payload: applied.append(payload),
    )

    assert result.status == "completed_with_errors"
    assert applied == [{"name": "Alpha"}]


@pytest.mark.django_db
def test_export_is_scoped_to_organization() -> None:
    org_a = _make_org("export-a")
    _make_org("export-b")

    def provider(organization_id: str) -> list[dict]:
        return list(Organization.objects.filter(id=organization_id).values("slug"))

    job, rows = run_export(organization_id=str(org_a.id), label="orgs", row_provider=provider)
    assert job.row_count == 1
    assert rows == [{"slug": "org-export-a"}]


@pytest.mark.django_db
def test_saved_views_and_table_preferences() -> None:
    org = _make_org("ui-prefs")
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.create_user(username="ui_user", password="StrongPass123!")

    view = save_view(
        organization_id=str(org.id),
        user_id=user.id,
        view_key="invoices",
        name="En retard",
        parameters={"status": "overdue"},
    )
    updated = save_view(
        organization_id=str(org.id),
        user_id=user.id,
        view_key="invoices",
        name="En retard",
        parameters={"status": "overdue", "sort": "due_date"},
    )
    assert view.id == updated.id  # upsert, no duplicate

    preference = save_table_preference(user_id=user.id, table_key="invoices", preferences={"page_size": 50})
    assert preference.preferences["page_size"] == 50


def test_ui_templates_are_accessible() -> None:
    base = render_to_string("ui/base.html", {"page_title": "Test"})
    assert 'role="main"' in base
    assert "skip-link" in base
    assert 'lang="fr"' in base

    table = render_to_string(
        "ui/components/table.html",
        {"caption": "Factures", "headers": ["Numéro"], "rows": [["INV-1"]]},
    )
    assert "<caption>Factures</caption>" in table
    assert 'scope="col"' in table

    empty = render_to_string("ui/components/table.html", {"caption": "Vide", "headers": [], "rows": []})
    assert 'role="status"' in empty
