from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.apps import apps
from django.db.models import Model, QuerySet


@dataclass(frozen=True)
class ResourceField:
    path: str
    label: str


@dataclass(frozen=True)
class Resource:
    key: str
    category: str
    label: str
    singular: str
    model_label: str
    organization_lookup: str
    list_fields: tuple[ResourceField, ...]
    detail_fields: tuple[ResourceField, ...]
    search_fields: tuple[str, ...] = ()
    select_related: tuple[str, ...] = ()
    ordering: tuple[str, ...] = ("-pk",)
    create_url_name: str = ""
    detail_template: str = "portal/resource_detail.html"

    @property
    def model(self) -> type[Model]:
        model = apps.get_model(self.model_label)
        if model is None:
            raise LookupError(f"Model {self.model_label} is not installed.")
        return model

    def queryset(self, organization_id: str) -> QuerySet:
        queryset = self.model.objects.all()
        if self.organization_lookup:
            queryset = queryset.filter(**{self.organization_lookup: organization_id})
        if self.select_related:
            queryset = queryset.select_related(*self.select_related)
        return queryset.order_by(*self.ordering)


def field(path: str, label: str) -> ResourceField:
    return ResourceField(path=path, label=label)


RESOURCES = (
    Resource(
        "parties", "Gestion", "Tiers", "tiers", "management_parties.Party", "organization_id",
        (field("display_name", "Nom"), field("kind", "Type"), field("email", "E-mail"), field("is_active", "Actif")),
        (field("display_name", "Nom"), field("kind", "Type"), field("email", "E-mail"), field("normalized_name", "Nom normalisé"), field("is_active", "Actif"), field("created_at", "Créé le")),
        ("display_name", "email", "normalized_name"), ordering=("display_name",), create_url_name="portal:party-create",
    ),
    Resource(
        "leads", "Gestion", "Prospects", "prospect", "management_crm.Lead", "organization_id",
        (field("display_name", "Nom"), field("email", "E-mail"), field("status", "Statut"), field("created_at", "Créé le")),
        (field("display_name", "Nom"), field("email", "E-mail"), field("status", "Statut"), field("party.display_name", "Tiers lié"), field("created_at", "Créé le")),
        ("display_name", "email", "status"), select_related=("party",), ordering=("-created_at",), create_url_name="portal:lead-create",
    ),
    Resource(
        "opportunities", "Gestion", "Opportunités", "opportunité", "management_crm.Opportunity", "organization_id",
        (field("label", "Libellé"), field("stage", "Étape"), field("probability", "Probabilité"), field("status", "Statut")),
        (field("label", "Libellé"), field("party.display_name", "Tiers"), field("lead.display_name", "Prospect"), field("stage", "Étape"), field("probability", "Probabilité"), field("status", "Statut"), field("loss_reason", "Motif de perte"), field("created_at", "Créé le")),
        ("label", "stage", "status", "party__display_name"), select_related=("party", "lead"), ordering=("-created_at",),
    ),
    Resource(
        "catalog", "Gestion", "Catalogue", "article", "management_catalog.CatalogItem", "organization_id",
        (field("code", "Code"), field("label", "Libellé"), field("item_type", "Type"), field("default_tax_rate", "TVA"), field("is_active", "Actif")),
        (field("code", "Code"), field("label", "Libellé"), field("item_type", "Type"), field("default_tax_rate", "TVA"), field("is_active", "Actif"), field("created_at", "Créé le")),
        ("code", "label", "item_type"), ordering=("code",),
    ),
    Resource(
        "quotes", "Gestion", "Devis", "devis", "management_sales.Quote", "organization_id",
        (field("number", "Numéro"), field("party.display_name", "Tiers"), field("version", "Version"), field("status", "Statut"), field("total_incl_tax", "Total TTC")),
        (field("number", "Numéro"), field("version", "Version"), field("party.display_name", "Tiers"), field("status", "Statut"), field("currency", "Devise"), field("valid_until", "Valide jusqu’au"), field("total_excl_tax", "Total HT"), field("total_tax", "TVA"), field("total_incl_tax", "Total TTC"), field("accepted_at", "Accepté le"), field("acceptance_proof", "Preuve d’acceptation")),
        ("number", "party__display_name", "status"), select_related=("party",), ordering=("-created_at",), create_url_name="portal:quote-create", detail_template="portal/quotes_detail.html",
    ),
    Resource(
        "orders", "Gestion", "Commandes", "commande", "management_sales.SalesOrder", "organization_id",
        (field("number", "Numéro"), field("party.display_name", "Tiers"), field("status", "Statut"), field("total_incl_tax", "Total TTC")),
        (field("number", "Numéro"), field("party.display_name", "Tiers"), field("quote.number", "Devis"), field("status", "Statut"), field("currency", "Devise"), field("total_excl_tax", "Total HT"), field("total_tax", "TVA"), field("total_incl_tax", "Total TTC"), field("created_at", "Créé le")),
        ("number", "party__display_name", "status"), select_related=("party", "quote"), ordering=("-created_at",), detail_template="portal/orders_detail.html",
    ),
    Resource(
        "invoices", "Finance", "Factures", "facture", "finance_billing.Invoice", "organization_id",
        (field("number", "Numéro"), field("party.display_name", "Tiers"), field("status", "Statut"), field("due_date", "Échéance"), field("total_incl_tax", "Total TTC")),
        (field("number", "Numéro"), field("party.display_name", "Tiers"), field("status", "Statut"), field("issue_date", "Émise le"), field("due_date", "Échéance"), field("currency", "Devise"), field("seller_name", "Vendeur"), field("buyer_name", "Acheteur"), field("total_excl_tax", "Total HT"), field("total_tax", "TVA"), field("total_incl_tax", "Total TTC")),
        ("number", "party__display_name", "status", "buyer_name"), select_related=("party", "sales_order"), ordering=("-created_at",), detail_template="portal/invoices_detail.html",
    ),
    Resource(
        "payments", "Finance", "Paiements", "paiement", "finance_payments.Payment", "organization_id",
        (field("received_at", "Reçu le"), field("party.display_name", "Tiers"), field("amount", "Montant"), field("currency", "Devise"), field("method", "Moyen")),
        (field("received_at", "Reçu le"), field("party.display_name", "Tiers"), field("amount", "Montant"), field("currency", "Devise"), field("method", "Moyen"), field("provider_reference", "Référence"), field("idempotency_key", "Clé d’idempotence")),
        ("party__display_name", "provider_reference", "idempotency_key", "method"), select_related=("party",), ordering=("-received_at",), create_url_name="portal:payment-create", detail_template="portal/payments_detail.html",
    ),
    Resource(
        "disputes", "Finance", "Litiges", "litige", "finance_receivables.Dispute", "invoice__organization_id",
        (field("invoice.number", "Facture"), field("reason", "Motif"), field("status", "Statut"), field("opened_at", "Ouvert le")),
        (field("invoice.number", "Facture"), field("invoice.party.display_name", "Tiers"), field("reason", "Motif"), field("status", "Statut"), field("opened_at", "Ouvert le"), field("resolved_at", "Résolu le")),
        ("invoice__number", "reason", "status"), select_related=("invoice", "invoice__party"), ordering=("-opened_at",),
    ),
    Resource(
        "reminders", "Finance", "Relances", "relance", "finance_receivables.Reminder", "invoice__organization_id",
        (field("invoice.number", "Facture"), field("invoice.party.display_name", "Tiers"), field("level", "Niveau"), field("sent_at", "Envoyée le")),
        (field("invoice.number", "Facture"), field("invoice.party.display_name", "Tiers"), field("level", "Niveau"), field("sent_at", "Envoyée le")),
        ("invoice__number", "invoice__party__display_name"), select_related=("invoice", "invoice__party"), ordering=("-sent_at",),
    ),
    Resource(
        "documents", "Socle", "Documents", "document", "foundation_documents.Document", "organization_id",
        (field("category.label", "Catégorie"), field("object_type", "Objet"), field("object_id", "Identifiant"), field("is_regulatory", "Réglementaire"), field("access_revoked", "Accès révoqué")),
        (field("category.label", "Catégorie"), field("object_type", "Objet"), field("object_id", "Identifiant"), field("is_regulatory", "Réglementaire"), field("access_revoked", "Accès révoqué"), field("created_at", "Créé le")),
        ("category__label", "object_type", "object_id"), select_related=("category",), ordering=("-created_at",),
    ),
    Resource(
        "workflows", "Socle", "Validations", "validation", "foundation_workflows.WorkflowInstance", "organization_id",
        (field("definition.code", "Workflow"), field("object_type", "Objet"), field("object_id", "Identifiant"), field("current_state.label", "État"), field("updated_at", "Mis à jour")),
        (field("definition.code", "Workflow"), field("definition.version", "Version"), field("object_type", "Objet"), field("object_id", "Identifiant"), field("current_state.label", "État"), field("requester_user.username", "Demandeur"), field("created_at", "Créé le"), field("updated_at", "Mis à jour")),
        ("definition__code", "object_type", "object_id", "current_state__label"), select_related=("definition", "current_state", "requester_user"), ordering=("-updated_at",),
    ),
    Resource(
        "notifications", "Socle", "Notifications", "notification", "foundation_notifications.Notification", "organization_id",
        (field("subject", "Objet"), field("recipient_user.username", "Destinataire"), field("channel", "Canal"), field("status", "Statut"), field("created_at", "Créée le")),
        (field("subject", "Objet"), field("body", "Message"), field("recipient_user.username", "Destinataire"), field("channel", "Canal"), field("status", "Statut"), field("idempotency_key", "Clé d’idempotence"), field("created_at", "Créée le")),
        ("subject", "body", "channel", "status", "recipient_user__username"), select_related=("recipient_user",), ordering=("-created_at",),
    ),
    Resource(
        "imports", "Socle", "Imports", "import", "foundation_data_transfer.ImportJob", "organization_id",
        (field("label", "Libellé"), field("status", "Statut"), field("all_or_nothing", "Tout ou rien"), field("created_at", "Créé le")),
        (field("label", "Libellé"), field("status", "Statut"), field("all_or_nothing", "Tout ou rien"), field("created_at", "Créé le")),
        ("label", "status"), ordering=("-created_at",),
    ),
    Resource(
        "exports", "Socle", "Exports", "export", "foundation_data_transfer.ExportJob", "organization_id",
        (field("label", "Libellé"), field("status", "Statut"), field("row_count", "Lignes"), field("created_at", "Créé le")),
        (field("label", "Libellé"), field("status", "Statut"), field("row_count", "Lignes"), field("created_at", "Créé le")),
        ("label", "status"), ordering=("-created_at",),
    ),
    Resource(
        "sequences", "Socle", "Séquences", "séquence", "foundation_sequences.SequenceCounter", "organization_id",
        (field("code", "Code"), field("period", "Période"), field("last_number", "Dernier numéro"), field("updated_at", "Mis à jour")),
        (field("code", "Code"), field("period", "Période"), field("last_number", "Dernier numéro"), field("created_at", "Créé le"), field("updated_at", "Mis à jour")),
        ("code", "period"), ordering=("code", "period"),
    ),
    Resource(
        "indicators", "Pilotage", "Indicateurs", "indicateur", "steering_indicators.IndicatorDefinition", "organization_id",
        (field("code", "Code"), field("label", "Libellé"), field("unit", "Unité"), field("frequency", "Fréquence"), field("owner", "Responsable")),
        (field("code", "Code"), field("label", "Libellé"), field("unit", "Unité"), field("source", "Source"), field("frequency", "Fréquence"), field("owner", "Responsable"), field("formula_code", "Formule"), field("formula_version", "Version"), field("created_at", "Créé le")),
        ("code", "label", "source", "owner"), ordering=("code",),
    ),
    Resource(
        "dashboards", "Pilotage", "Tableaux de bord", "tableau de bord", "steering_dashboards.Dashboard", "organization_id",
        (field("title", "Titre"), field("owner_user.username", "Propriétaire"), field("created_at", "Créé le")),
        (field("title", "Titre"), field("owner_user.username", "Propriétaire"), field("created_at", "Créé le")),
        ("title", "owner_user__username"), select_related=("owner_user",), ordering=("title",),
    ),
    Resource(
        "objectives", "Pilotage", "Objectifs", "objectif", "steering_objectives.Objective", "organization_id",
        (field("label", "Libellé"), field("owner", "Responsable"), field("horizon", "Horizon"), field("status", "Statut")),
        (field("label", "Libellé"), field("owner", "Responsable"), field("horizon", "Horizon"), field("status", "Statut"), field("created_at", "Créé le")),
        ("label", "owner", "status"), ordering=("horizon",),
    ),
    Resource(
        "budgets", "Pilotage", "Budgets", "budget", "steering_budgeting.Budget", "organization_id",
        (field("label", "Libellé"), field("period_start", "Début"), field("period_end", "Fin"), field("created_at", "Créé le")),
        (field("label", "Libellé"), field("period_start", "Début"), field("period_end", "Fin"), field("created_at", "Créé le")),
        ("label",), ordering=("-period_start",),
    ),
    Resource(
        "forecasts", "Pilotage", "Prévisions", "prévision", "steering_forecasts.Forecast", "organization_id",
        (field("label", "Libellé"), field("created_at", "Créée le")),
        (field("label", "Libellé"), field("created_at", "Créée le")),
        ("label",), ordering=("-created_at",),
    ),
    Resource(
        "reports", "Pilotage", "Rapports", "rapport", "steering_reports.Report", "organization_id",
        (field("code", "Code"), field("label", "Libellé"), field("dataset_key", "Jeu de données"), field("created_at", "Créé le")),
        (field("code", "Code"), field("label", "Libellé"), field("dataset_key", "Jeu de données"), field("created_at", "Créé le")),
        ("code", "label", "dataset_key"), ordering=("code",),
    ),
)

RESOURCE_BY_KEY = {resource.key: resource for resource in RESOURCES}


def get_resource(key: str) -> Resource:
    try:
        return RESOURCE_BY_KEY[key]
    except KeyError as exc:
        raise LookupError(f"Unknown portal resource: {key}") from exc


def navigation_groups() -> tuple[tuple[str, tuple[Resource, ...]], ...]:
    categories = ("Gestion", "Finance", "Pilotage", "Socle")
    return tuple((category, tuple(item for item in RESOURCES if item.category == category)) for category in categories)


def resolve_value(instance: Model, path: str) -> Any:
    value: Any = instance
    for part in path.split("."):
        if value is None:
            return None
        value = getattr(value, part, None)
    return value


def format_value(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, Decimal):
        return f"{value:,.2f}".replace(",", " ")
    return str(value)


def serialize_fields(instance: Model, fields: tuple[ResourceField, ...]) -> list[dict[str, Any]]:
    serialized = []
    for item in fields:
        raw_value = resolve_value(instance, item.path)
        serialized.append(
            {
                "label": item.label,
                "path": item.path,
                "raw": raw_value,
                "value": format_value(raw_value),
                "is_status": item.path.endswith("status") or item.path.endswith("is_active"),
            }
        )
    return serialized
