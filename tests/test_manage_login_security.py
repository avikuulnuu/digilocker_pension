"""Tests for manage portal CAPTCHA login and failed-attempt lockout."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from axes.models import AccessAttempt
from captcha.models import CaptchaStore

from issuer.models import Document
from issuer.manage_login_security import get_failure_count

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
    AXES_FAILURE_LIMIT=3,
    AXES_COOLOFF_TIME=timedelta(minutes=15),
)
class ManageLoginSecurityTest(TestCase):
    def setUp(self):
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

    def test_invalid_captcha_does_not_increment_failure_counter(self):
        response = self.client.post(
            self.login_url,
            {
                "username": "ops_user",
                "password": "wrong",
                "captcha_0": "missing",
                "captcha_1": "wrong",
            },
        )
        request = RequestFactory().get("/", REMOTE_ADDR="127.0.0.1")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid CAPTCHA")
        self.assertEqual(get_failure_count(request), 0)

    def test_login_page_provides_captcha_refresh_control(self):
        response = self.client.get(self.login_url)

        self.assertContains(response, "Refresh security check")
        self.assertContains(response, reverse("captcha-refresh"))

    def test_captcha_image_returns_png(self):
        key = CaptchaStore.generate_key()

        response = self.client.get(reverse("captcha-image", args=[key]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertTrue(response.content.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_successful_login_clears_failure_counter(self):
        self._post_login("ops_user", "wrong")
        self._post_login("ops_user", "test-pass-123")
        response = self.client.get(reverse("issuer:manage-hub"))
        self.assertEqual(response.status_code, 200)

    def test_failed_login_increments_counter_message(self):
        response = self._post_login("ops_user", "wrong")
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Sign-in failed. 1 of 3 failed attempts; 2 attempt(s) remaining "
            "before a 15-minute lockout.",
            count=1,
        )
        self.assertNotContains(response, "Failed sign-in attempts from your network")
        self.assertNotContains(
            response,
            "Please enter a correct username and password",
        )
        self.assertEqual(AccessAttempt.objects.get().failures_since_start, 1)

    def test_lockout_after_max_failures(self):
        for _ in range(3):
            response = self._post_login("ops_user", "wrong")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many failed sign-in attempts")

        response = self._post_login("ops_user", "test-pass-123")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many failed sign-in attempts")
