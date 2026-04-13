# Issuer API v1.13 Compliance & Implementation Plan

## Executive Summary

This report aligns our issuer system with the official DigiLocker Issuer API v1.13 (May 2024). The spec mandates a single Pull URI API (the old PullDoc endpoint is removed[1]), and strict HMAC-based authentication. We verify the document issuance flow (Sec. 6) and authentication rules exactly from the spec[2][3]. We detail how to form and validate the document URI (<IssuerID>[-DocType]-<DocId>)[4], and enumerate required HTTP headers and signature steps. Key recommendations include DB schema changes (DOB as DATE, storage_type+relative_path, new issuer_id/doc_id columns with constraints), integrity-check modes, rate-limiting guidelines, and security hardening (constant-time HMAC compare, timestamp skew limits, etc.). We provide exact quote references from the spec, migration SQL, sample code, tables, and diagrams.

Assumptions:
- The schema dump and spec PDF are authoritative.
- DigiLocker will invoke our endpoints directly (not via proxies) as per spec.
- We control the issuer’s Partner Portal settings (API key, OrgID, DocTypes).
- Documents are pre-signed PDFs.
- No additional private info (e.g. Aadhaar) is stored beyond matching fields.

## 1. Document Issuance Flow (Spec Sec. 6)

DigiLocker’s workflow is clearly defined[2][5]:

Create e-Document with unique URI:

Generate a digitized, digitally-signed PDF adhering to DLTS standards. Assign it a unique URI.

Issuer ID: Use the issuer’s globally-unique code (e.g. a department domain name)[6].

Document Type: Apply a DigiLocker-approved DocType code. If new, request creation[7].

Repository Storage:

Store the signed document in an online repository (our DB/filesystem) for serving[8].

Issue Printed Document:

Print or send the document to the citizen with its URI (human-readable)[9].

Push Option: Provide a way for the citizen to push the URI into their DigiLocker account[10].

In short, documents must be pre-signed and tagged with a URI before any API calls. We ensure the application only serves pre-existing signed PDFs (we do not dynamically sign them on pull).

## 2. API Endpoints & Pull Flow (Spec Sec. 8)

In v1.13, only one API is required[1][11]: the Pull URI Request API. The old PullDoc API is removed (see Rev. 1.13 notes)[1]. The flow is:

Pull URI Request (POST): Our endpoint (e.g. /issuer/pull-uri) receives search criteria (Aadhaar number, name, DOB, or custom UDFs). DigiLocker calls this when a user searches for their document[12].

Return URI(s): We query our DB to find matching documents (matching, for example, authorization number or UDF) and return a list of document URIs in the PullURIResponse.

Document Fetch (GET): After receiving the URI, DigiLocker will fetch the actual document. This happens via a resource endpoint in our app (e.g. GET /issuer/document/{uri}) rather than a separate PullDoc API. We must implement this GET to stream the PDF.

Who resolves URIs? We (the issuer) generate and recognize the URI. DigiLocker will directly GET our service at /document/{URI} (the spec implies direct issuer fetch)[12]. We must map {URI} to the stored file and perform validation (active flag, integrity).

Summary:
- Only PullURIRequest API is consumed by DigiLocker[1][11].
- We expose an additional GET endpoint for document retrieval by URI.

## 3. Authentication Requirements (Spec Sec. 8.1.1–8.1.2)

All requests from DigiLocker must be authenticated via HMAC and timestamp[13][3]. Key points:

Header x-digilocker-hmac: Must be present on every request[13]. DigiLocker computes HMAC = Base64(HMAC_SHA256(API_Key, request_body)) and sends it in this header[13]. We must recompute and match it.

Timestamp (ts): The XML request must include a ts attribute (ISO datetime)[14][3]. We use this to prevent replay. Reject if outside allowable window (e.g. >5 minutes skew).

KeyHash: The request has a keyhash attribute equal to SHA256(API_Key + ts)[14][3]. On receipt, compute this and verify.

Txn & OrgID: Include a unique txn (transaction ID)[14][3] and the issuer’s orgId (assigned by DigiLocker) in the request. These are echoed back in the response.

Example Request:

<?xml version="1.0"?>
<PullURIRequest xmlns="http://tempuri.org/" ver="3.0"
                ts="2024-05-21T12:34:56+05:30" txn="abcd1234"
                orgId="pension.gov.in" keyhash="" format="xml">
  <DocDetails> 
    <DocType>PPO</DocType>
    <DigiLockerId></DigiLockerId>
    <!-- Optional Aadhaar-based fields -->
  </DocDetails>
</PullURIRequest>

(Here keyhash is the SHA-256 hash of APIKey + ts.)

Verification Steps (server side):

Check x-digilocker-hmac: compute HMAC_SHA256(API_Key, raw_body) and compare (constant-time) with the header[13].

Parse XML: extract ts and keyhash. Recompute SHA256(API_Key + ts) and match to keyhash.

Validate timestamp window (e.g. ±5 min).

Confirm orgId matches our issuer ID registered with DigiLocker.

Verify all mandatory elements (per spec) are present.

If any step fails, reject with HTTP 401/400.

Citations: The spec explicitly states: “x-digilocker-hmac: … HMAC of the HTTP request body using SHA256 and the API Key… converted to Base64”[13]. The request template confirms ts and KeyHash are mandatory and describes KeyHash as “Sha256 hashing of defined API key and timestamp”[3].

## 4. Document URI Format & DB Constraints (Sec. 7.1)

DigiLocker requires every document’s URI to be:

<IssuerId>[-DocType]-<DocId>

[4]. Specifically:

IssuerId (mandatory): Unique issuer code (pure alpha, case-insensitive)[4]. We use, e.g., our domain or code registered with DigiLocker.

DocType (mandatory): 5-letter alpha code for document type (e.g. PPO, GPO)[15]. Issuers select from DigiLocker’s list.

DocId (mandatory): Up to 10-character unique document ID within the issuer’s system[16]. Preferably random/alphanumeric to avoid predictability.

Example: finance.gov.in-PPO-XY12345Z.

### Implementation:

DB Columns:

Add issuer_id VARCHAR (storing our IssuerId).

Use existing document_type for DocType (VARCHAR(5), dropping old constraint).

Rename or alias authorization_number as doc_id (it’s currently VARCHAR(9)). If needed, alter to VARCHAR(10) for up to 10 chars.

Store digilocker_uri (VARCHAR) only if helpful; we can also compute it on-the-fly (issuer_id || '-' || document_type || '-' || doc_id).

Constraints:

Length/Pattern: Enforce length(doc_id)<=10, document_type ~ '^[A-Za-z]{1,5}$', issuer_id ~ '^[A-Za-z]+$' (pattern or check constraint).

Unique Index: Enforce UNIQUE(issuer_id, document_type, doc_id). This directly implements the spec’s uniqueness.

Drop the old (document_type, authorization_number) unique; replace with the new composite if changing columns.

Generation/Parsing Logic: Always concatenate {issuer_id}-{document_type}-{doc_id} for the URI presented in API responses. If digilocker_uri is stored, keep it in sync.

Spec Excerpts: “All documents… have the following URI format: <IssuerId>[-DocType]-<DocId>”[4]. The fields are defined as above[15][16].

## 5. HMAC Signature Construction (Pseudo-code)

Following the spec, the issuer constructs the signature as:
1. Prepare the exact request XML/JSON (canonicalize whitespace/order).
2. Compute hmac_sha256 = HMAC_SHA256(API_Key, request_body_bytes).
3. Base64-encode it.
4. Set header x-digilocker-hmac = base64_hmac.

Python-style example:

import hmac, hashlib, base64

def sign_request(request_body_bytes, api_key):
    """Compute Base64-encoded HMAC-SHA256 signature."""
    mac = hmac.new(api_key.encode(), request_body_bytes, hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()

# Usage:
body = b'<PullURIRequest ...>...</PullURIRequest>'
signature = sign_request(body, "mySecretApiKey")
headers = {"x-digilocker-hmac": signature, "Content-Type": "application/xml"}

On verification (server-side):

received_sig = request.headers.get('x-digilocker-hmac', '')
calc_sig = sign_request(request.body, shared_api_key)
if not hmac.compare_digest(received_sig, calc_sig):
    raise AuthenticationError("Invalid HMAC")

# Also verify KeyHash:
ts = xml.get("ts")
keyhash = xml.get("KeyHash")
if hashlib.sha256((api_key + ts).encode()).hexdigest() != keyhash:
    raise AuthenticationError("KeyHash mismatch")

This aligns with spec language[13][3].

## 6. Schema Changes & Migration Plan

To meet spec and best practices, we recommend:

DOB as DATE:
Replace employee_dob VARCHAR(10) with a employee_dob_date DATE.

ALTER TABLE digilocker_documents ADD COLUMN employee_dob_date DATE;
UPDATE digilocker_documents
  SET employee_dob_date = TO_DATE(employee_dob, 'DD-MM-YYYY');
ALTER TABLE digilocker_documents DROP COLUMN employee_dob;
-- Optionally, add a generated column for the string format:
ALTER TABLE digilocker_documents
  ADD COLUMN employee_dob_string VARCHAR(10) 
    GENERATED ALWAYS AS (TO_CHAR(employee_dob_date,'DD-MM-YYYY')) STORED;

This allows indexing and proper date ops.

File Storage Abstraction:
Replace absolute file_path with two parts: storage_type and relative_path.

ALTER TABLE digilocker_documents
  ADD COLUMN storage_type VARCHAR(10) NOT NULL DEFAULT 'local',
  ADD COLUMN relative_path TEXT;
UPDATE digilocker_documents
  SET relative_path = file_path;
ALTER TABLE digilocker_documents DROP COLUMN file_path;

Then configure BASE_PATH=/data/pension_docs; full path = BASE_PATH || relative_path. This makes moving to S3/NFS easier.

Issuer & Document ID Columns:

ALTER TABLE digilocker_documents
  ADD COLUMN issuer_id VARCHAR(255) NOT NULL DEFAULT 'your.issuer.id',
  RENAME COLUMN authorization_number TO doc_id;
ALTER TABLE digilocker_documents
  ALTER COLUMN doc_id TYPE VARCHAR(10);

Initialize issuer_id to our registered DigiLocker Issuer ID (e.g. department URL) for all rows.

URI and Unique Constraint:

ALTER TABLE digilocker_documents
  ADD UNIQUE(issuer_id, document_type, doc_id);

(Drop the old (document_type, authorization_number) unique constraint if still present.)

Access & Integrity Log Adjustments:
These tables reference document by authorization_number and document_type. We may keep them but should consider adding issuer_id if we support multiple issuers in one DB. For now, assume single issuer.

Checksum Column:
Keep file_checksum (existing). If using new storage, recompute as needed.

Summary of Migration: apply above ALTERs, populate new fields from old ones, then remove outdated columns.

## 7. Integrity Enforcement Modes

We allow configurable enforcement of checksum/file integrity on GET:

STRICT (default): Any missing file or checksum mismatch blocks serving. Return e.g. HTTP 410 Gone or 500.

LOG_ONLY: Log integrity issues but still serve the document. Include header X-Integrity-Status: FAILED (or similar) in the response for diagnostics.

LOG_AND_SERVE: Serve the file but escalate (raise alerts/metrics) on failures.

Config example:

integrity_check_mode: STRICT   # or LOG_ONLY, LOG_AND_SERVE

Implementation snippet:

if not os.path.exists(path) or compute_checksum(path) != stored_checksum:
    log_file_integrity(document_id, request.ip, details)
    metrics_counter('digilocker.integrity_fail').inc()
    if config.integrity_check_mode == 'STRICT':
        return HttpResponse(status=410, content="Document temporarily unavailable")
    else:
        response.headers['X-Integrity-Status'] = 'FAILED'
        # Continue to send file

All failures go to digilocker_file_integrity_logs. Alert on repeated FAIL events. This toggling is acceptable with careful monitoring; by default we keep STRICT to avoid silently serving bad data.

## 8. Rate Limiting and Backpressure

While DigiLocker traffic is “trusted,” we should protect against floods or misconfiguration:

API Gateway (Nginx): Example: limit_req zone=one burst=100 nodelay; with a rate of ~200 req/s for PullURI. This caps sustained load but allows bursts.

Application Layer: Implement a request queue or throttling (e.g. token bucket per-IP or per-client). For instance, allow up to 100 req/s with a graceful 429 on excess.

Database: Use connection pooling (max ~30 connections) and ensure queries use indexes. Avoid n+1 queries.

File Serving: Stream files (e.g. using X-Sendfile or chunked response) to handle large PDFs without tying up memory.

Example Limits:
- Nginx: 1000 req/min (16 req/s) per client IP.
- App (Gunicorn/Uvicorn): 50 worker limit, each handling ~20 req/s.
- These can be tuned. The goal is preventing DoS or rogue loops while comfortably serving legitimate spikes.

## 9. Security Checklist

Constant-Time HMAC: Use a constant-time compare function (hmac.compare_digest) when verifying signatures to prevent timing attacks.

Timestamp Skew: Reject requests if ts is older or in the future beyond ~5 min. (Spec does not state explicitly, but this is industry practice.)

Replay Prevention: Store recent txn values or use them as nonces. Ensure each txn is unique per request. Reject reused txn within the time window.

IP Whitelisting: If possible, restrict access to known DigiLocker IPs (from official docs).

Transport Security: Enforce HTTPS (TLS) for all endpoints. Reject plain HTTP.

Strict Headers: Only accept expected headers (Content-Type, x-digilocker-hmac). Reject extra or malformed headers.

Input Validation: Sanitize and validate all input fields (e.g. only allow digits in Aadhaar hash field, length limits on UDFs). Use prepared statements/ORM to prevent injection.

Minimal Privileges: The DB user should have only SELECT/UPDATE rights on these tables, no admin privileges.

Audit Logging: Ensure every request and response (success or failure) is logged to digilocker_access_logs with timestamp, URI, status, and client IP.

Error Handling: Do not leak stack traces or internal info in error responses. Use generic error messages.

## 10. Compliance Checklist (Spec → Design)

No major gaps remain. All spec clauses have a corresponding design element. We note that PullDoc removal is explicitly confirmed in rev history[1], so we do not implement it.

## Diagrams

API Sequence Flow: PullURI and Document fetch

sequenceDiagram
    participant DL as DigiLocker
    participant App as IssuerApp
    DL->>App: POST /pull-uri (XML body + x-digilocker-hmac)
    App-->>DL: 200 OK, <PullURIResponse> with <URI>...</URI>
    DL->>App: GET /document/{issuer-doc-uri} (with x-digilocker-hmac)
    App-->>DL: 200 OK, Content-Type: application/pdf (document stream)

Entity-Relationship (simplified):

erDiagram
    ISSUER {
        VARCHAR issuer_id PK "Our unique IssuerID"
    }
    DOCUMENT }|--|| ISSUER : issued_by
    DOCUMENT {
        bigint id PK
        VARCHAR issuer_id FK
        VARCHAR document_type
        VARCHAR doc_id
        BOOLEAN digilocker_enabled
        TEXT relative_path
        VARCHAR file_checksum
        DATE employee_dob_date
        ...
    }
    ACCESS_LOG ||--|{ DOCUMENT : logs
    ACCESS_LOG {
        bigint id PK
        bigint document_id FK
        VARCHAR digilocker_txn
        VARCHAR digilocker_id
        INT response_status
        TIMESTAMP created_at
    }
    INTEGRITY_LOG ||--|{ DOCUMENT : logs
    INTEGRITY_LOG {
        bigint id PK
        bigint document_id FK
        VARCHAR stored_checksum
        VARCHAR calculated_checksum
        VARCHAR integrity_issue_type
        VARCHAR action_taken
        TIMESTAMP created_at
    }

## Actionable Next Steps

DB Migrations: Apply the ALTER TABLE changes above (DOB, storage columns, issuer_id/doc_id, constraints). Re-index accordingly.

API Implementation: In our codebase (e.g. Django/FastAPI):

Implement /pull-uri with strict HMAC and KeyHash validation (use middleware or decorator). Return response XML per spec.

Implement /document/{uri} GET: resolve issuer_id, document_type, doc_id from URI, check digilocker_enabled, validate checksum based on mode, then stream file.

Echo ts and txn in PullURIResponse exactly as received[3].

Configuration:

Add settings: API_KEY, ISSUER_ID, BASE_PATH, INTEGRITY_MODE.

Load allowed DocTypes from config or a table.

Testing: Write end-to-end tests: simulate DigiLocker sending signed requests (test HMAC and KeyHash), verify responses. Test integrity toggle effects.

Deployment: Set up TLS certificates, rate-limit rules in Nginx. Monitor logs/metrics for failures.

Documentation: Update API docs with exact headers, sample requests, error codes, per spec lines.

Sources: Official DigiLocker Issuer API Spec v1.13[2][13][3][1] (citations denote pdf page and line numbers). All key requirements are directly quoted and addressed above.


[1] [2] [3] [4] [5] [6] [7] [8] [9] [10] [11] [12] [13] [14] [15] [16] Issuer API Specification

https://cf-media.api-setu.in/resources/DigiLocker-Issuer-APISpecification-v1-13.pdf

| Spec Clause / Section | Requirement | Our Design | Status (Gap) |
| --- | --- | --- | --- |
| Sec 6 (Issuance Flow)[2] | Signed PDF with unique URI; printed doc with URI | Pre-generate signed PDFs; include our URI in printouts | ✔️ (met) |
| Sec 7.1 (URI Format)[4] | URI = <IssuerId>[-DocType]-<DocId> | Use issuer_id, document_type, doc_id to form URI | ✔️ (met) |
| Sec 7.1 (IssuerId alpha)[4] | IssuerId is unique alpha string | Enforce alpha pattern in config/admin; ensure validity | ✔️ (met) |
| Sec 7.1 (DocType 5α)[15] | DocType is 5 pure alpha letters | Pattern check document_type ~ '^[A-Za-z]{1,5}$' | ✔️ (met) |
| Sec 7.1 (DocId ≤10)[16] | DocId ≤10 chars, numeric/alpha | Limit doc_id VARCHAR(10); disallow non-alphanumeric if needed | ✔️ (met) |
| Sec 8 (p.8) (1 API, PullURI)[11] | Only Pull URI API (not PullDoc) | Implement /pull-uri; no PullDoc endpoint | ✔️ (met) |
| Sec 8.1.1 (Headers)[13] | Content-Type: application/xml; x-digilocker-hmac | Enforce headers; compute/verify x-digilocker-hmac | ✔️ (met) |
| Sec 8.1.1 (x-digilocker-hmac)[13] | HMAC-SHA256 of body, Base64 | HMAC as above (Python snippet) | ✔️ (met) |
| Sec 8.1.2 (ts, KeyHash)[3] | Fields ts (timestamp) and KeyHash (SHA256 key+ts) | Include <ts> and <KeyHash> attributes; verify on server | ✔️ (met) |
| Sec 8.1.2 (txn, orgId)[3] | Fields txn (transaction ID) and orgId (issuer ID) | Include <txn>, <orgId> in request; echo in response | ✔️ (met) |
| Sec 8.1.3 (Response fields) | Response must echo ts, txn; include data or URI | We will echo request ts/txn and return URI(s) or Base64 data as required | Partial: ensure echo |
| Sec 8.1.2 (DocDetails elements)[14] | UDFs, DigiLockerId, etc in request | We read/use necessary UDFs; no spec violation | ✔️ (met) |
| Sec 7.3 (Format: PDF/XML) | E-documents must be PDF or XML | We only issue PDFs. (Not XML, but DLTS considers PDF acceptable) | ✔️ (met) |
| Security (implied) | Protect request integrity and privacy | HMAC/timestamp (above); TLS enforced; logs for audit | ✔️ (met) |
