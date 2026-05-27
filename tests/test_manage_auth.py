"""Tests for management console authentication and authorization."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse

from issuer.models import Document

User = get_user_model()


def grant_manage_portal(user):
    perm = Permission.objects.get(
        codename="access_manage_portal",
        content_type=ContentType.objects.get_for_model(Document),
    )
    user.user_permissions.add(perm)


@override_settings(CAPTCHA_TEST_MODE=True)
class ManagePortalAuthTest(TestCase):
    def _post_login(self, username, password, *, follow=False):
        return self.client.post(
            self.login_url,
            {
                "username": username,
                "password": password,
                "captcha_0": "passed",
                "captcha_1": "passed",
            },
            follow=follow,
        )

    def setUp(self):
        self.hub_url = reverse("issuer:manage-hub")
        self.login_url = reverse("issuer:manage-login")

        self.authorized = User.objects.create_user(
            username="ops_user",
            password="test-pass-123",
        )
        grant_manage_portal(self.authorized)

        self.other = User.objects.create_user(
            username="no_access",
            password="test-pass-123",
        )

    def test_anonymous_manage_hub_redirects_to_login(self):
        response = self.client.get(self.hub_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/issuer/manage/login/", response["Location"])

    def test_user_without_permission_gets_403(self):
        self.client.force_login(self.other)
        response = self.client.get(self.hub_url)
        self.assertEqual(response.status_code, 403)

    def test_user_with_permission_can_access_hub(self):
        self.client.force_login(self.authorized)
        response = self.client.get(self.hub_url)
        self.assertEqual(response.status_code, 200)

    def test_superuser_can_access_hub_without_explicit_permission(self):
        admin = User.objects.create_superuser(
            username="admin",
            email="admin@test",
            password="admin-pass-123",
        )
        self.client.force_login(admin)
        response = self.client.get(self.hub_url)
        self.assertEqual(response.status_code, 200)

    def test_login_without_permission_shows_error(self):
        response = self._post_login("no_access", "test-pass-123", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "does not have access to the management console",
        )
        self.assertFalse(self.client.session.get("_auth_user_id"))

    def test_login_with_permission_redirects_to_hub(self):
        response = self._post_login("ops_user", "test-pass-123")
        self.assertRedirects(response, self.hub_url, fetch_redirect_response=False)

    def test_decode_pdf_requires_auth(self):
        url = reverse("issuer:decode-pdf-tool")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/issuer/manage/login/", response["Location"])

    def test_logout_clears_session(self):
        self.client.force_login(self.authorized)
        response = self.client.post(reverse("issuer:manage-logout"))
        self.assertRedirects(response, self.login_url, fetch_redirect_response=False)
        response = self.client.get(self.hub_url)
        self.assertEqual(response.status_code, 302)
