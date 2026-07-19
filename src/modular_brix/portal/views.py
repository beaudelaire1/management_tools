from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.views import redirect_to_login
from django.apps import apps
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Model, Q, Sum
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.decorators.http import require_http_methods, require_POST

from modular_brix.foundation.accounts.models import Membership
from modular_brix.foundation.organizations.models import Organization
from modular_brix.foundation.permissions.policies import has_action_permission

from .forms import (
    LeadCreateForm,
    PartyCreateForm,
    PaymentAllocationForm,
    PaymentCreateForm,
    QuoteAcceptanceForm,
    QuoteCreateForm,
    QuoteLineForm,
)
from .configuration import load_portal_configuration
from .resources import Resource, available_resources, get_resource, navigation_groups, serialize_fields


def _active_membership(user: AbstractBaseUser, organization: Organization) -> Membership:
    membership = Membership.objects.filter(
        user=user,
        organization=organization,
        is_active=True,
    ).first()
    if membership is None:
        raise PermissionDenied("Vous n’avez pas accès à cette organisation.")
    return membership


def _organization_for(user: AbstractBaseUser, slug: str) -> tuple[Organization, Membership]:
    organization = get_object_or_404(Organization, slug=slug, is_active=True)
    return organization, _active_membership(user, organization)


def _check_action(
    membership: Membership,
    organization: Organization,
    action: str,
    *,
    scope_type: str = "",
    scope_ref: str = "",
) -> None:
    if not has_action_permission(
        membership_id=str(membership.id),
        action=action,
        organization_id=str(organization.id),
        scope_type=scope_type,
        scope_ref=scope_ref,
    ):
        raise PermissionDenied("Cette action n’est pas autorisée par votre rôle.")


def _portal_context(
    request: HttpRequest,
    organization: Organization | None = None,
    membership: Membership | None = None,
    **extra: Any,
) -> dict[str, Any]:
    portal_configuration = load_portal_configuration()
    context: dict[str, Any] = {
        "organization": organization,
        "membership": membership,
        "navigation_groups": navigation_groups(),
        "portal_configuration": portal_configuration,
        "organization_memberships": Membership.objects.filter(
            user=request.user,
            is_active=True,
            organization__is_active=True,
        ).select_related("organization").order_by("organization__legal_name"),
    }
    if organization is not None and membership is not None:
        context["can_create"] = has_action_permission(
            membership_id=str(membership.id),
            action="create",
            organization_id=str(organization.id),
        )
        context["can_validate"] = has_action_permission(
            membership_id=str(membership.id),
            action="validate",
            organization_id=str(organization.id),
        )
    context.update(extra)
    return context


class OrganizationPickerView(LoginRequiredMixin, View):
    template_name = "portal/organization_picker.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        memberships = Membership.objects.filter(
            user=request.user,
            is_active=True,
            organization__is_active=True,
        ).select_related("organization").order_by("organization__legal_name")
        if memberships.count() == 1:
            return redirect("portal:home", org_slug=memberships[0].organization.slug)
        return render(request, self.template_name, _portal_context(request, memberships=memberships))


class OrganizationViewMixin(LoginRequiredMixin):
    required_action = "read"
    organization: Organization
    membership: Membership

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        self.organization, self.membership = _organization_for(request.user, kwargs["org_slug"])
        if self.required_action:
            _check_action(self.membership, self.organization, self.required_action)
        return super().dispatch(request, *args, **kwargs)

    def context(self, request: HttpRequest, **extra: Any) -> dict[str, Any]:
        return _portal_context(request, self.organization, self.membership, **extra)


class HomeView(OrganizationViewMixin, View):
    template_name = "portal/home.html"

    def get(self, request: HttpRequest, org_slug: str) -> HttpResponse:
        organization_id = self.organization.id
        resource_keys = {resource.key for resource in available_resources()}
        invoice_model = apps.get_model("finance_billing.Invoice") if "invoices" in resource_keys else None
        if invoice_model is not None:
            issued_invoices = invoice_model.objects.filter(
                organization_id=organization_id,
                status="issued",
            )
            invoice_total = issued_invoices.aggregate(total=Sum("total_incl_tax"))["total"] or 0
            recent_invoices = issued_invoices.select_related("party").order_by("-issue_date", "-created_at")[:5]
        else:
            invoice_total = 0
            recent_invoices = []
        payment_model = apps.get_model("finance_payments.Payment") if "payments" in resource_keys else None
        paid_total = (
            payment_model.objects.filter(organization_id=organization_id).aggregate(total=Sum("amount"))["total"] or 0
            if payment_model is not None
            else 0
        )
        stat_definitions: tuple[tuple[str, str, dict[str, Any]], ...] = (
            ("parties", "Tiers actifs", {"is_active": True}),
            ("quotes", "Devis", {}),
            ("invoices", "Factures émises", {"status": "issued"}),
            ("payments", "Paiements", {}),
        )
        stats = tuple(
            {
                "label": label,
                "value": get_resource(key).queryset(str(organization_id)).filter(**filters).count(),
                "resource": key,
            }
            for key, label, filters in stat_definitions
            if key in resource_keys
        )
        quote_model = apps.get_model("management_sales.Quote") if "quotes" in resource_keys else None
        recent_quotes = (
            quote_model.objects.filter(organization_id=organization_id)
            .select_related("party")
            .order_by("-created_at")[:5]
            if quote_model is not None
            else []
        )
        return render(
            request,
            self.template_name,
            self.context(
                request,
                page_title="Vue d’ensemble",
                stats=stats,
                invoice_total=invoice_total,
                paid_total=paid_total,
                recent_invoices=recent_invoices,
                recent_quotes=recent_quotes,
                available_resource_keys=resource_keys,
            ),
        )


class ResourceListView(OrganizationViewMixin, View):
    template_name = "portal/resource_list.html"

    def get(self, request: HttpRequest, org_slug: str, resource_key: str) -> HttpResponse:
        try:
            resource = get_resource(resource_key)
        except LookupError as exc:
            raise Http404 from exc
        queryset = resource.queryset(str(self.organization.id))
        query = request.GET.get("q", "").strip()
        if query and resource.search_fields:
            filters = Q()
            for search_field in resource.search_fields:
                filters |= Q(**{f"{search_field}__icontains": query})
            queryset = queryset.filter(filters)
        paginator = Paginator(queryset, 25)
        page = paginator.get_page(request.GET.get("page"))
        rows = [
            {"pk": instance.pk, "cells": serialize_fields(instance, resource.list_fields)}
            for instance in page.object_list
        ]
        return render(
            request,
            self.template_name,
            self.context(
                request,
                page_title=resource.label,
                resource=resource,
                page=page,
                rows=rows,
                query=query,
                active_resource=resource.key,
            ),
        )


class ResourceDetailView(OrganizationViewMixin, View):
    required_action = ""

    def get(self, request: HttpRequest, org_slug: str, resource_key: str, pk: str) -> HttpResponse:
        try:
            resource = get_resource(resource_key)
        except LookupError as exc:
            raise Http404 from exc
        instance = get_object_or_404(resource.queryset(str(self.organization.id)), pk=pk)
        _check_action(
            self.membership,
            self.organization,
            "read",
            scope_type="object",
            scope_ref=str(instance.pk),
        )
        extra = self._domain_context(resource, instance)
        return render(
            request,
            resource.detail_template,
            self.context(
                request,
                page_title=f"{resource.singular.capitalize()} — {instance}",
                resource=resource,
                instance=instance,
                details=serialize_fields(instance, resource.detail_fields),
                active_resource=resource.key,
                **extra,
            ),
        )

    def _domain_context(self, resource: Resource, instance: Model) -> dict[str, Any]:
        if resource.key == "quotes":
            return {"lines": instance.lines.order_by("position")}
        if resource.key == "orders":
            return {
                "lines": instance.lines.order_by("position"),
                "deliveries": instance.deliveries.order_by("-created_at"),
            }
        if resource.key == "invoices":
            from modular_brix.finance.billing.services import invoice_remaining

            remaining = invoice_remaining(instance) if instance.status == "issued" else None
            return {
                "lines": instance.lines.order_by("position"),
                "credit_notes": instance.credit_notes.order_by("-created_at"),
                "allocations": instance.allocations.select_related("payment").order_by("-created_at"),
                "remaining": remaining,
            }
        if resource.key == "payments":
            from modular_brix.finance.payments.services import payment_unallocated

            return {
                "allocations": instance.allocations.select_related("invoice").order_by("-created_at"),
                "unallocated": payment_unallocated(instance),
            }
        return {}


def _form_context(
    request: HttpRequest,
    organization: Organization,
    membership: Membership,
    *,
    form,
    title: str,
    submit_label: str,
    cancel_url: str,
    description: str = "",
) -> dict[str, Any]:
    return _portal_context(
        request,
        organization,
        membership,
        page_title=title,
        form=form,
        submit_label=submit_label,
        cancel_url=cancel_url,
        description=description,
    )


def _authorized_form_view(
    request: HttpRequest,
    org_slug: str,
    *,
    action: str = "create",
) -> tuple[Organization, Membership] | HttpResponse:
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    organization, membership = _organization_for(request.user, org_slug)
    _check_action(membership, organization, action)
    return organization, membership


def _require_resource(resource_key: str) -> Resource:
    try:
        return get_resource(resource_key)
    except LookupError as exc:
        raise Http404 from exc


@require_http_methods(["GET", "POST"])
def party_create(request: HttpRequest, org_slug: str) -> HttpResponse:
    _require_resource("parties")
    access = _authorized_form_view(request, org_slug)
    if isinstance(access, HttpResponse):
        return access
    organization, membership = access
    form = PartyCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        from modular_brix.management.parties.services import create_party

        party = create_party(organization_id=str(organization.id), **form.cleaned_data)
        messages.success(request, "Le tiers a été créé.")
        return redirect("portal:resource-detail", org_slug=org_slug, resource_key="parties", pk=party.pk)
    return render(request, "portal/form.html", _form_context(request, organization, membership, form=form, title="Nouveau tiers", submit_label="Créer le tiers", cancel_url=reverse("portal:resource-list", kwargs={"org_slug": org_slug, "resource_key": "parties"})))


@require_http_methods(["GET", "POST"])
def lead_create(request: HttpRequest, org_slug: str) -> HttpResponse:
    _require_resource("leads")
    access = _authorized_form_view(request, org_slug)
    if isinstance(access, HttpResponse):
        return access
    organization, membership = access
    form = LeadCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        lead_model = apps.get_model("management_crm.Lead")
        lead = lead_model.objects.create(organization=organization, **form.cleaned_data)
        messages.success(request, "Le prospect a été créé.")
        return redirect("portal:resource-detail", org_slug=org_slug, resource_key="leads", pk=lead.pk)
    return render(request, "portal/form.html", _form_context(request, organization, membership, form=form, title="Nouveau prospect", submit_label="Créer le prospect", cancel_url=reverse("portal:resource-list", kwargs={"org_slug": org_slug, "resource_key": "leads"})))


@require_http_methods(["GET", "POST"])
def quote_create_view(request: HttpRequest, org_slug: str) -> HttpResponse:
    _require_resource("quotes")
    access = _authorized_form_view(request, org_slug)
    if isinstance(access, HttpResponse):
        return access
    organization, membership = access
    form = QuoteCreateForm(request.POST or None, organization_id=str(organization.id))
    if request.method == "POST" and form.is_valid():
        from modular_brix.management.sales.services import create_quote

        quote = create_quote(
            organization_id=str(organization.id),
            party_id=str(form.cleaned_data["party"].id),
            currency=form.cleaned_data["currency"],
        )
        messages.success(request, "Le devis a été créé. Ajoutez maintenant ses lignes.")
        return redirect("portal:resource-detail", org_slug=org_slug, resource_key="quotes", pk=quote.pk)
    return render(request, "portal/form.html", _form_context(request, organization, membership, form=form, title="Nouveau devis", submit_label="Créer le devis", cancel_url=reverse("portal:resource-list", kwargs={"org_slug": org_slug, "resource_key": "quotes"})))


@require_http_methods(["GET", "POST"])
def quote_line_create(request: HttpRequest, org_slug: str, quote_id: str) -> HttpResponse:
    _require_resource("quotes")
    access = _authorized_form_view(request, org_slug)
    if isinstance(access, HttpResponse):
        return access
    organization, membership = access
    quote_model = apps.get_model("management_sales.Quote")
    quote = get_object_or_404(quote_model, id=quote_id, organization=organization, status="draft")
    form = QuoteLineForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        from modular_brix.management.sales.services import add_quote_line

        add_quote_line(quote_id=str(quote.id), **form.cleaned_data)
        messages.success(request, "La ligne a été ajoutée au devis.")
        return redirect("portal:resource-detail", org_slug=org_slug, resource_key="quotes", pk=quote.pk)
    return render(request, "portal/form.html", _form_context(request, organization, membership, form=form, title=f"Ajouter une ligne à {quote.number}", submit_label="Ajouter la ligne", cancel_url=reverse("portal:resource-detail", kwargs={"org_slug": org_slug, "resource_key": "quotes", "pk": quote.pk})))


@require_POST
def quote_send_view(request: HttpRequest, org_slug: str, quote_id: str) -> HttpResponse:
    _require_resource("quotes")
    access = _authorized_form_view(request, org_slug, action="validate")
    if isinstance(access, HttpResponse):
        return access
    organization, _ = access
    quote_model = apps.get_model("management_sales.Quote")
    quote = get_object_or_404(quote_model, id=quote_id, organization=organization)
    try:
        from modular_brix.management.sales.services import send_quote

        send_quote(quote_id=str(quote.id))
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Le devis a été envoyé et sa version est désormais figée.")
    return redirect("portal:resource-detail", org_slug=org_slug, resource_key="quotes", pk=quote.pk)


@require_http_methods(["GET", "POST"])
def quote_accept_view(request: HttpRequest, org_slug: str, quote_id: str) -> HttpResponse:
    _require_resource("quotes")
    access = _authorized_form_view(request, org_slug, action="validate")
    if isinstance(access, HttpResponse):
        return access
    organization, membership = access
    quote_model = apps.get_model("management_sales.Quote")
    quote = get_object_or_404(quote_model, id=quote_id, organization=organization, status="sent")
    form = QuoteAcceptanceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        from modular_brix.management.sales.services import accept_quote

        accept_quote(quote_id=str(quote.id), **form.cleaned_data)
        messages.success(request, "Le devis a été accepté avec sa preuve.")
        return redirect("portal:resource-detail", org_slug=org_slug, resource_key="quotes", pk=quote.pk)
    return render(request, "portal/form.html", _form_context(request, organization, membership, form=form, title=f"Accepter {quote.number}", submit_label="Confirmer l’acceptation", cancel_url=reverse("portal:resource-detail", kwargs={"org_slug": org_slug, "resource_key": "quotes", "pk": quote.pk})))


@require_POST
def quote_convert_view(request: HttpRequest, org_slug: str, quote_id: str) -> HttpResponse:
    _require_resource("quotes")
    _require_resource("orders")
    access = _authorized_form_view(request, org_slug, action="validate")
    if isinstance(access, HttpResponse):
        return access
    organization, _ = access
    quote_model = apps.get_model("management_sales.Quote")
    quote = get_object_or_404(quote_model, id=quote_id, organization=organization)
    try:
        from modular_brix.management.sales.services import convert_quote_to_order

        order = convert_quote_to_order(quote_id=str(quote.id))
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("portal:resource-detail", org_slug=org_slug, resource_key="quotes", pk=quote.pk)
    messages.success(request, "La commande a été créée à partir du devis accepté.")
    return redirect("portal:resource-detail", org_slug=org_slug, resource_key="orders", pk=order.pk)


@require_POST
def order_invoice_view(request: HttpRequest, org_slug: str, order_id: str) -> HttpResponse:
    _require_resource("orders")
    _require_resource("invoices")
    access = _authorized_form_view(request, org_slug, action="validate")
    if isinstance(access, HttpResponse):
        return access
    organization, _ = access
    from modular_brix.finance.billing.services import create_invoice_from_order

    order_model = apps.get_model("management_sales.SalesOrder")
    order = get_object_or_404(order_model, id=order_id, organization=organization)
    invoice = create_invoice_from_order(order_id=str(order.id))
    messages.success(request, "La facture brouillon a été créée depuis la commande.")
    return redirect("portal:resource-detail", org_slug=org_slug, resource_key="invoices", pk=invoice.pk)


@require_POST
def invoice_issue_view(request: HttpRequest, org_slug: str, invoice_id: str) -> HttpResponse:
    _require_resource("invoices")
    access = _authorized_form_view(request, org_slug, action="validate")
    if isinstance(access, HttpResponse):
        return access
    organization, _ = access
    from modular_brix.finance.billing.services import issue_invoice

    invoice_model = apps.get_model("finance_billing.Invoice")
    invoice = get_object_or_404(invoice_model, id=invoice_id, organization=organization)
    try:
        issue_invoice(invoice_id=str(invoice.id))
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "La facture a été émise et figée.")
    return redirect("portal:resource-detail", org_slug=org_slug, resource_key="invoices", pk=invoice.pk)


@require_http_methods(["GET", "POST"])
def payment_create_view(request: HttpRequest, org_slug: str) -> HttpResponse:
    _require_resource("payments")
    access = _authorized_form_view(request, org_slug)
    if isinstance(access, HttpResponse):
        return access
    organization, membership = access
    form = PaymentCreateForm(request.POST or None, organization_id=str(organization.id))
    if request.method == "POST" and form.is_valid():
        from modular_brix.finance.payments.services import register_payment

        cleaned = form.cleaned_data
        payment = register_payment(
            organization_id=str(organization.id),
            party_id=str(cleaned["party"].id) if cleaned["party"] else None,
            amount=cleaned["amount"],
            currency=cleaned["currency"],
            method=cleaned["method"],
            provider_reference=cleaned["provider_reference"],
            idempotency_key=cleaned["idempotency_key"],
        )
        messages.success(request, "Le paiement a été enregistré sans duplication.")
        return redirect("portal:resource-detail", org_slug=org_slug, resource_key="payments", pk=payment.pk)
    return render(request, "portal/form.html", _form_context(request, organization, membership, form=form, title="Nouveau paiement", submit_label="Enregistrer le paiement", cancel_url=reverse("portal:resource-list", kwargs={"org_slug": org_slug, "resource_key": "payments"})))


@require_http_methods(["GET", "POST"])
def payment_allocate_view(request: HttpRequest, org_slug: str, payment_id: str) -> HttpResponse:
    _require_resource("payments")
    _require_resource("invoices")
    access = _authorized_form_view(request, org_slug, action="validate")
    if isinstance(access, HttpResponse):
        return access
    organization, membership = access
    from modular_brix.finance.payments.services import allocate_payment, payment_unallocated

    payment_model = apps.get_model("finance_payments.Payment")
    payment = get_object_or_404(payment_model, id=payment_id, organization=organization)
    form = PaymentAllocationForm(
        request.POST or None,
        organization_id=str(organization.id),
        party_id=str(payment.party_id) if payment.party_id else None,
        currency=payment.currency,
    )
    if request.method == "POST" and form.is_valid():
        try:
            allocate_payment(
                payment_id=str(payment.id),
                invoice_id=str(form.cleaned_data["invoice"].id),
                amount=form.cleaned_data["amount"],
            )
        except ValueError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Le paiement a été affecté à la facture.")
            return redirect("portal:resource-detail", org_slug=org_slug, resource_key="payments", pk=payment.pk)
    return render(request, "portal/form.html", _form_context(request, organization, membership, form=form, title="Affecter le paiement", submit_label="Affecter", cancel_url=reverse("portal:resource-detail", kwargs={"org_slug": org_slug, "resource_key": "payments", "pk": payment.pk}), description=f"Montant non affecté : {payment_unallocated(payment)} {payment.currency}"))
