import sys
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    ADMIN_IP_ALLOWLIST=(list, []),
    TRUST_X_FORWARDED_FOR=(bool, False),
    TRUSTED_PROXY_IPS=(list, ["127.0.0.1", "::1"]),
    INTEGRITY_MODE=(str, "STRICT"),
    IDENTITY_VALIDATION_MODE=(str, "STRICT"),
    LENIENT_NAME_MATCH_THRESHOLD=(float, 0.70),
    MAX_FILE_SIZE_MB=(int, 10),
    REQUEST_TIMEOUT_MS=(int, 5000),
    TIMESTAMP_SKEW_SECONDS=(int, 300),
    ISSUER_VERBOSE_LOGGING=(bool, False),
    ISSUER_API_LOG_PATH=(str, ""),
    ISSUER_API_LOG_MAX_BYTES=(int, 10 * 1024 * 1024),
    ISSUER_API_LOG_BACKUP_COUNT=(int, 10),
    MANAGE_LOGIN_MAX_FAILURES=(int, 5),
    MANAGE_LOGIN_LOCKOUT_MINUTES=(int, 15),
    SECURE_SSL_REDIRECT=(bool, True),
    SESSION_COOKIE_SECURE=(bool, True),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "axes",
    "captcha",
    "issuer",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.ip_allowlist.RestrictedAdminIPMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "axes.middleware.AxesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

database_url = env("DATABASE_URL", default=None)
if database_url:
    DATABASES = {
        "default": env.db("DATABASE_URL"),
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME"),
            "USER": env("DB_USER"),
            "PASSWORD": env("DB_PASSWORD"),
            "HOST": env("DB_HOST"),
            "PORT": env("DB_PORT"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Management console auth ---
LOGIN_URL = "/issuer/manage/login/"
LOGIN_REDIRECT_URL = "/issuer/manage/"
LOGOUT_REDIRECT_URL = "/issuer/manage/login/"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# --- Admin / manage console network restriction ---
TRUST_X_FORWARDED_FOR = env("TRUST_X_FORWARDED_FOR")
TRUSTED_PROXY_IPS = env.list("TRUSTED_PROXY_IPS")
RESTRICTED_ADMIN_IP_ALLOWLIST = env.list("ADMIN_IP_ALLOWLIST")
if not RESTRICTED_ADMIN_IP_ALLOWLIST and (DEBUG or "test" in sys.argv):
    RESTRICTED_ADMIN_IP_ALLOWLIST = ["127.0.0.1", "::1"]
elif DEBUG or "test" in sys.argv:
    for _localhost in ("127.0.0.1", "::1"):
        if _localhost not in RESTRICTED_ADMIN_IP_ALLOWLIST:
            RESTRICTED_ADMIN_IP_ALLOWLIST.append(_localhost)

from config.ip_allowlist import parse_ip_allowlist

if RESTRICTED_ADMIN_IP_ALLOWLIST and not parse_ip_allowlist(RESTRICTED_ADMIN_IP_ALLOWLIST):
    import warnings

    warnings.warn(
        "ADMIN_IP_ALLOWLIST is set but no entries could be parsed; "
        "/admin/ and /issuer/manage/ will be blocked for all clients.",
        stacklevel=1,
    )

if not DEBUG and RESTRICTED_ADMIN_IP_ALLOWLIST and not TRUST_X_FORWARDED_FOR:
    import warnings

    warnings.warn(
        "TRUST_X_FORWARDED_FOR is False while DEBUG is False. If Gunicorn runs behind "
        "nginx, the allowlist middleware usually sees 127.0.0.1 (the proxy), not your "
        "workstation IP. Set TRUST_X_FORWARDED_FOR=True and configure nginx to pass "
        "X-Forwarded-For or X-Real-IP.",
        stacklevel=1,
    )

# --- DigiLocker Issuer Configuration ---
DIGILOCKER_ISSUER_ID = env("ISSUER_ID")
DIGILOCKER_API_KEY = env("API_KEY")
DIGILOCKER_BASE_STORAGE_PATH = env("BASE_STORAGE_PATH")
DIGILOCKER_GPF_STORAGE_PATH = env("GPF_STORAGE_PATH", default=DIGILOCKER_BASE_STORAGE_PATH)
DIGILOCKER_INTEGRITY_MODE = env("INTEGRITY_MODE")
DIGILOCKER_IDENTITY_VALIDATION_MODE = env("IDENTITY_VALIDATION_MODE")
DIGILOCKER_LENIENT_NAME_MATCH_THRESHOLD = env("LENIENT_NAME_MATCH_THRESHOLD")
DIGILOCKER_MAX_FILE_SIZE_MB = env("MAX_FILE_SIZE_MB")
DIGILOCKER_REQUEST_TIMEOUT_MS = env("REQUEST_TIMEOUT_MS")
DIGILOCKER_TIMESTAMP_SKEW_SECONDS = env("TIMESTAMP_SKEW_SECONDS")

# Certificate metadata (DataContent) — IssuedBy organization defaults
DIGILOCKER_CERT_LANGUAGE = env("CERT_LANGUAGE", default="99")
DIGILOCKER_CERT_ISSUER_NAME = env(
    "CERT_ISSUER_NAME",
    default="PAG, Nagaland",
)
DIGILOCKER_CERT_ISSUER_ORG_TYPE = env("CERT_ISSUER_ORG_TYPE", default="SG")
DIGILOCKER_CERT_ISSUER_ADDRESS_TYPE = env("CERT_ISSUER_ADDRESS_TYPE", default="Own Building")
DIGILOCKER_CERT_ISSUER_ADDRESS_LINE1 = env("CERT_ISSUER_ADDRESS_LINE1", default="Kohima")
DIGILOCKER_CERT_ISSUER_ADDRESS_PIN = env("CERT_ISSUER_ADDRESS_PIN", default="797001")
DIGILOCKER_CERT_ISSUER_ADDRESS_STATE = env("CERT_ISSUER_ADDRESS_STATE", default="Nagaland")
DIGILOCKER_CERT_ISSUER_ADDRESS_COUNTRY = env("CERT_ISSUER_ADDRESS_COUNTRY", default="IN")

ISSUER_VERBOSE_LOGGING = env("ISSUER_VERBOSE_LOGGING")
ISSUER_API_LOG_PATH = env("ISSUER_API_LOG_PATH")
ISSUER_API_LOG_MAX_BYTES = env("ISSUER_API_LOG_MAX_BYTES")
ISSUER_API_LOG_BACKUP_COUNT = env("ISSUER_API_LOG_BACKUP_COUNT")

# --- Management console login protection ---
MANAGE_LOGIN_MAX_FAILURES = env("MANAGE_LOGIN_MAX_FAILURES")
MANAGE_LOGIN_LOCKOUT_MINUTES = env("MANAGE_LOGIN_LOCKOUT_MINUTES")
AXES_HANDLER = "axes.handlers.database.AxesDatabaseHandler"
AXES_FAILURE_LIMIT = MANAGE_LOGIN_MAX_FAILURES
AXES_COOLOFF_TIME = timedelta(minutes=MANAGE_LOGIN_LOCKOUT_MINUTES)
AXES_LOCKOUT_PARAMETERS = ["ip_address"]
AXES_CLIENT_IP_CALLABLE = "config.ip_allowlist.get_axes_client_ip"
AXES_WHITELIST_CALLABLE = "issuer.manage_login_security.is_outside_manage_login"
AXES_LOCKOUT_CALLABLE = "issuer.manage_login_security.axes_lockout_response"
AXES_RESET_ON_SUCCESS = True
AXES_DISABLE_ACCESS_LOG = True
AXES_ENABLE_ACCESS_FAILURE_LOG = False
AXES_SENSITIVE_PARAMETERS = ["username", "captcha_0", "captcha_1", "csrfmiddlewaretoken"]
CAPTCHA_CHALLENGE_FUNCT = "captcha.helpers.math_challenge"
CAPTCHA_IMAGE_SIZE = (220, 70)
CAPTCHA_FONT_SIZE = 36
CAPTCHA_LENGTH = 4
CAPTCHA_LETTER_ROTATION = (-8, 8)
CAPTCHA_NOISE_FUNCTIONS = ("captcha.helpers.noise_dots",)
CAPTCHA_FILTER_FUNCTIONS = ()
CAPTCHA_FOREGROUND_COLOR = "#111827"
CAPTCHA_BACKGROUND_COLOR = "#ffffff"
# django-simple-captcha caches this at import time; must be set here for manage.py test.
CAPTCHA_TEST_MODE = "test" in sys.argv

# --- Security Hardening ---
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
if not DEBUG:
    # Trust X-Forwarded-Proto from Nginx when TLS terminates at the proxy.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT")
    SESSION_COOKIE_SECURE = env("SESSION_COOKIE_SECURE")
    CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
    if SECURE_SSL_REDIRECT:
        SECURE_HSTS_SECONDS = 31536000
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SECURE_HSTS_PRELOAD = True

from config.logging_config import build_logging_config

LOGGING = build_logging_config(
    debug=DEBUG,
    verbose=ISSUER_VERBOSE_LOGGING,
    log_path=ISSUER_API_LOG_PATH,
    max_bytes=ISSUER_API_LOG_MAX_BYTES,
    backup_count=ISSUER_API_LOG_BACKUP_COUNT,
    base_dir=BASE_DIR,
    running_tests="test" in sys.argv,
)
