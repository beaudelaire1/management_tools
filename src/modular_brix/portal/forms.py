from decimal import Decimal

from django import forms

from modular_brix.finance.billing.models import Invoice
from modular_brix.management.parties.models import Party


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
    party = forms.ModelChoiceField(label="Tiers", queryset=Party.objects.none())
    currency = forms.CharField(label="Devise", initial="EUR", min_length=3, max_length=3)

    def __init__(self, *args, organization_id: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["party"].queryset = Party.objects.filter(
            organization_id=organization_id,
            is_active=True,
            merged_into__isnull=True,
        ).order_by("display_name")

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
    party = forms.ModelChoiceField(
        label="Tiers",
        queryset=Party.objects.none(),
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
        self.fields["party"].queryset = Party.objects.filter(
            organization_id=organization_id,
            is_active=True,
            merged_into__isnull=True,
        ).order_by("display_name")

    def clean_currency(self) -> str:
        return self.cleaned_data["currency"].upper()


class PaymentAllocationForm(forms.Form):
    invoice = forms.ModelChoiceField(label="Facture", queryset=Invoice.objects.none())
    amount = forms.DecimalField(label="Montant à affecter", min_value=Decimal("0.01"), decimal_places=2)

    def __init__(self, *args, organization_id: str, party_id: str | None, currency: str, **kwargs):
        super().__init__(*args, **kwargs)
        invoices = Invoice.objects.filter(
            organization_id=organization_id,
            status="issued",
            currency=currency,
        ).order_by("due_date", "number")
        if party_id is not None:
            invoices = invoices.filter(party_id=party_id)
        self.fields["invoice"].queryset = invoices
