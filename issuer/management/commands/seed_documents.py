import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from issuer.models import Document

DOCS = [
    {"authorization_number": "AUTH1001", "document_type": "GPF", "file_name": "IMLIAKUM_GPF.pdf", "employee_name": "Imliakum", "external_system_id": 1001},
    {"authorization_number": "AUTH1002", "document_type": "CPO", "file_name": "KIKWETNA_CPO.pdf", "employee_name": "Kitwena", "external_system_id": 1002},
    {"authorization_number": "AUTH1003", "document_type": "PPO", "file_name": "KIKWETNA_PPO.pdf", "employee_name": "Kitwena", "external_system_id": 1003},
    {"authorization_number": "AUTH1004", "document_type": "GPO", "file_name": "KIKWETNA_GPO.pdf", "employee_name": "Kitwena", "external_system_id": 1004},
]

class Command(BaseCommand):
    help = "Seed the documents table with test documents"

    def handle(self, *args, **options):
        base_path = os.environ.get("BASE_STORAGE_PATH") or os.getenv("BASE_STORAGE_PATH")
        if not base_path:
            self.stderr.write("BASE_STORAGE_PATH not set in environment.")
            return

        for doc in DOCS:
            file_path = os.path.join(base_path, doc["file_name"])
            if not os.path.exists(file_path):
                self.stderr.write(f"File not found: {file_path}")
                continue

            Document.objects.update_or_create(
                authorization_number=doc["authorization_number"],
                document_type=doc["document_type"],
                defaults={
                    "employee_name": doc["employee_name"],
                    "external_system_id": doc["external_system_id"],
                    "authorization_date": "01/01/2024",
                    "file_name": doc["file_name"],
                    "is_active": True,
                    "digilocker_enabled": True,
                    "created_at": timezone.now(),
                    "updated_at": timezone.now(),
                }
            )
            self.stdout.write(f"Seeded document: {doc['file_name']} for {doc['employee_name']}")
