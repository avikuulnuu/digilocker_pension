from django.db import migrations, models


def prepare_document_identifiers(apps, schema_editor):
    Document = apps.get_model("issuer", "Document")

    seen_authorization_numbers = set()
    seen_external_ids = set()

    for document in Document.objects.order_by("pk"):
        authorization_number = (document.authorization_number or "").strip()
        if not authorization_number:
            raise RuntimeError(
                f"Document {document.pk} is missing authorization_number; cannot enforce uniqueness."
            )
        if len(authorization_number) > 20:
            raise RuntimeError(
                f"Document {document.pk} has authorization_number longer than 20 characters."
            )
        if authorization_number in seen_authorization_numbers:
            raise RuntimeError(
                "Duplicate authorization_number values exist; clean the data before applying this migration."
            )
        seen_authorization_numbers.add(authorization_number)

        external_system_id = (document.external_system_id or "").strip()
        if (
            not external_system_id
            or len(external_system_id) > 20
            or external_system_id in seen_external_ids
        ):
            candidate = authorization_number
            if candidate in seen_external_ids:
                candidate = f"EXT{document.pk}"
            if len(candidate) > 20:
                candidate = f"EXT{document.pk}"
            if len(candidate) > 20:
                raise RuntimeError(
                    f"Document {document.pk} could not be assigned a valid external_system_id."
                )
            external_system_id = candidate

        document.external_system_id = external_system_id
        document.save(update_fields=["external_system_id"])
        seen_external_ids.add(external_system_id)


class Migration(migrations.Migration):

    dependencies = [
        ("issuer", "0005_accesslog_file_checksum_accesslog_file_path_and_more"),
    ]

    operations = [
        migrations.RunPython(
            prepare_document_identifiers,
            migrations.RunPython.noop,
        ),
        migrations.RemoveConstraint(
            model_name="document",
            name="uq_documents_business",
        ),
        migrations.AddField(
            model_name="document",
            name="treasury_code",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name="document",
            name="authorization_number",
            field=models.CharField(max_length=20, unique=True),
        ),
        migrations.AlterField(
            model_name="document",
            name="external_system_id",
            field=models.CharField(max_length=20, unique=True),
        ),
        migrations.AlterField(
            model_name="document",
            name="treasury_name",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
