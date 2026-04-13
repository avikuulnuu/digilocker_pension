## **DigiLocker Issuer Application** 

## **Production Technical Design Document (Final v1.1)** 

## **1. Objective** 

## Build a **DLTS-compliant Issuer service** that: 

- Implements **Pull URI API (only API)** 

- Returns: 

   - URI 

   - Base64 PDF 

   - Base64 XML metadata 

- Enforces: 

   - HMAC authentication 

   - Identity validation (post-lookup) 

   - Document integrity 

## **2. Spec Compliance (Verified)** 

From v1.13: 

- ✔ Only **Pull URI API** exists 

- ✔ PullDoc removed 

- ✔ Response includes document content 

- ✔ URI format mandatory 

- ✔ Identity validation recommended 

## **3. System Architecture** 

[DigiLocker] 

| 

v 

[API Layer] 

`├` ── HMAC Validator 

`├` ── XML Parser 

`├` ── Request Validator 

`├` ── Document Service 

`├` ── URI Service 

`├` ── File Service 

`├` ── Response Builder 

`├` ── Audit Logger 

| 

v 

[PostgreSQL] + [File Storage] 

## **4. Configuration** 

ISSUER_ID=in.gov.state.department 

API_KEY=<shared-secret> 

BASE_STORAGE_PATH=/data/docs 

INTEGRITY_MODE=STRICT | LOG_AND_SERVE 

IDENTITY_VALIDATION_MODE=STRICT | LENIENT 

MAX_FILE_SIZE_MB=10 

REQUEST_TIMEOUT_MS=5000 

## **5. Data Model** 

## **5.1 Table: documents** 

CREATE TABLE documents ( 

id BIGSERIAL PRIMARY KEY, 

authorization_number VARCHAR(50) NOT NULL, 

document_type VARCHAR(5) NOT NULL, 

doc_id VARCHAR(10) UNIQUE, 

uri VARCHAR(255) UNIQUE, 

employee_name TEXT, 

employee_dob DATE, 

file_relative_path TEXT NOT NULL, 

file_checksum TEXT, 

is_active BOOLEAN DEFAULT TRUE, 

created_at TIMESTAMP, 

updated_at TIMESTAMP 

); 

## **5.2 Constraints** 

UNIQUE (authorization_number, document_type) 

CHECK (document_type ~ '^[A-Za-z]{1,5}$') 

## **5.3 Indexes** 

CREATE INDEX idx_lookup 

ON documents (authorization_number, document_type); 

CREATE INDEX idx_uri ON documents (uri); 

## **6. URI Management** 

## **6.1 Format** 

URI = ISSUER_ID + "-" + document_type + "-" + doc_id 

## **6.2 Strategy** 

- Lazy generation 

- Atomic 

- Persistent 

## **6.3 Algorithm** 

def ensure_uri(row_id): 

with transaction(): 

row = SELECT ... FOR UPDATE 

if row.uri: 

return row.uri 

doc_id = random_string(10) 

uri = f"{ISSUER_ID}-{row.document_type}-{doc_id}" 

UPDATE documents 

SET doc_id = doc_id, uri = uri 

WHERE id = row_id 

return uri 

## **7. Authentication** 

## **7.1 HMAC Validation** 

expected = Base64(HMAC_SHA256(request_body, API_KEY)) 

Compare with: 

x-digilocker-hmac 

## **7.2 KeyHash Validation** 

keyhash = SHA256(API_KEY + timestamp) 

## **7.3 Rejection Rules** 

**Condition Action** 

HMAC mismatch 401 

keyhash mismatch 401 

timestamp invalid 401 

## **8. Request Handling Pipeline** 

## 1. Parse XML 

## 2. Validate HMAC 

3. Validate keyhash + timestamp 

## 4. Extract: 

- DocType 

- authorization_number (UDF) 

- DOB (optional) 

- Name (optional) 

5. Lookup document 

6. Identity validation 

## 7. Ensure URI 

8. File read + integrity check 

9. Base64 encode 

## 10. Build response XML 

11. Log 

12. Return 

## **9. Lookup vs Identity Validation (Final)** 

## **9.1 Lookup (Primary Key Resolution)** 

SELECT * 

FROM documents 

WHERE authorization_number = ? 

AND document_type = ? 

AND is_active = true; 

## **9.2 Identity Validation (Access Control)** 

## **Rules** 

## **Field Rule** 

DOB exact match (if provided) 

Name normalized match (if provided) 

## **Normalization** 

def normalize(name): 

return lower(remove_spaces(remove_punctuation(name))) 

## **9.3 Mode** 

IDENTITY_VALIDATION_MODE=STRICT | LENIENT 

## **STRICT** 

- Require at least one identity field 

- Reject if mismatch 

## **LENIENT** 

- Allow access without identity fields 

- Still validate if provided 

## **10. File Handling** 

## **10.1 Path Resolution** 

path = BASE_STORAGE_PATH + file_relative_path 

## **10.2 Integrity Check** 

## **Check Action** 

file missing fail 

checksum mismatch config-based 

## **10.3 Modes** 

INTEGRITY_MODE=STRICT | LOG_AND_SERVE 

## **11. Response Construction** 

## **11.1 XML Structure** 

<PullURIResponse> 

<ResponseStatus Status="1" ts="..." txn="..." /> 

<DocDetails> 

<IssuedTo> 

<Persons> 

<Person name="" dob="" /> 

</Persons> </IssuedTo> <URI>...</URI> 

<DocContent>BASE64 PDF</DocContent> 

## <DataContent>BASE64 XML</DataContent> 

## </DocDetails> 

## </PullURIResponse> 

## **11.2 Rules** 

- DocContent mandatory (pdf/both) 

- DataContent mandatory 

- synchronous response 

## **12. Error Handling** 

## **12.1 Response Status** 

## **Status Meaning** 

- 1 success 

- 0 failure 

- 9 pending 

## **12.2 Mapping** 

**Scenario Output** no record Status=0 

identity mismatch Status=0 

auth failure HTTP 401 integrity fail depends 

## **13. Security Model** 

## **13.1 Layers** 

## **Layer Mechanism** 

Transport HMAC 

Request keyhash 

Access identity validation 

## **13.2 Prohibitions** 

- No public doc endpoint 

- No URI-only access 

## **14. Logging & Audit** 

## **14.1 Access Log** 

- txn 

- timestamp 

- docType 

- status 

- latency 

## **14.2 Integrity Log** 

- checksum mismatch 

- file missing 

## **15. Performance** 

## **15.1 Constraints** 

- Base64 → +33% size 

- Full file in memory 

## **15.2 Limits** 

MAX_FILE_SIZE_MB=10 

## **15.3 Concurrency** 

- bounded worker pool 

- DB pool capped 

## **16. Background Jobs** 

## **16.1 URI Pre-generation** 

assign URI for documents where uri IS NULL 

## **16.2 Integrity Scan** 

periodic checksum verification 

## **17. Deployment** 

Nginx 

↓ 

App (Uvicorn/Gunicorn) 

↓ 

PostgreSQL 

↓ 

File Storage 

## **18. Observability** 

## **Metrics** 

- request rate 

- error rate 

- latency 

- integrity failures 

## **Alerts** 

- HMAC failures spike 

- integrity failures 

- DB latency 

## **19. Acceptance Criteria** 

- ✔ HMAC validation correct 

- ✔ URI stable and unique 

- ✔ No duplicate URI under concurrency 

- ✔ Identity mismatch blocks access (STRICT mode) 

- ✔ Response matches XML schema 

- ✔ Integrity checks enforced 

