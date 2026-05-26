from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("issuer", "0014_alter_accesslog_document_type"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="document",
            options={
                "permissions": [
                    (
                        "access_manage_portal",
                        "Can access the issuer management console",
                    ),
                ],
            },
        ),
    ]
