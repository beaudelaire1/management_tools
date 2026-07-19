from decimal import Decimal

from django import forms
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db.models import QuerySet


class ScopedModelChoiceField(forms.ChoiceField):
    """Model selector that does not import an optional brick at module import time."""

    queryset: QuerySet | None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queryset = None

    def bind_queryset(self, queryset: QuerySet) -> None:
        self.queryset = queryset
        empty = [('', '---------')] if not self.required else []
        self.choices = [*empty, *((str(instance.pk), str(instance)) for instance in queryset)]

    def clean(self, value):
        selected_id = super().clean(value)
        if selected_id in self.empty_values:
            return None
        if self.queryset is None:
            raise ValidationError("Cette sélection n’est pas disponible.", code="unavailable")
        try:
            return self.queryset.get(pk=selected_id)
        except (ValueError, self.queryset.model.DoesNotExist) as exc:
            raise ValidationError("Sélection invalide.", code="invalid_choice") from exc


class PartyCreateForm(forms.Form):
    kind = forms.ChoiceField(
        label="Type de tiers",
        choices=(("organization", "Organisation"), ("person", "Personne")),
    )
    display_name = forms.CharField(label="Nom", max_length=255)
    email = forms.EmailField(label="E-mail", required=False)


class LeadCreateForm(forms.Form):
    display_name = forms.CharField(label="Nom du prospect", max_length=255)
    email = forms.EmailField(label="E-mail", required=False)


class QuoteCreateForm(forms.Form):
    party = ScopedModelChoiceField(label="Tiers")
    currency = forms.CharField(label="Devise", initial="EUR", min_length=3, max_length=3)

    def __init__(self, *args, organization_id: str, **kwargs):
        super().__init__(*args, **kwargs)
        party_model = apps.get_model("management_parties.Party")
        queryset = party_model.objects.filter(
            organization_id=organization_id,
            is_active=True,
            merged_into__isnull=True,
        ).order_by("display_name")
        self.fields["party"].bind_queryset(queryset)

    def clean_currency(self) -> str:
        return self.cleaned_data["currency"].upper()


class QuoteLineForm(forms.Form):
    description = forms.CharField(label="Description", max_length=500)
    quantity = forms.DecimalField(label="Quantité", min_value=Decimal("0.001"), decimal_places=3)
    unit_price = forms.DecimalField(label="Prix unitaire HT", min_value=Decimal("0"), decimal_places=4)
    tax_rate = forms.DecimalField(label="Taux de TVA (%)", min_value=Decimal("0"), decimal_places=3)


class QuoteAcceptanceForm(forms.Form):
    acceptance_proof = forms.CharField(
        label="Preuve d’acceptation",
        max_length=255,
        help_text="Référence du bon pour accord, du courriel ou de la signature.",
    )


class PaymentCreateForm(forms.Form):
    party = ScopedModelChoiceField(
        label="Tiers",
        required=False,
        help_text="Laisser vide pour un paiement non identifié.",
    )
    amount = forms.DecimalField(label="Montant", min_value=Decimal("0.01"), decimal_places=2)
    currency = forms.CharField(label="Devise", initial="EUR", min_length=3, max_length=3)
    method = forms.ChoiceField(
        label="Moyen de paiement",
        choices=(
            ("transfer", "Virement"),
            ("card", "Carte"),
            ("check", "Chèque"),
            ("cash", "Espèces"),
        ),
    )
    provider_reference = forms.CharField(label="Référence externe", max_length=128, required=False)
    idempotency_key = forms.CharField(
        label="Clé d’idempotence",
        max_length=120,
        help_text="Identifiant stable de l’événement bancaire ou de l’import.",
    )

    def __init__(self, *args, organization_id: str, **kwargs):
        super().__init__(*args, **kwargs)
        party_model = apps.get_model("management_parties.Party")
        queryset = party_model.objects.filter(
            organization_id=organization_id,
            is_active=True,
            merged_into__isnull=True,
        ).order_by("display_name")
        self.fields["party"].bind_queryset(queryset)

    def clean_currency(self) -> str:
        return self.cleaned_data["currency"].upper()


class PaymentAllocationForm(forms.Form):
    invoice = ScopedModelChoiceField(label="Facture")
    amount = forms.DecimalField(label="Montant à affecter", min_value=Decimal("0.01"), decimal_places=2)

    def __init__(self, *args, organization_id: str, party_id: str | None, currency: str, **kwargs):
        super().__init__(*args, **kwargs)
        invoice_model = apps.get_model("finance_billing.Invoice")
        invoices = invoice_model.objects.filter(
            organization_id=organization_id,
            status="issued",
            currency=currency,
        ).order_by("due_date", "number")
        if party_id is not None:
            invoices = invoices.filter(party_id=party_id)
        self.fields["invoice"].bind_queryset(invoices)
