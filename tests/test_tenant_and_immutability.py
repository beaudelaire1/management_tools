from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from modular_brix.finance.billing.models import Invoice, InvoiceLine
from modular_brix.finance.billing.services import create_invoice_from_order, issue_invoice
from modular_brix.finance.payments.services import register_payment
from modular_brix.foundation.notifications.services import queue_notification
from modular_brix.foundation.organizations.services import create_organization_with_default_establishment
from modular_brix.foundation.permissions.models import DataScope, PolicyDecisionLog, Role
from modular_brix.foundation.permissions.policies import has_action_permission
from modular_brix.foundation.permissions.services import assign_role, delegate_role
from modular_brix.foundation.workflows.services import (
    create_workflow_definition,
    create_workflow_state,
    start_workflow_instance,
)
from modular_brix.management.parties.services import create_party
from modular_brix.management.sales.models import Quote, QuoteLine
from modular_brix.management.sales.services import (
    accept_quote,
    add_quote_line,
    convert_quote_to_order,
    create_quote,
    send_quote,
)
from modular_brix.steering.dashboards.models import Dashboard
from modular_brix.steering.dashboards.services import add_widget, get_widget_data
from modular_brix.steering.indicators.services import create_indicator, record_manual_value
from modular_brix.steering.objectives.services import add_key_result, create_objective
from modular_brix.steering.reports.services import create_report, run_report


def _make_org(suffix: str):
    return create_organization_with_default_establishment(
        slug=f"secure-{suffix}",
        legal_name=f"Secure {suffix}",
        legal_identifier=f"SEC-{suffix}",
        country_code="FR",
    )


def _make_membership(org, username: str):
    user = get_user_model().objects.create_user(username=username, password="StrongPass123!")
    return user.memberships.create(organization=org)


def _make_indicator(org, code: str):
    return create_indicator(
        organization_id=str(org.id),
        code=code,
        label=code,
        unit="EUR",
        source="test",
        frequency="monthly",
        owner="Direction",
    )


def _make_issued_invoice(org, party):
    quote = create_quote(organization_id=str(org.id), party_id=str(party.id))
    add_quote_line(
        quote_id=str(quote.id),
        description="Prestation",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        tax_rate=Decimal("20"),
    )
    send_quote(quote_id=str(quote.id))
    accept_quote(quote_id=str(quote.id), acceptance_proof="Bon pour accord")
    order = convert_quote_to_order(quote_id=str(quote.id))
    invoice = create_invoice_from_order(order_id=str(order.id))
    return quote, issue_invoice(invoice_id=str(invoice.id))


@pytest.mark.django_db
def test_permission_is_bound_to_active_membership_organization() -> None:
    org_a = _make_org("permission-a")
    org_b = _make_org("permission-b")
    membership = _make_membership(org_a, "tenant_reader")
    Role.objects.create(code="tenant-reader", label="Reader", can_read=True)
    assign_role(membership_id=str(membership.id), role_code="tenant-reader", trusted_system=True)

    assert has_action_permission(
        membership_id=str(membership.id), action="read", organization_id=str(org_a.id)
    ) is True
    assert has_action_permission(
        membership_id=str(membership.id), action="read", organization_id=str(org_b.id)
    ) is False
    assert PolicyDecisionLog.objects.filter(
        membership=membership,
        target_organization=org_b,
        reason="organization_mismatch",
        allowed=False,
    ).exists()

    membership.is_active = False
    membership.save(update_fields=["is_active"])
    assert has_action_permission(
        membership_id=str(membership.id), action="read", organization_id=str(org_a.id)
    ) is False


@pytest.mark.django_db
def test_data_scope_and_delegation_cannot_be_broadened() -> None:
    org = _make_org("scope")
    manager = _make_membership(org, "scope_manager")
    substitute = _make_membership(org, "scope_substitute")
    outsider_org = _make_org("scope-outsider")
    outsider = _make_membership(outsider_org, "scope_outsider")
    role = Role.objects.create(code="scoped-validator", label="Validator", can_validate=True)
    assignment = assign_role(
        membership_id=str(manager.id), role_code=role.code, trusted_system=True
    )
    DataScope.objects.create(role_assignment=assignment, scope_type="object", scope_ref="invoice-1")

    assert has_action_permission(
        membership_id=str(manager.id),
        action="validate",
        organization_id=str(org.id),
        scope_type="object",
        scope_ref="invoice-1",
    ) is True
    assert has_action_permission(
        membership_id=str(manager.id),
        action="validate",
        organization_id=str(org.id),
        scope_type="object",
        scope_ref="invoice-2",
    ) is False
    assert has_action_permission(
        membership_id=str(manager.id), action="validate", organization_id=str(org.id)
    ) is False

    starts_at = timezone.now() - timezone.timedelta(minutes=1)
    ends_at = timezone.now() + timezone.timedelta(days=1)
    with pytest.raises(ValueError, match="explicit permitted scope"):
        delegate_role(
            role_code=role.code,
            from_membership_id=str(manager.id),
            to_membership_id=str(substitute.id),
            starts_at=starts_at,
            ends_at=ends_at,
        )
    with pytest.raises(ValueError, match="across organizations"):
        delegate_role(
            role_code=role.code,
            from_membership_id=str(manager.id),
            to_membership_id=str(outsider.id),
            starts_at=starts_at,
            ends_at=ends_at,
            scope_type="object",
            scope_ref="invoice-1",
        )

    delegate_role(
        role_code=role.code,
        from_membership_id=str(manager.id),
        to_membership_id=str(substitute.id),
        starts_at=starts_at,
        ends_at=ends_at,
        scope_type="object",
        scope_ref="invoice-1",
    )
    assert has_action_permission(
        membership_id=str(substitute.id),
        action="validate",
        organization_id=str(org.id),
        scope_type="object",
        scope_ref="invoice-1",
    ) is True
    assert has_action_permission(
        membership_id=str(substitute.id),
        action="validate",
        organization_id=str(org.id),
        scope_type="object",
        scope_ref="invoice-2",
    ) is False

    assignment.delete()
    assert has_action_permission(
        membership_id=str(substitute.id),
        action="validate",
        organization_id=str(org.id),
        scope_type="object",
        scope_ref="invoice-1",
    ) is False


@pytest.mark.django_db
def test_dashboard_and_report_block_cross_organization_access() -> None:
    org_a = _make_org("steering-a")
    org_b = _make_org("steering-b")
    membership_a = _make_membership(org_a, "steering_reader")
    Role.objects.create(code="steering-reader", label="Reader", can_read=True)
    assign_role(
        membership_id=str(membership_a.id), role_code="steering-reader", trusted_system=True
    )

    indicator_a = _make_indicator(org_a, "indicator-a")
    indicator_b = _make_indicator(org_b, "indicator-b")
    record_manual_value(definition_id=str(indicator_b.id), period="2026-07", value=Decimal("42"))
    dashboard_a = Dashboard.objects.create(organization=org_a, owner_user=membership_a.user, title="A")
    dashboard_b = Dashboard.objects.create(organization=org_b, owner_user=membership_a.user, title="B")

    with pytest.raises(ValueError, match="another organization"):
        add_widget(dashboard_id=str(dashboard_a.id), widget_type="kpi", indicator_id=str(indicator_b.id))

    widget_b = add_widget(
        dashboard_id=str(dashboard_b.id), widget_type="kpi", indicator_id=str(indicator_b.id)
    )
    with pytest.raises(PermissionError, match="denied"):
        get_widget_data(widget_id=str(widget_b.id), membership_id=str(membership_a.id))

    add_widget(dashboard_id=str(dashboard_a.id), widget_type="kpi", indicator_id=str(indicator_a.id))
    report_b = create_report(
        organization_id=str(org_b.id), code="invoices-b", label="Invoices B", dataset_key="issued_invoices"
    )
    with pytest.raises(PermissionError, match="denied"):
        run_report(report_id=str(report_b.id), membership_id=str(membership_a.id))


@pytest.mark.django_db
def test_commercial_documents_reject_cross_organization_relations_and_mutation() -> None:
    org_a = _make_org("commerce-a")
    org_b = _make_org("commerce-b")
    party_a = create_party(organization_id=str(org_a.id), kind="organization", display_name="Client A")

    with pytest.raises(ValueError, match="created as a draft"):
        Quote.objects.create(organization=org_a, party=party_a, number="Q-INVALID", status="sent")
    with pytest.raises(ValueError, match="created as a draft"):
        Invoice.objects.create(organization=org_a, party=party_a, status="issued")

    with pytest.raises(ValueError, match="same organization"):
        create_quote(organization_id=str(org_b.id), party_id=str(party_a.id))

    quote, invoice = _make_issued_invoice(org_a, party_a)
    quote.number = "Q-TAMPERED"
    with pytest.raises(ValueError, match="immutable"):
        quote.save()
    quote.refresh_from_db()
    quote.status = "draft"
    with pytest.raises(ValueError, match="Illegal quote status transition"):
        quote.save()
    quote.refresh_from_db()
    with pytest.raises(ValueError, match="immutable"):
        quote.delete()

    quote_line = QuoteLine.objects.get(quote=quote)
    quote_line.description = "Altération"
    with pytest.raises(ValueError, match="immutable"):
        quote_line.save()
    with pytest.raises(ValueError, match="immutable"):
        quote_line.delete()

    invoice_line = InvoiceLine.objects.get(invoice=invoice)
    invoice_line.description = "Altération"
    with pytest.raises(ValueError, match="immutable"):
        invoice_line.save()
    with pytest.raises(ValueError, match="immutable"):
        invoice_line.delete()


@pytest.mark.django_db
def test_cross_organization_service_relationships_are_rejected() -> None:
    org_a = _make_org("relations-a")
    org_b = _make_org("relations-b")
    member_a = _make_membership(org_a, "relations_a")
    member_b = _make_membership(org_b, "relations_b")
    actor_a = _make_membership(org_a, "relations_actor_a")
    role = Role.objects.create(code="relations-role", label="Relations", can_create=True)

    with pytest.raises(PermissionError, match="authorized actor"):
        assign_role(membership_id=str(member_a.id), role_code=role.code)

    with pytest.raises(ValueError, match="across organizations"):
        assign_role(
            membership_id=str(member_a.id),
            role_code=role.code,
            actor_membership_id=str(member_b.id),
        )

    with pytest.raises(PermissionError, match="cannot manage permissions"):
        assign_role(
            membership_id=str(member_a.id),
            role_code=role.code,
            actor_membership_id=str(actor_a.id),
        )

    permission_manager = Role.objects.create(
        code="permission-manager", label="Permission manager", can_manage_permissions=True
    )
    assign_role(
        membership_id=str(actor_a.id), role_code=permission_manager.code, trusted_system=True
    )
    assignment = assign_role(
        membership_id=str(member_a.id),
        role_code=role.code,
        actor_membership_id=str(actor_a.id),
    )
    assert str(assignment.membership_id) == str(member_a.id)

    with pytest.raises(ValueError, match="actively belong"):
        queue_notification(
            organization_id=str(org_a.id),
            recipient_user_id=member_b.user_id,
            channel="in_app",
            subject="Private",
            body="Private",
            idempotency_key="cross-tenant-notification",
        )

    definition = create_workflow_definition(organization_id=str(org_a.id), code="tenant-workflow")
    create_workflow_state(
        definition_id=str(definition.id), code="initial", label="Initial", is_initial=True
    )
    with pytest.raises(ValueError, match="same organization"):
        start_workflow_instance(
            organization_id=str(org_b.id),
            definition_id=str(definition.id),
            object_type="invoice",
            object_id="INV-1",
            requester_user_id=member_b.user_id,
        )

    indicator_b = _make_indicator(org_b, "relations-indicator-b")
    objective_a = create_objective(
        organization_id=str(org_a.id),
        label="Objective A",
        owner="Direction",
        horizon=timezone.now().date(),
    )
    with pytest.raises(ValueError, match="same organization"):
        add_key_result(
            objective_id=str(objective_a.id),
            indicator_id=str(indicator_b.id),
            target_value=Decimal("1"),
        )

    party_b = create_party(organization_id=str(org_b.id), kind="organization", display_name="Party B")
    with pytest.raises(ValueError, match="same organization"):
        register_payment(
            organization_id=str(org_a.id),
            party_id=str(party_b.id),
            amount=Decimal("10.00"),
            method="transfer",
            idempotency_key="cross-tenant-payment",
        )


@pytest.mark.django_db
def test_payment_idempotency_replay_requires_identical_payload() -> None:
    org = _make_org("payment-replay")
    payment = register_payment(
        organization_id=str(org.id),
        amount=Decimal("100.00"),
        method="transfer",
        idempotency_key="provider-event-1",
        provider_reference="bank-1",
    )
    replay = register_payment(
        organization_id=str(org.id),
        amount=Decimal("100.00"),
        method="transfer",
        idempotency_key="provider-event-1",
        provider_reference="bank-1",
    )
    assert replay.id == payment.id

    with pytest.raises(ValueError, match="different payment payload"):
        register_payment(
            organization_id=str(org.id),
            amount=Decimal("101.00"),
            method="transfer",
            idempotency_key="provider-event-1",
            provider_reference="bank-1",
        )


@pytest.mark.skipif(connection.vendor != "postgresql", reason="Database triggers require PostgreSQL.")
@pytest.mark.django_db(transaction=True)
def test_postgresql_triggers_block_bulk_financial_mutation() -> None:
    org = _make_org("trigger")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client Trigger")
    quote, invoice = _make_issued_invoice(org, party)

    with pytest.raises(DatabaseError):
        with transaction.atomic():
            QuoteLine.objects.filter(quote=quote).update(description="Bulk alteration")
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            InvoiceLine.objects.filter(invoice=invoice).update(description="Bulk alteration")
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            Quote.objects.bulk_create(
                [Quote(organization=org, party=party, number="Q-BULK-INVALID", status="sent")]
            )
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            Invoice.objects.bulk_create([Invoice(organization=org, party=party, status="issued")])
