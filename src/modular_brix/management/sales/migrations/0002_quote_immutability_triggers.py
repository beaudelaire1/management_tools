from django.db import migrations


def create_quote_immutability_triggers(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        CREATE OR REPLACE FUNCTION modular_brix_protect_quote_version()
        RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'draft' THEN
                    RAISE EXCEPTION 'A quote must be created as a draft and sent through the sending service.';
                END IF;
                RETURN NEW;
            END IF;
            IF TG_OP = 'DELETE' THEN
                IF OLD.status <> 'draft' THEN
                    RAISE EXCEPTION 'A sent quote version is immutable; create a revision instead.';
                END IF;
                RETURN OLD;
            END IF;

            IF OLD.status <> 'draft' AND (
                NEW.organization_id IS DISTINCT FROM OLD.organization_id
                OR NEW.party_id IS DISTINCT FROM OLD.party_id
                OR NEW.number IS DISTINCT FROM OLD.number
                OR NEW.version IS DISTINCT FROM OLD.version
                OR NEW.previous_version_id IS DISTINCT FROM OLD.previous_version_id
                OR NEW.currency IS DISTINCT FROM OLD.currency
                OR NEW.valid_until IS DISTINCT FROM OLD.valid_until
                OR NEW.total_excl_tax IS DISTINCT FROM OLD.total_excl_tax
                OR NEW.total_tax IS DISTINCT FROM OLD.total_tax
                OR NEW.total_incl_tax IS DISTINCT FROM OLD.total_incl_tax
            ) THEN
                RAISE EXCEPTION 'A sent quote version is immutable; create a revision instead.';
            END IF;

            IF NOT (
                (OLD.status = 'draft' AND NEW.status IN ('draft', 'sent'))
                OR (OLD.status = 'sent' AND NEW.status IN ('sent', 'accepted', 'rejected'))
                OR (OLD.status = 'accepted' AND NEW.status = 'accepted')
                OR (OLD.status = 'rejected' AND NEW.status = 'rejected')
            ) THEN
                RAISE EXCEPTION 'Illegal quote status transition.';
            END IF;

            IF OLD.status = 'draft' AND NEW.status = 'sent' AND (
                NEW.total_excl_tax IS NULL OR NEW.total_tax IS NULL OR NEW.total_incl_tax IS NULL
                OR NOT EXISTS (
                    SELECT 1 FROM management_sales_quoteline line WHERE line.quote_id = OLD.id
                )
            ) THEN
                RAISE EXCEPTION 'A sent quote requires totals and at least one line.';
            END IF;

            IF NEW.status = 'accepted' AND (
                btrim(NEW.acceptance_proof) = '' OR NEW.accepted_at IS NULL
            ) THEN
                RAISE EXCEPTION 'An accepted quote requires dated acceptance proof.';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS protect_quote_version ON management_sales_quote;
        CREATE TRIGGER protect_quote_version
        BEFORE INSERT OR UPDATE OR DELETE ON management_sales_quote
        FOR EACH ROW EXECUTE FUNCTION modular_brix_protect_quote_version();

        CREATE OR REPLACE FUNCTION modular_brix_protect_quote_line()
        RETURNS trigger AS $$
        DECLARE
            parent_status text;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                SELECT status INTO parent_status FROM management_sales_quote WHERE id = NEW.quote_id;
            ELSE
                SELECT status INTO parent_status FROM management_sales_quote WHERE id = OLD.quote_id;
            END IF;
            IF parent_status <> 'draft' THEN
                RAISE EXCEPTION 'Lines of a sent quote version are immutable.';
            END IF;
            IF TG_OP = 'UPDATE' AND NEW.quote_id IS DISTINCT FROM OLD.quote_id THEN
                SELECT status INTO parent_status FROM management_sales_quote WHERE id = NEW.quote_id;
                IF parent_status <> 'draft' THEN
                    RAISE EXCEPTION 'Lines of a sent quote version are immutable.';
                END IF;
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS protect_quote_line ON management_sales_quoteline;
        CREATE TRIGGER protect_quote_line
        BEFORE INSERT OR UPDATE OR DELETE ON management_sales_quoteline
        FOR EACH ROW EXECUTE FUNCTION modular_brix_protect_quote_line();
        """
    )


def drop_quote_immutability_triggers(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        DROP TRIGGER IF EXISTS protect_quote_line ON management_sales_quoteline;
        DROP FUNCTION IF EXISTS modular_brix_protect_quote_line();
        DROP TRIGGER IF EXISTS protect_quote_version ON management_sales_quote;
        DROP FUNCTION IF EXISTS modular_brix_protect_quote_version();
        """
    )


class Migration(migrations.Migration):
    dependencies = [
        ("management_sales", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_quote_immutability_triggers, drop_quote_immutability_triggers),
    ]
