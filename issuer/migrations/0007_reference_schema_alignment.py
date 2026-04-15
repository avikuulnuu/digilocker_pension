import re

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.db import migrations, models


def _normalize_authorization_date(value):
    if not value:
        return "01/01/1970"
    value = value.strip()
    if re.match(r"^\d{2}/\d{2}/\d{4}$", value):
        return value
    if re.match(r"^\d{2}-\d{2}-\d{4}$", value):
        return value.replace("-", "/")
    return "01/01/1970"


def prepare_reference_alignment(apps, schema_editor):
    Document = apps.get_model("issuer", "Document")

    used_external_ids = set()
    fallback_base = 9_000_000_000_000_000_000

    for doc in Document.objects.order_by("pk"):
        # employee_name must be non-null/non-empty
        if not (doc.employee_name or "").strip():
            doc.employee_name = f"UNKNOWN-{doc.pk}"

        # authorization_date must be DD/MM/YYYY and non-null
        doc.authorization_date = _normalize_authorization_date(doc.authorization_date)

        # external_system_id must become BIGINT unique non-null
        raw_ext = str(doc.external_system_id or "").strip()
        candidate = None
        if raw_ext.isdigit():
            try:
                parsed = int(raw_ext)
                if parsed > 0:
                    candidate = parsed
            except ValueError:
                candidate = None

        if candidate is None or candidate in used_external_ids:
            candidate = fallback_base + doc.pk
            while candidate in used_external_ids:
                candidate += 1

        doc.external_system_id = str(candidate)
        used_external_ids.add(candidate)

        doc.save(update_fields=["employee_name", "authorization_date", "external_system_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("issuer", "0006_redesign_document_identifiers"),
    ]

    operations = [
        migrations.RunPython(
            prepare_reference_alignment,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="document",
            name="authorization_number",
            field=models.CharField(max_length=20),
        ),
        migrations.RenameField(
            model_name="document",
            old_name="doc_id",
            new_name="digilocker_doc_id",
        ),
        migrations.RenameField(
            model_name="document",
            old_name="uri",
            new_name="digilocker_uri",
        ),
        migrations.RenameField(
            model_name="document",
            old_name="file_relative_path",
            new_name="file_name",
        ),
        migrations.AlterField(
            model_name="document",
            name="employee_name",
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name="document",
            name="authorization_date",
            field=models.CharField(max_length=10),
        ),
        migrations.AlterField(
            model_name="document",
            name="file_checksum",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AlterField(
            model_name="document",
            name="external_system_id",
            field=models.BigIntegerField(unique=True),
        ),
        migrations.AlterModelTable(
            name="document",
            table="digilocker_documents",
        ),
        migrations.RemoveIndex(
            model_name="document",
            name="idx_documents_lookup",
        ),
        migrations.RemoveIndex(
            model_name="document",
            name="idx_documents_uri",
        ),
        migrations.RemoveIndex(
            model_name="document",
            name="idx_documents_doc_id",
        ),
        migrations.AddConstraint(
            model_name="document",
            constraint=models.UniqueConstraint(fields=("authorization_number", "document_type"), name="uq_document"),
        ),
        migrations.AddConstraint(
            model_name="document",
            constraint=models.CheckConstraint(condition=models.Q(("authorization_date__regex", r"^\d{2}/\d{2}/\d{4}$")), name="chk_authorization_date"),
        ),
        migrations.AddConstraint(
            model_name="document",
            constraint=models.CheckConstraint(condition=models.Q(("access_count__gte", 0)), name="chk_access_count"),
        ),
        migrations.AddConstraint(
            model_name="document",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("file_size_bytes__isnull", True), ("file_size_bytes__gt", 0), _connector="OR")), name="chk_file_size"),
        ),
        migrations.RemoveConstraint(
            model_name="document",
            name="chk_doc_id_uri_pair",
        ),
        migrations.AddConstraint(
            model_name="document",
            constraint=models.CheckConstraint(
                condition=models.Q(models.Q(("digilocker_doc_id__isnull", True), ("digilocker_uri__isnull", True)), models.Q(("digilocker_doc_id__isnull", False), ("digilocker_uri__isnull", False)), _connector="OR"),
                name="chk_doc_id_uri_pair",
            ),
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(condition=models.Q(("is_active", True), ("digilocker_enabled", True)), fields=["authorization_number", "document_type"], name="idx_auth_lookup"),
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(fields=["created_at"], name="idx_created"),
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(fields=["digilocker_uri"], name="idx_digilocker_uri"),
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(fields=["digilocker_doc_id"], name="idx_digilocker_doc_id"),
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(fields=["file_exists", "file_last_checked_at"], name="idx_file_verification"),
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(fields=["employee_mobile"], name="idx_mobile"),
        ),
        migrations.AddIndex(
            model_name="document",
            index=GinIndex(SearchVector("employee_name", config="english"), name="idx_employee_name_fts"),
        ),
        migrations.RunSQL(
            sql="""
            DROP TRIGGER IF EXISTS trg_prevent_identifier_update ON digilocker_documents;
            DROP FUNCTION IF EXISTS prevent_identifier_update();

            CREATE OR REPLACE FUNCTION prevent_identifier_update()
            RETURNS trigger AS $$
            BEGIN
                IF OLD.digilocker_uri IS NOT NULL AND NEW.digilocker_uri IS DISTINCT FROM OLD.digilocker_uri THEN
                    RAISE EXCEPTION 'URI is immutable once assigned';
                END IF;
                IF OLD.digilocker_doc_id IS NOT NULL AND NEW.digilocker_doc_id IS DISTINCT FROM OLD.digilocker_doc_id THEN
                    RAISE EXCEPTION 'doc_id is immutable once assigned';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER trg_prevent_identifier_update
            BEFORE UPDATE ON digilocker_documents
            FOR EACH ROW
            EXECUTE FUNCTION prevent_identifier_update();
            """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS trg_prevent_identifier_update ON digilocker_documents;
            DROP FUNCTION IF EXISTS prevent_identifier_update();

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
        ),
    ]
