from django.db import migrations


def create_financial_immutability_triggers(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        CREATE OR REPLACE FUNCTION modular_brix_protect_issued_invoice()
        RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'draft' THEN
                    RAISE EXCEPTION 'An invoice must be created as a draft and issued through the issuance service.';
                END IF;
                RETURN NEW;
            END IF;
            IF OLD.status = 'issued' THEN
                RAISE EXCEPTION 'An issued invoice is immutable; correct it with a credit note.';
            END IF;
            IF TG_OP = 'UPDATE' AND NEW.status NOT IN ('draft', 'issued') THEN
                RAISE EXCEPTION 'Unsupported invoice status transition.';
            END IF;
            IF TG_OP = 'UPDATE' AND NEW.status = 'issued' AND (
                NEW.number = '' OR NEW.issue_date IS NULL OR NEW.due_date IS NULL
                OR NEW.total_excl_tax IS NULL OR NEW.total_tax IS NULL OR NEW.total_incl_tax IS NULL
                OR NOT EXISTS (
                    SELECT 1 FROM finance_billing_invoiceline line WHERE line.invoice_id = OLD.id
                )
            ) THEN
                RAISE EXCEPTION 'An issued invoice requires a number, dates, totals, and at least one line.';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS protect_issued_invoice ON finance_billing_invoice;
        CREATE TRIGGER protect_issued_invoice
        BEFORE INSERT OR UPDATE OR DELETE ON finance_billing_invoice
        FOR EACH ROW EXECUTE FUNCTION modular_brix_protect_issued_invoice();

        CREATE OR REPLACE FUNCTION modular_brix_protect_issued_invoice_line()
        RETURNS trigger AS $$
        DECLARE
            parent_status text;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                SELECT status INTO parent_status FROM finance_billing_invoice WHERE id = NEW.invoice_id;
            ELSE
                SELECT status INTO parent_status FROM finance_billing_invoice WHERE id = OLD.invoice_id;
            END IF;
            IF parent_status = 'issued' THEN
                RAISE EXCEPTION 'Lines of an issued invoice are immutable.';
            END IF;
            IF TG_OP = 'UPDATE' AND NEW.invoice_id IS DISTINCT FROM OLD.invoice_id THEN
                SELECT status INTO parent_status FROM finance_billing_invoice WHERE id = NEW.invoice_id;
                IF parent_status = 'issued' THEN
                    RAISE EXCEPTION 'Lines of an issued invoice are immutable.';
                END IF;
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS protect_issued_invoice_line ON finance_billing_invoiceline;
        CREATE TRIGGER protect_issued_invoice_line
        BEFORE INSERT OR UPDATE OR DELETE ON finance_billing_invoiceline
        FOR EACH ROW EXECUTE FUNCTION modular_brix_protect_issued_invoice_line();
        """
    )


def drop_financial_immutability_triggers(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        DROP TRIGGER IF EXISTS protect_issued_invoice_line ON finance_billing_invoiceline;
        DROP FUNCTION IF EXISTS modular_brix_protect_issued_invoice_line();
        DROP TRIGGER IF EXISTS protect_issued_invoice ON finance_billing_invoice;
        DROP FUNCTION IF EXISTS modular_brix_protect_issued_invoice();
        """
    )


class Migration(migrations.Migration):
    dependencies = [
        ("finance_billing", "0003_initial"),
    ]

    operations = [
        migrations.RunPython(create_financial_immutability_triggers, drop_financial_immutability_triggers),
    ]
