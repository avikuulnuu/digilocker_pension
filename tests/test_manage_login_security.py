"""Tests for manage portal CAPTCHA login and failed-attempt lockout."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
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


@override_settings(
    CAPTCHA_TEST_MODE=True,
    MANAGE_LOGIN_MAX_FAILURES=3,
    MANAGE_LOGIN_LOCKOUT_MINUTES=15,
)
class ManageLoginSecurityTest(TestCase):
    def setUp(self):
        cache.clear()
        self.login_url = reverse("issuer:manage-login")
        self.user = User.objects.create_user(username="ops_user", password="test-pass-123")
        grant_manage_portal(self.user)

    def _post_login(self, username, password):
        return self.client.post(
            self.login_url,
            {
                "username": username,
                "password": password,
                "captcha_0": "passed",
                "captcha_1": "passed",
            },
        )

    def test_login_requires_captcha_field(self):
        response = self.client.post(
            self.login_url,
            {"username": "ops_user", "password": "test-pass-123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Security check")

    def test_successful_login_clears_failure_counter(self):
        self._post_login("ops_user", "wrong")
        self._post_login("ops_user", "test-pass-123")
        response = self.client.get(reverse("issuer:manage-hub"))
        self.assertEqual(response.status_code, 200)

    def test_failed_login_increments_counter_message(self):
        response = self._post_login("ops_user", "wrong")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "attempt(s) remaining")

    def test_lockout_after_max_failures(self):
        for _ in range(3):
            self._post_login("ops_user", "wrong")
        response = self._post_login("ops_user", "test-pass-123")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many failed sign-in attempts")
