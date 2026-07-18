import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Organization",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("slug", models.SlugField(max_length=80, unique=True)),
                ("legal_name", models.CharField(max_length=255)),
                ("legal_identifier", models.CharField(max_length=64)),
                ("country_code", models.CharField(max_length=2)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="Establishment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=32)),
                ("display_name", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="establishments",
                        to="foundation_organizations.organization",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="organization",
            constraint=models.UniqueConstraint(
                fields=("legal_identifier", "country_code"),
                name="uq_org_legal_identifier_country",
            ),
        ),
        migrations.AddConstraint(
            model_name="establishment",
            constraint=models.UniqueConstraint(
                fields=("organization", "code"),
                name="uq_establishment_org_code",
            ),
        ),
    ]
