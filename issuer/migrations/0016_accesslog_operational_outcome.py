from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("issuer", "0015_document_manage_portal_permission"),
    ]

    operations = [
        migrations.AddField(
            model_name="accesslog",
            name="http_status_code",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="accesslog",
            name="outcome_class",
            field=models.CharField(
                choices=[
                    ("HANDLED", "Handled outcome"),
                    ("SERVICE_FAILURE", "Service failure"),
                    ("REJECTED", "Rejected request"),
                    ("PENDING", "Pending"),
                    ("LEGACY_UNCLASSIFIED", "Legacy or unclassified"),
                ],
                default="LEGACY_UNCLASSIFIED",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="accesslog",
            name="processing_stage",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="accesslog",
            name="reason_code",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
    ]