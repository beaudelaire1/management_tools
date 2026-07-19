"""Lot 4 operations bricks (G06-G15): acceptance-criteria tests."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from modular_brix.foundation.organizations.services import create_organization_with_default_establishment
from modular_brix.management.assets.models import Asset, MaintenancePlan
from modular_brix.management.assets.services import (
    maintenance_due,
    record_maintenance,
    record_meter_reading,
)
from modular_brix.management.catalog.models import CatalogItem
from modular_brix.management.contracts.models import Contract, Subscription
from modular_brix.management.contracts.services import (
    add_version,
    bill_subscription_period,
    expiring_contracts,
    sign_version,
    terminate_contract,
)
from modular_brix.management.interventions.models import Intervention, WorkOrder
from modular_brix.management.interventions.services import close_intervention, consume_item, sign_intervention
from modular_brix.management.parties.services import create_party
from modular_brix.management.projects.services import (
    add_dependency,
    add_task,
    blocked_tasks,
    create_project,
    project_progress,
)
from modular_brix.management.purchasing.models import PurchaseRequest, PurchaseRequestLine
from modular_brix.management.purchasing.services import (
    approve_request,
    create_order_from_request,
    receive_goods,
    submit_request,
)
from modular_brix.management.scheduling.models import Resource
from modular_brix.management.scheduling.services import book_resource, cancel_booking
from modular_brix.management.stock.models import Warehouse
from modular_brix.management.stock.services import (
    record_inventory_count,
    record_movement,
    reserve_stock,
    stock_level,
)
from modular_brix.management.support.models import SLAPolicy
from modular_brix.management.support.services import (
    add_message,
    customer_visible_messages,
    open_ticket,
    reopen_ticket,
    resolve_ticket,
)
from modular_brix.management.time_tracking.models import BillingRate, TimesheetPeriod
from modular_brix.management.time_tracking.services import record_time, value_entry
from modular_brix.management.workforce.models import (
    Certification,
    Employee,
    LeaveRequest,
    Position,
    SensitiveRecord,
)
from modular_brix.management.workforce.services import approve_leave, assign_position, read_sensitive_record


def _org(suffix: str):
    return create_organization_with_default_establishment(
        slug=f"ops-{suffix}",
        legal_name=f"Ops {suffix}",
        legal_identifier=f"OPS-{suffix}",
        country_code="FR",
    )


def _membership(org, suffix: str):
    user = get_user_model().objects.create_user(username=f"ops_{suffix}", password="StrongPass123!")
    return user.memberships.create(organization=org)


def _item(org, code="itm"):
    return CatalogItem.objects.create(organization=org, code=code, label=f"Item {code}")


# --- G06 purchasing -------------------------------------------------------


@pytest.mark.django_db
def test_purchase_request_approval_separation_and_capped_receipt() -> None:
    org = _org("g06")
    requester = _membership(org, "g06-req")
    approver = _membership(org, "g06-app")
    supplier = create_party(organization_id=str(org.id), kind="organization", display_name="Fournisseur")
    request = PurchaseRequest.objects.create(organization=org, requested_by=requester, subject="Matériel")
    PurchaseRequestLine.objects.create(
        request=request, position=1, description="Câbles", quantity=Decimal("10"), unit_price=Decimal("5")
    )
    submit_request(request_id=str(request.id))

    with pytest.raises(ValueError, match="requester"):
        approve_request(request_id=str(request.id), approver_membership_id=str(requester.id))
    approve_request(request_id=str(request.id), approver_membership_id=str(approver.id))

    order = create_order_from_request(request_id=str(request.id), supplier_id=str(supplier.id))
    assert create_order_from_request(request_id=str(request.id), supplier_id=str(supplier.id)).id == order.id

    line = order.lines.get()
    receive_goods(order_id=str(order.id), quantities={str(line.id): Decimal("6")})
    with pytest.raises(ValueError, match="exceeds the ordered remainder"):
        receive_goods(order_id=str(order.id), quantities={str(line.id): Decimal("5")})
    receive_goods(order_id=str(order.id), quantities={str(line.id): Decimal("4")})
    order.refresh_from_db()
    assert order.status == "received"


# --- G07 stock ------------------------------------------------------------


@pytest.mark.django_db
def test_stock_is_computed_from_append_only_movements() -> None:
    org = _org("g07")
    warehouse = Warehouse.objects.create(organization=org, code="MAIN", name="Principal")
    item = _item(org)

    movement = record_movement(
        organization_id=str(org.id),
        warehouse_id=str(warehouse.id),
        item_id=str(item.id),
        quantity=Decimal("100"),
        reason="receipt",
    )
    record_movement(
        organization_id=str(org.id),
        warehouse_id=str(warehouse.id),
        item_id=str(item.id),
        quantity=Decimal("-30"),
        reason="delivery",
    )
    assert stock_level(warehouse_id=str(warehouse.id), item_id=str(item.id)) == Decimal("70")

    movement.quantity = Decimal("999")
    with pytest.raises(ValueError, match="append-only"):
        movement.save()
    with pytest.raises(ValueError, match="append-only"):
        movement.delete()


@pytest.mark.django_db
def test_reservation_never_exceeds_available_and_inventory_justifies_gap() -> None:
    org = _org("g07b")
    warehouse = Warehouse.objects.create(organization=org, code="MAIN", name="Principal")
    item = _item(org)
    record_movement(
        organization_id=str(org.id),
        warehouse_id=str(warehouse.id),
        item_id=str(item.id),
        quantity=Decimal("10"),
        reason="receipt",
    )

    reserve_stock(
        organization_id=str(org.id), warehouse_id=str(warehouse.id), item_id=str(item.id), quantity=Decimal("7")
    )
    with pytest.raises(ValueError, match="only 3.000 available"):
        reserve_stock(
            organization_id=str(org.id),
            warehouse_id=str(warehouse.id),
            item_id=str(item.id),
            quantity=Decimal("4"),
        )

    count = record_inventory_count(
        warehouse_id=str(warehouse.id),
        item_id=str(item.id),
        counted_quantity=Decimal("8"),
        justification="casse constatée",
    )
    assert count.adjustment is not None and count.adjustment.quantity == Decimal("-2")
    assert stock_level(warehouse_id=str(warehouse.id), item_id=str(item.id)) == Decimal("8")


# --- G08 projects ---------------------------------------------------------


@pytest.mark.django_db
def test_task_dependency_cycles_rejected_and_progress_computed() -> None:
    org = _org("g08")
    project = create_project(organization_id=str(org.id), name="Refonte")
    task_a = add_task(project_id=str(project.id), name="Cadrage")
    task_b = add_task(project_id=str(project.id), name="Design")
    task_c = add_task(project_id=str(project.id), name="Développement")

    add_dependency(task_id=str(task_b.id), depends_on_id=str(task_a.id))
    add_dependency(task_id=str(task_c.id), depends_on_id=str(task_b.id))
    with pytest.raises(ValueError, match="cycle"):
        add_dependency(task_id=str(task_a.id), depends_on_id=str(task_c.id))

    assert {task.id for task in blocked_tasks(project_id=str(project.id))} == {task_b.id, task_c.id}
    task_a.status = "done"
    task_a.save()
    assert project_progress(project_id=str(project.id)) == Decimal("33.3")


# --- G09 interventions ----------------------------------------------------


@pytest.mark.django_db
def test_intervention_consumes_stock_once_and_signature_is_immutable() -> None:
    org = _org("g09")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client T")
    warehouse = Warehouse.objects.create(organization=org, code="VAN", name="Camion")
    item = _item(org)
    record_movement(
        organization_id=str(org.id),
        warehouse_id=str(warehouse.id),
        item_id=str(item.id),
        quantity=Decimal("5"),
        reason="receipt",
    )
    work_order = WorkOrder.objects.create(organization=org, party=party, subject="Dépannage")
    intervention = Intervention.objects.create(work_order=work_order, scheduled_at=timezone.now())

    for _ in range(2):  # replay decrements stock exactly once
        consume_item(
            intervention_id=str(intervention.id),
            warehouse_id=str(warehouse.id),
            item_id=str(item.id),
            quantity=Decimal("2"),
            idempotency_key="consume-1",
        )
    assert stock_level(warehouse_id=str(warehouse.id), item_id=str(item.id)) == Decimal("3")

    with pytest.raises(ValueError, match="report"):
        close_intervention(intervention_id=str(intervention.id), report="   ")
    close_intervention(intervention_id=str(intervention.id), report="Remplacement effectué")

    signature = sign_intervention(intervention_id=str(intervention.id), signed_by="Mme Cliente")
    signature.signed_by = "Falsifié"
    with pytest.raises(ValueError, match="never be modified"):
        signature.save()


# --- G10 scheduling -------------------------------------------------------


@pytest.mark.django_db
def test_double_booking_blocked_until_cancelled() -> None:
    org = _org("g10")
    resource = Resource.objects.create(organization=org, kind="room", name="Salle A")
    start = timezone.make_aware(datetime(2026, 8, 3, 9))

    booking = book_resource(
        organization_id=str(org.id),
        resource_id=str(resource.id),
        starts_at=start,
        ends_at=start + timedelta(hours=2),
    )
    with pytest.raises(ValueError, match="conflicts"):
        book_resource(
            organization_id=str(org.id),
            resource_id=str(resource.id),
            starts_at=start + timedelta(hours=1),
            ends_at=start + timedelta(hours=3),
        )
    # Adjacent slot is fine.
    book_resource(
        organization_id=str(org.id),
        resource_id=str(resource.id),
        starts_at=start + timedelta(hours=2),
        ends_at=start + timedelta(hours=3),
    )
    cancel_booking(booking_id=str(booking.id))
    book_resource(
        organization_id=str(org.id),
        resource_id=str(resource.id),
        starts_at=start,
        ends_at=start + timedelta(hours=1),
    )


# --- G11 time tracking ----------------------------------------------------


@pytest.mark.django_db
def test_time_entries_no_overlap_locked_periods_and_dated_valuation() -> None:
    org = _org("g11")
    worker = _membership(org, "g11-w")
    BillingRate.objects.create(
        organization=org,
        activity="dev",
        hourly_cost=Decimal("40.00"),
        hourly_price=Decimal("95.00"),
        valid_from=date(2026, 1, 1),
    )
    start = timezone.make_aware(datetime(2026, 7, 6, 9))

    entry = record_time(
        organization_id=str(org.id),
        worker_membership_id=str(worker.id),
        activity="dev",
        started_at=start,
        ended_at=start + timedelta(hours=3),
    )
    with pytest.raises(ValueError, match="overlaps"):
        record_time(
            organization_id=str(org.id),
            worker_membership_id=str(worker.id),
            activity="dev",
            started_at=start + timedelta(hours=2),
            ended_at=start + timedelta(hours=4),
        )

    valuation = value_entry(entry)
    assert valuation == {"hours": Decimal("3.00"), "cost": Decimal("120.00"), "price": Decimal("285.00")}

    TimesheetPeriod.objects.create(
        organization=org, starts_on=date(2026, 6, 1), ends_on=date(2026, 6, 30), is_locked=True
    )
    locked_start = timezone.make_aware(datetime(2026, 6, 15, 9))
    with pytest.raises(ValueError, match="locked"):
        record_time(
            organization_id=str(org.id),
            worker_membership_id=str(worker.id),
            activity="dev",
            started_at=locked_start,
            ended_at=locked_start + timedelta(hours=1),
        )


# --- G12 contracts --------------------------------------------------------


@pytest.mark.django_db
def test_signed_version_frozen_and_recurring_billing_idempotent() -> None:
    org = _org("g12")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Abonné")
    item = _item(org, code="abo")
    contract = Contract.objects.create(
        organization=org, party=party, subject="Maintenance", ends_on=date(2026, 9, 30), notice_days=30
    )
    version = add_version(contract_id=str(contract.id), terms="Conditions v1")
    sign_version(version_id=str(version.id))

    version.terms = "Réécrit"
    with pytest.raises(ValueError, match="frozen"):
        version.save()

    Subscription.objects.create(
        contract=contract, item=item, quantity=Decimal("1"), unit_price=Decimal("100"), tax_rate=Decimal("20")
    )
    invoice_1 = bill_subscription_period(contract_id=str(contract.id), period="2026-07")
    invoice_2 = bill_subscription_period(contract_id=str(contract.id), period="2026-07")
    assert invoice_1.id == invoice_2.id  # idempotent per period

    assert contract in expiring_contracts(organization_id=str(org.id))
    terminate_contract(contract_id=str(contract.id))
    contract.refresh_from_db()
    assert contract.versions.count() == 1  # history preserved


# --- G13 support ----------------------------------------------------------


@pytest.mark.django_db
def test_ticket_sla_private_messages_and_traced_reopening() -> None:
    org = _org("g13")
    party = create_party(organization_id=str(org.id), kind="organization", display_name="Client S")
    SLAPolicy.objects.create(organization=org, priority="high", resolution_hours=4)

    ticket = open_ticket(
        organization_id=str(org.id), party_id=str(party.id), subject="Panne", priority="high"
    )
    assert ticket.sla_due_at == ticket.opened_at + timedelta(hours=4)

    add_message(ticket_id=str(ticket.id), author_name="Agent", body="Note interne", is_private=True)
    add_message(ticket_id=str(ticket.id), author_name="Agent", body="Bonjour, nous intervenons.")
    visible = customer_visible_messages(ticket_id=str(ticket.id))
    assert [message.body for message in visible] == ["Bonjour, nous intervenons."]

    resolve_ticket(ticket_id=str(ticket.id))
    reopened = reopen_ticket(ticket_id=str(ticket.id))
    assert reopened.reopened_count == 1 and reopened.status == "open"


# --- G14 assets -----------------------------------------------------------


@pytest.mark.django_db
def test_asset_meter_monotonic_and_maintenance_due_by_time_or_meter() -> None:
    org = _org("g14")
    asset = Asset.objects.create(
        organization=org, code="VH-01", name="Véhicule", commissioned_on=date(2026, 1, 1)
    )
    record_meter_reading(asset_id=str(asset.id), read_at=timezone.now(), value=Decimal("1000"))
    with pytest.raises(ValueError, match="cannot decrease"):
        record_meter_reading(asset_id=str(asset.id), read_at=timezone.now(), value=Decimal("900"))

    time_plan = MaintenancePlan.objects.create(asset=asset, name="Révision annuelle", interval_days=180)
    meter_plan = MaintenancePlan.objects.create(
        asset=asset, name="Vidange", meter_interval=Decimal("500")
    )
    assert maintenance_due(plan_id=str(time_plan.id), on_day=date(2026, 7, 15)) is True
    assert maintenance_due(plan_id=str(meter_plan.id)) is True

    record_maintenance(
        asset_id=str(asset.id), plan_id=str(meter_plan.id), description="Vidange faite", done_on=date(2026, 7, 15)
    )
    assert maintenance_due(plan_id=str(meter_plan.id)) is False


# --- G15 workforce --------------------------------------------------------


@pytest.mark.django_db
def test_expired_certification_blocks_assignment_and_sensitive_reads_are_audited() -> None:
    org = _org("g15")
    membership = _membership(org, "g15-e")
    employee = Employee.objects.create(organization=org, membership=membership, full_name="Alex Martin")
    position = Position.objects.create(
        organization=org, title="Technicien haute tension", required_certification="HT-B2"
    )

    with pytest.raises(ValueError, match="required"):
        assign_position(employee_id=str(employee.id), position_id=str(position.id), starts_on=date(2026, 8, 1))
    Certification.objects.create(employee=employee, name="HT-B2", expires_on=date(2026, 6, 30))
    with pytest.raises(ValueError, match="expired"):
        assign_position(employee_id=str(employee.id), position_id=str(position.id), starts_on=date(2026, 8, 1))

    leave = LeaveRequest.objects.create(
        employee=employee, starts_on=date(2026, 8, 10), ends_on=date(2026, 8, 20)
    )
    with pytest.raises(ValueError, match="own requester"):
        approve_leave(leave_id=str(leave.id), approver_membership_id=str(membership.id))
    manager = _membership(org, "g15-m")
    assert approve_leave(leave_id=str(leave.id), approver_membership_id=str(manager.id)).status == "approved"

    SensitiveRecord.objects.create(employee=employee, payload={"iban": "FR76..."})
    from modular_brix.foundation.audit.models import AuditEvent

    before = AuditEvent.objects.filter(event_type="workforce.sensitive_record.read").count()
    payload = read_sensitive_record(employee_id=str(employee.id), actor_user_id=manager.user_id)
    assert payload == {"iban": "FR76..."}
    assert AuditEvent.objects.filter(event_type="workforce.sensitive_record.read").count() == before + 1
