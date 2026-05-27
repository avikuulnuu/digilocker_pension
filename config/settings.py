import sys

import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    ADMIN_IP_ALLOWLIST=(list, []),
    TRUST_X_FORWARDED_FOR=(bool, False),
    INTEGRITY_MODE=(str, "STRICT"),
    IDENTITY_VALIDATION_MODE=(str, "STRICT"),
    LENIENT_NAME_MATCH_THRESHOLD=(float, 0.70),
    MAX_FILE_SIZE_MB=(int, 10),
    REQUEST_TIMEOUT_MS=(int, 5000),
    TIMESTAMP_SKEW_SECONDS=(int, 300),
    ISSUER_VERBOSE_LOGGING=(bool, False),
    MANAGE_LOGIN_MAX_FAILURES=(int, 5),
    MANAGE_LOGIN_LOCKOUT_MINUTES=(int, 15),
    SECURE_SSL_REDIRECT=(bool, True),
    SESSION_COOKIE_SECURE=(bool, True),
    MANAGE_DECODE_PDF_ENABLED=(bool, False),
    MANAGE_DECODE_PDF_TTL_SECONDS=(int, 900),
    MANAGE_DECODE_PDF_MAX_SESSION_ITEMS=(int, 3),
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
    "captcha",
    "issuer",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.ip_allowlist.RestrictedAdminIPMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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
                "issuer.context_processors.manage_portal",
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

# --- Admin / manage console network restriction ---
TRUST_X_FORWARDED_FOR = env("TRUST_X_FORWARDED_FOR")
RESTRICTED_ADMIN_IP_ALLOWLIST = env.list("ADMIN_IP_ALLOWLIST")
if not RESTRICTED_ADMIN_IP_ALLOWLIST and (DEBUG or "test" in sys.argv):
    RESTRICTED_ADMIN_IP_ALLOWLIST = ["127.0.0.1", "::1"]

# --- DigiLocker Issuer Configuration ---
DIGILOCKER_ISSUER_ID = env("ISSUER_ID")
DIGILOCKER_API_KEY = env("API_KEY")
DIGILOCKER_BASE_STORAGE_PATH = env("BASE_STORAGE_PATH")
DIGILOCKER_INTEGRITY_MODE = env("INTEGRITY_MODE")
DIGILOCKER_IDENTITY_VALIDATION_MODE = env("IDENTITY_VALIDATION_MODE")
DIGILOCKER_LENIENT_NAME_MATCH_THRESHOLD = env("LENIENT_NAME_MATCH_THRESHOLD")
DIGILOCKER_MAX_FILE_SIZE_MB = env("MAX_FILE_SIZE_MB")
DIGILOCKER_REQUEST_TIMEOUT_MS = env("REQUEST_TIMEOUT_MS")
DIGILOCKER_TIMESTAMP_SKEW_SECONDS = env("TIMESTAMP_SKEW_SECONDS")

ISSUER_VERBOSE_LOGGING = env("ISSUER_VERBOSE_LOGGING")

# --- Management console login protection ---
MANAGE_LOGIN_MAX_FAILURES = env("MANAGE_LOGIN_MAX_FAILURES")
MANAGE_LOGIN_LOCKOUT_MINUTES = env("MANAGE_LOGIN_LOCKOUT_MINUTES")
CAPTCHA_CHALLENGE_FUNCT = "captcha.helpers.math_challenge"
CAPTCHA_FONT_SIZE = 28
CAPTCHA_LENGTH = 4

# --- Manage portal: Base64 PDF decoder (off by default in production) ---
MANAGE_DECODE_PDF_ENABLED = env("MANAGE_DECODE_PDF_ENABLED")
MANAGE_DECODE_PDF_TTL_SECONDS = env("MANAGE_DECODE_PDF_TTL_SECONDS")
MANAGE_DECODE_PDF_MAX_SESSION_ITEMS = env("MANAGE_DECODE_PDF_MAX_SESSION_ITEMS")

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

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "issuer": {
            "handlers": ["console"],
            "level": "DEBUG" if (DEBUG or ISSUER_VERBOSE_LOGGING) else "INFO",
            "propagate": False,
        },
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
        },
    },
}
