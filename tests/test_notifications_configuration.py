import pytest

from modular_brix.foundation.configuration.models import Feature, SettingDefinition
from modular_brix.foundation.configuration.services import (
    disable_feature,
    enable_feature,
    get_setting,
    get_vocabulary_label,
    is_feature_enabled,
    set_setting,
    set_vocabulary_term,
)
from modular_brix.foundation.notifications.models import MessageTemplate
from modular_brix.foundation.notifications.services import (
    activate_template,
    deliver_notification,
    queue_notification,
    render_template,
)
from modular_brix.foundation.organizations.services import create_organization_with_default_establishment


def _make_org(suffix: str):
    return create_organization_with_default_establishment(
        slug=f"org-{suffix}",
        legal_name=f"Org {suffix}",
        legal_identifier=f"NC-{suffix}",
        country_code="FR",
    )


class SucceedingChannel:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, *, recipient: str, subject: str, body: str) -> None:
        self.sent.append({"recipient": recipient, "subject": subject, "body": body})


class FailingChannel:
    def send(self, *, recipient: str, subject: str, body: str) -> None:
        raise RuntimeError("provider unavailable")


@pytest.mark.django_db
def test_notification_queue_is_idempotent() -> None:
    org = _make_org("notif-idem")
    first = queue_notification(
        organization_id=str(org.id),
        recipient_user_id=None,
        channel="email",
        subject="Hello",
        body="Body",
        idempotency_key="evt-1",
    )
    second = queue_notification(
        organization_id=str(org.id),
        recipient_user_id=None,
        channel="email",
        subject="Hello again",
        body="Other body",
        idempotency_key="evt-1",
    )
    assert first.id == second.id  # no double notification on replay


@pytest.mark.django_db
def test_delivery_success_failure_and_retry_cap() -> None:
    org = _make_org("notif-deliv")
    notification = queue_notification(
        organization_id=str(org.id),
        recipient_user_id=None,
        channel="email",
        subject="S",
        body="B",
        idempotency_key="evt-2",
    )

    failing = FailingChannel()
    for _ in range(3):
        result = deliver_notification(
            notification_id=str(notification.id),
            channel_adapter=failing,
            recipient="x@example.test",
        )
        assert result.status == "failed"  # failure is visible and retryable

    with pytest.raises(ValueError, match="Maximum delivery attempts"):
        deliver_notification(
            notification_id=str(notification.id),
            channel_adapter=failing,
            recipient="x@example.test",
        )

    ok_notification = queue_notification(
        organization_id=str(org.id),
        recipient_user_id=None,
        channel="email",
        subject="S",
        body="B",
        idempotency_key="evt-3",
    )
    channel = SucceedingChannel()
    delivered = deliver_notification(
        notification_id=str(ok_notification.id),
        channel_adapter=channel,
        recipient="x@example.test",
    )
    assert delivered.status == "delivered"
    redelivered = deliver_notification(
        notification_id=str(ok_notification.id),
        channel_adapter=channel,
        recipient="x@example.test",
    )
    assert redelivered.status == "delivered"
    assert len(channel.sent) == 1  # idempotent: no double send


@pytest.mark.django_db
def test_template_variables_validated_before_activation() -> None:
    template = MessageTemplate.objects.create(
        code="welcome",
        subject_template="Bienvenue {name}",
        body_template="Bonjour {name}, votre organisation est {org}.",
        required_variables=["name"],
    )
    with pytest.raises(ValueError, match="variables mismatch"):
        activate_template(template_id=str(template.id))

    template.required_variables = ["name", "org"]
    template.save(update_fields=["required_variables"])
    activated = activate_template(template_id=str(template.id))
    assert activated.is_active is True

    with pytest.raises(ValueError, match="Missing template variables"):
        render_template(code="welcome", variables={"name": "Ada"})

    subject, body = render_template(code="welcome", variables={"name": "Ada", "org": "ACME"})
    assert subject == "Bienvenue Ada"
    assert "ACME" in body


@pytest.mark.django_db
def test_feature_dependencies_enforced() -> None:
    org = _make_org("features")
    Feature.objects.create(code="billing", label="Billing", depends_on=["parties"])
    Feature.objects.create(code="parties", label="Parties", depends_on=[])

    with pytest.raises(ValueError, match="requires 'parties'"):
        enable_feature(organization_id=str(org.id), feature_code="billing")

    enable_feature(organization_id=str(org.id), feature_code="parties")
    enable_feature(organization_id=str(org.id), feature_code="billing")
    assert is_feature_enabled(organization_id=str(org.id), feature_code="billing") is True

    disable_feature(organization_id=str(org.id), feature_code="billing")
    assert is_feature_enabled(organization_id=str(org.id), feature_code="billing") is False


@pytest.mark.django_db
def test_setting_type_validation_and_defaults() -> None:
    org = _make_org("settings")
    SettingDefinition.objects.create(code="max-lines", value_type="integer", default_value=100)
    SettingDefinition.objects.create(code="vat-rate", value_type="decimal", default_value="20.0")
    SettingDefinition.objects.create(code="dark-mode", value_type="boolean", default_value=False)
    SettingDefinition.objects.create(code="app-title", value_type="string", default_value="App")

    assert get_setting(organization_id=str(org.id), code="max-lines") == 100  # default fallback

    set_setting(organization_id=str(org.id), code="max-lines", value=500)
    assert get_setting(organization_id=str(org.id), code="max-lines") == 500

    with pytest.raises(ValueError, match="expects an integer"):
        set_setting(organization_id=str(org.id), code="max-lines", value="beaucoup")
    with pytest.raises(ValueError, match="expects a boolean"):
        set_setting(organization_id=str(org.id), code="dark-mode", value="yes")
    with pytest.raises(ValueError, match="expects a decimal"):
        set_setting(organization_id=str(org.id), code="vat-rate", value="abc")
    with pytest.raises(ValueError, match="expects a string"):
        set_setting(organization_id=str(org.id), code="app-title", value=42)


@pytest.mark.django_db
def test_vocabulary_terms_per_organization() -> None:
    org_a = _make_org("vocab-a")
    org_b = _make_org("vocab-b")
    set_vocabulary_term(organization_id=str(org_a.id), key="customer", label="Adhérent")

    assert get_vocabulary_label(organization_id=str(org_a.id), key="customer", default="Client") == "Adhérent"
    assert get_vocabulary_label(organization_id=str(org_b.id), key="customer", default="Client") == "Client"
