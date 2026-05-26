from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError

from issuer.manage_auth import MANAGE_PORTAL_PERMISSION
from issuer.models import Document

User = get_user_model()


class Command(BaseCommand):
    help = "Create a management console user (no Django admin / is_staff access)."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--email", default="")
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Read password from DJANGO_MANAGE_PORTAL_PASSWORD env var.",
        )

    def handle(self, *args, **options):
        username = options["username"].strip()
        if not username:
            raise CommandError("Username cannot be empty.")

        if User.objects.filter(username=username).exists():
            raise CommandError(f"User {username!r} already exists.")

        if options["no_input"]:
            import os

            password = os.environ.get("DJANGO_MANAGE_PORTAL_PASSWORD", "").strip()
            if not password:
                raise CommandError(
                    "Set DJANGO_MANAGE_PORTAL_PASSWORD when using --no-input."
                )
        else:
            password = self.get_pass()

        user = User.objects.create_user(
            username=username,
            email=options["email"] or "",
            password=password,
            is_staff=False,
            is_superuser=False,
        )
        perm = Permission.objects.get(
            codename="access_manage_portal",
            content_type=ContentType.objects.get_for_model(Document),
        )
        user.user_permissions.add(perm)
        self.stdout.write(
            self.style.SUCCESS(
                f"Created user {username!r} with permission {MANAGE_PORTAL_PERMISSION} "
                "(management console only; not Django admin)."
            )
        )

    def get_pass(self):
        from getpass import getpass

        p1 = getpass("Password: ")
        p2 = getpass("Password (again): ")
        if p1 != p2:
            raise CommandError("Passwords do not match.")
        if not p1:
            raise CommandError("Password cannot be empty.")
        return p1
