from django.urls import path

from .views import (
    HomeView,
    OrganizationPickerView,
    ResourceDetailView,
    ResourceListView,
    invoice_issue_view,
    lead_create,
    order_invoice_view,
    party_create,
    payment_allocate_view,
    payment_create_view,
    quote_accept_view,
    quote_convert_view,
    quote_create_view,
    quote_line_create,
    quote_send_view,
)

app_name = "portal"

urlpatterns = [
    path("", OrganizationPickerView.as_view(), name="organization-picker"),
    path("<slug:org_slug>/", HomeView.as_view(), name="home"),
    path("<slug:org_slug>/resources/<slug:resource_key>/", ResourceListView.as_view(), name="resource-list"),
    path("<slug:org_slug>/resources/<slug:resource_key>/<uuid:pk>/", ResourceDetailView.as_view(), name="resource-detail"),
    path("<slug:org_slug>/parties/new/", party_create, name="party-create"),
    path("<slug:org_slug>/leads/new/", lead_create, name="lead-create"),
    path("<slug:org_slug>/quotes/new/", quote_create_view, name="quote-create"),
    path("<slug:org_slug>/quotes/<uuid:quote_id>/lines/new/", quote_line_create, name="quote-line-create"),
    path("<slug:org_slug>/quotes/<uuid:quote_id>/send/", quote_send_view, name="quote-send"),
    path("<slug:org_slug>/quotes/<uuid:quote_id>/accept/", quote_accept_view, name="quote-accept"),
    path("<slug:org_slug>/quotes/<uuid:quote_id>/convert/", quote_convert_view, name="quote-convert"),
    path("<slug:org_slug>/orders/<uuid:order_id>/invoice/", order_invoice_view, name="order-invoice"),
    path("<slug:org_slug>/invoices/<uuid:invoice_id>/issue/", invoice_issue_view, name="invoice-issue"),
    path("<slug:org_slug>/payments/new/", payment_create_view, name="payment-create"),
    path("<slug:org_slug>/payments/<uuid:payment_id>/allocate/", payment_allocate_view, name="payment-allocate"),
]
