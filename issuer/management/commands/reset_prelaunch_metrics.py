from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from issuer.models import AccessLog, Document, IntegrityLog


CONFIRMATION = "RESET-PRELAUNCH-METRICS"


class Command(BaseCommand):
    help = (
        "Preview or clear pre-launch API/integrity logs and reset document "
        "access counters without deleting document records."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            default="",
            help=f"Required destructive confirmation value: {CONFIRMATION}",
        )

    def handle(self, *args, **options):
        access_logs = AccessLog.objects.count()
        integrity_logs = IntegrityLog.objects.count()
        documents_with_access = Document.objects.filter(
            access_count__gt=0
        ).count()

        self.stdout.write(f"Access logs: {access_logs}")
        self.stdout.write(f"Integrity logs: {integrity_logs}")
        self.stdout.write(
            f"Document access counters to reset: {documents_with_access}"
        )

        confirmation = options["confirm"]
        if not confirmation:
            self.stdout.write(
                "Preview only. No data changed. Run again with "
                f"--confirm {CONFIRMATION} to reset pre-launch metrics."
            )
            return
        if confirmation != CONFIRMATION:
            raise CommandError("Invalid confirmation value. No data changed.")

        with transaction.atomic():
            AccessLog.objects.all().delete()
            IntegrityLog.objects.all().delete()
            Document.objects.update(access_count=0, last_accessed_at=None)

        self.stdout.write(
            self.style.SUCCESS(
                "Pre-launch metrics reset. Document records were preserved."
            )
        )