from django.db import migrations


def create_append_only_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        CREATE OR REPLACE FUNCTION foundation_audit_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Audit events are append-only.';
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_foundation_audit_append_only
        BEFORE UPDATE OR DELETE ON foundation_audit_auditevent
        FOR EACH ROW EXECUTE FUNCTION foundation_audit_append_only();
        """
    )


def drop_append_only_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        DROP TRIGGER IF EXISTS trg_foundation_audit_append_only ON foundation_audit_auditevent;
        DROP FUNCTION IF EXISTS foundation_audit_append_only();
        """
    )


class Migration(migrations.Migration):
    dependencies = [
        ("foundation_audit", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_append_only_trigger, drop_append_only_trigger),
    ]
