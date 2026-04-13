"""Add PostgreSQL trigger to prevent URI/doc_id mutation after assignment."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("issuer", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE FUNCTION prevent_identifier_update()
            RETURNS trigger AS $$
            BEGIN
                IF OLD.uri IS NOT NULL AND NEW.uri IS DISTINCT FROM OLD.uri THEN
                    RAISE EXCEPTION 'URI is immutable once assigned';
                END IF;
                IF OLD.doc_id IS NOT NULL AND NEW.doc_id IS DISTINCT FROM OLD.doc_id THEN
                    RAISE EXCEPTION 'doc_id is immutable once assigned';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER trg_prevent_identifier_update
            BEFORE UPDATE ON documents
            FOR EACH ROW
            EXECUTE FUNCTION prevent_identifier_update();
            """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS trg_prevent_identifier_update ON documents;
            DROP FUNCTION IF EXISTS prevent_identifier_update();
            """,
        ),
    ]
