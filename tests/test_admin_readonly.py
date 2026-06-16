"""Tests for read-only Django admin configuration."""

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from issuer.admin import AccessLogAdmin, DocumentAdmin, IntegrityLogAdmin
from issuer.models import AccessLog, Document, IntegrityLog

User = get_user_model()


class ReadOnlyAdminTest(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.request = RequestFactory().get("/admin/")
        self.request.user = User.objects.create_superuser(
            username="admin",
            email="admin@test",
            password="admin-pass-123",
        )
        self.admins = (
            DocumentAdmin(Document, self.site),
            AccessLogAdmin(AccessLog, self.site),
            IntegrityLogAdmin(IntegrityLog, self.site),
        )

    def test_no_add_change_or_delete_permissions(self):
        for model_admin in self.admins:
            with self.subTest(model=model_admin.model.__name__):
                self.assertFalse(model_admin.has_add_permission(self.request))
                self.assertFalse(model_admin.has_change_permission(self.request))
                self.assertFalse(model_admin.has_delete_permission(self.request))
                self.assertTrue(model_admin.has_view_permission(self.request))
