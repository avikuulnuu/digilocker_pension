# DigiLocker Issuer Service

DLTS-compliant Issuer API built with Django and PostgreSQL. Implements the DigiLocker Issuer API Specification v1.13 — serving digitally-signed documents to citizens via the DigiLocker platform.

## Features

- **Pull URI Request API** (`POST /issuer/pull-uri`) — single API as per v1.13 spec
- **Document Fetch** (`GET /issuer/document/<uri>`) — serve PDFs by URI
- **HMAC-SHA256 authentication** with constant-time comparison
- **KeyHash + timestamp validation** to prevent replay attacks
- **Lazy atomic URI generation** with `SELECT ... FOR UPDATE`
- **Immutability trigger** — PostgreSQL enforces URI/doc_id cannot be changed once set
- **Identity validation** — name/DOB matching in STRICT or LENIENT mode
- **File integrity checks** — SHA-256 checksums with configurable enforcement
- **Rate limiting** — 60 req/min per IP
- **Full audit logging** — access logs + integrity logs

---

## Prerequisites

- **Python** 3.10+
- **PostgreSQL** 14+
- **Git**

---

## Setup — macOS

### 1. Install dependencies

```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python and PostgreSQL
brew install python postgresql@16

# Start PostgreSQL
brew services start postgresql@16
```

### 2. Create the database

```bash
psql postgres -c "CREATE DATABASE digilocker;"
psql postgres -c "CREATE USER digilocker WITH PASSWORD 'digilocker';"
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE digilocker TO digilocker;"
psql postgres -c "ALTER DATABASE digilocker OWNER TO digilocker;"
psql postgres -c "ALTER USER digilocker CREATEDB;"  # needed for tests
```

### 3. Clone and set up the project

```bash
git clone <repo-url> digilocker
cd digilocker

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env with your values:
#   SECRET_KEY   — generate one: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
#   API_KEY      — shared secret from DigiLocker Partner Portal
#   ISSUER_ID    — your registered issuer ID
#   DATABASE_URL — postgres://digilocker:digilocker@localhost:5432/digilocker
```

### 5. Run migrations

```bash
source venv/bin/activate
python manage.py migrate
```

### 6. Create admin user (optional)

```bash
python manage.py createsuperuser
```

### 7. Run the server

```bash
python manage.py runserver 8000
```

The API is available at `http://127.0.0.1:8000/issuer/pull-uri`
Admin panel at `http://127.0.0.1:8000/admin/`

---

## Setup — Windows

### 1. Install dependencies

- Download and install **Python 3.10+** from https://www.python.org/downloads/ (check "Add to PATH")
- Download and install **PostgreSQL 16+** from https://www.postgresql.org/download/windows/
- During PostgreSQL install, note the password you set for the `postgres` user

### 2. Create the database

Open **pgAdmin** or **SQL Shell (psql)** and run:

```sql
CREATE DATABASE digilocker;
CREATE USER digilocker WITH PASSWORD 'digilocker';
GRANT ALL PRIVILEGES ON DATABASE digilocker TO digilocker;
ALTER DATABASE digilocker OWNER TO digilocker;
ALTER USER digilocker CREATEDB;
```

### 3. Clone and set up the project

Open **Command Prompt** or **PowerShell**:

```cmd
git clone <repo-url> digilocker
cd digilocker

:: Create virtual environment
python -m venv venv
venv\Scripts\activate

:: Install packages
pip install -r requirements.txt
```

### 4. Configure environment

```cmd
copy .env.example .env
:: Edit .env with a text editor — set SECRET_KEY, API_KEY, ISSUER_ID, DATABASE_URL
:: DATABASE_URL example: postgres://digilocker:digilocker@localhost:5432/digilocker
```

### 5. Run migrations

```cmd
venv\Scripts\activate
python manage.py migrate
```

### 6. Create admin user (optional)

```cmd
python manage.py createsuperuser
```

### 7. Run the server

```cmd
python manage.py runserver 8000
```

---

## Running Tests

### Unit tests (no server needed)

```bash
# macOS / Linux
source venv/bin/activate
python manage.py test tests -v2

# Windows
venv\Scripts\activate
python manage.py test tests -v2
```

### End-to-end tests (requires running server)

```bash
# Terminal 1: start the server
python manage.py runserver 8000

# Terminal 2: run e2e tests
python test_e2e.py
```

---

## Seeding Test Data

```bash
# Create a sample document file
echo "%PDF-1.4 test document" > data/docs/sample_ppo.pdf

# Seed via Django shell
python manage.py shell -c "
from issuer.models import Document
from datetime import date
import hashlib

with open('data/docs/sample_ppo.pdf','rb') as f:
    cksum = hashlib.sha256(f.read()).hexdigest()

Document.objects.get_or_create(
    authorization_number='PPO123456',
    document_type='PPO',
    defaults={
        'employee_name': 'Sunil Kumar',
        'employee_dob': date(1990, 12, 31),
        'file_relative_path': 'sample_ppo.pdf',
        'file_checksum': cksum,
    }
)
print('Done')
"
```

---

## Project Structure

```
digilocker/
├── .env                         # Local config (not committed)
├── .env.example                 # Config template
├── requirements.txt             # Python dependencies
├── manage.py
├── test_e2e.py                  # End-to-end test script
├── tests/                       # Test suite
│   ├── test_authentication.py   # HMAC, KeyHash, timestamp tests
│   ├── test_xml_parser.py       # XML parsing tests
│   ├── test_uri_service.py      # URI generation tests
│   ├── test_identity_validator.py # Name/DOB matching tests
│   ├── test_response_builder.py # Response XML construction tests
│   └── test_views.py            # Integration tests (API endpoints)
├── data/docs/                   # Document storage root
├── architecture/                # Design docs (PDF/DOCX/MD)
├── config/
│   ├── settings.py              # Django settings
│   ├── urls.py                  # Root URL config
│   └── wsgi.py
└── issuer/
    ├── models.py                # Document, AccessLog, IntegrityLog
    ├── views.py                 # API views (pull_uri, document_fetch)
    ├── urls.py                  # /issuer/pull-uri, /issuer/document/<uri>
    ├── admin.py                 # Django admin registration
    ├── authentication.py        # HMAC, KeyHash, timestamp verification
    ├── services/
    │   ├── xml_parser.py        # PullURIRequest XML parsing
    │   ├── uri_service.py       # Atomic URI generation
    │   ├── file_service.py      # File read + SHA-256 integrity
    │   ├── identity_validator.py# Name/DOB access control
    │   ├── document_service.py  # Orchestration: lookup → validate → serve
    │   └── response_builder.py  # PullURIResponse XML construction
    └── migrations/
        ├── 0001_initial.py
        └── 0002_immutability_trigger.py
```

---

## Configuration Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | *(required)* |
| `DEBUG` | Debug mode | `False` |
| `ALLOWED_HOSTS` | Comma-separated hostnames | `localhost,127.0.0.1` |
| `DATABASE_URL` | PostgreSQL connection string | *(required)* |
| `ISSUER_ID` | DigiLocker issuer code | *(required)* |
| `API_KEY` | Shared HMAC secret | *(required)* |
| `BASE_STORAGE_PATH` | Absolute path to document files | *(required)* |
| `INTEGRITY_MODE` | `STRICT` or `LOG_AND_SERVE` | `STRICT` |
| `IDENTITY_VALIDATION_MODE` | `STRICT` or `LENIENT` | `STRICT` |
| `MAX_FILE_SIZE_MB` | Max document size to serve | `10` |
| `TIMESTAMP_SKEW_SECONDS` | Allowed clock drift | `300` |

---

## Production Deployment

```bash
# Use Gunicorn behind Nginx
pip install gunicorn
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4

# Collect static files
python manage.py collectstatic --noinput
```

Set `DEBUG=False`, configure a strong `SECRET_KEY`, and enforce HTTPS via Nginx.
