## **DigiLocker Issuer — Database Design Document (v2.1 FINAL)** 

## **1. Objective** 

Design a **PostgreSQL schema** that: 

- Enforces **DLTS-compliant document identity (URI + doc_id)** 

- Supports **lazy, atomic URI assignment** 

- Guarantees **immutability of identifiers** 

- Enables **secure lookup via (authorization_number + document_type)** 

- Provides **auditability and integrity tracking** 

- Remains **portable across environments** 

## **2. Core Design Principles** 

## **2.1 Identity Model** 

Lookup Key        → (authorization_number, document_type) 

Public Identifier → URI 

Internal ID       → doc_id (random, non-guessable) 

## **2.2 URI Rules** 

- Format: 

- <ISSUER_ID>-<DocType>-<doc_id> 

- Generated **once** 

- Never updated 

- Globally unique 

## **2.3 Responsibility Split** 

**Concern Layer** 

Uniqueness, immutability DB 

Identity validation (DOB/name) Application 

Authentication (HMAC) Application 

## **2.4 Storage Strategy** 

- Store **relative file paths only** 

- Resolve at runtime using config 

## **3. Schema Overview** 

documents 

access_logs 

integrity_logs 

(optional) document_types 

## **4. Core Table: documents** 

## **4.1 Final DDL** 

CREATE TABLE documents ( 

id BIGSERIAL PRIMARY KEY, 

-- Business lookup 

authorization_number VARCHAR(50) NOT NULL, 

document_type VARCHAR(5) NOT NULL, 

-- DLTS identifiers (write-once) doc_id VARCHAR(10), uri VARCHAR(255), 

-- Identity attributes employee_name TEXT, employee_dob DATE, 

-- File metadata 

file_relative_path TEXT NOT NULL, file_checksum VARCHAR(64), -- SHA256 hex file_size_bytes BIGINT, file_last_checked_at TIMESTAMP, 

-- State 

is_active BOOLEAN NOT NULL DEFAULT TRUE, 

digilocker_enabled BOOLEAN NOT NULL DEFAULT TRUE, 

-- Audit created_at TIMESTAMP NOT NULL DEFAULT NOW(), updated_at TIMESTAMP NOT NULL DEFAULT NOW() 

); 

## **5. Constraints** 

## **5.1 Business Uniqueness** 

## ALTER TABLE documents 

ADD CONSTRAINT uq_documents_business 

UNIQUE (authorization_number, document_type); 

## **5.2 DLTS Identity Constraints** 

ALTER TABLE documents 

ADD CONSTRAINT uq_doc_id UNIQUE (doc_id); 

ALTER TABLE documents 

ADD CONSTRAINT uq_uri UNIQUE (uri); 

## **5.3 Lifecycle Constraint (Critical)** 

ALTER TABLE documents 

ADD CONSTRAINT chk_doc_id_uri_pair 

CHECK ( 

(doc_id IS NULL AND uri IS NULL) 

OR 

(doc_id IS NOT NULL AND uri IS NOT NULL) 

); 

## **5.4 Format Constraints** 

ALTER TABLE documents 

ADD CONSTRAINT chk_document_type_format 

CHECK (document_type ~ '^[A-Za-z]{1,5}$'); 

ALTER TABLE documents 

ADD CONSTRAINT chk_doc_id_length 

CHECK (doc_id IS NULL OR length(doc_id) <= 10); 

ALTER TABLE documents 

ADD CONSTRAINT chk_file_size 

CHECK (file_size_bytes IS NULL OR file_size_bytes >= 0); 

## **6. Immutability Enforcement** 

## **6.1 Trigger** 

CREATE OR REPLACE FUNCTION prevent_identifier_update() 

RETURNS trigger AS $$ 

BEGIN 

IF OLD.uri IS NOT NULL AND NEW.uri IS DISTINCT FROM OLD.uri THEN 

RAISE EXCEPTION 'URI is immutable'; 

END IF; 

IF OLD.doc_id IS NOT NULL AND NEW.doc_id IS DISTINCT FROM OLD.doc_id THEN 

RAISE EXCEPTION 'doc_id is immutable'; 

END IF; 

RETURN NEW; 

END; 

$$ LANGUAGE plpgsql; 

CREATE TRIGGER trg_prevent_identifier_update 

BEFORE UPDATE ON documents 

FOR EACH ROW 

EXECUTE FUNCTION prevent_identifier_update(); 

## **7. Index Strategy** 

## **7.1 Primary Lookup** 

CREATE INDEX idx_documents_lookup 

ON documents (authorization_number, document_type) 

WHERE is_active = TRUE AND digilocker_enabled = TRUE; 

## **7.2 Identifier Access** 

CREATE INDEX idx_documents_uri ON documents (uri); 

CREATE INDEX idx_documents_doc_id ON documents (doc_id); 

## **7.3 Optional** 

CREATE INDEX idx_documents_created ON documents (created_at); 

## **8. File Handling Model** 

## **8.1 Storage** 

file_relative_path → stored 

BASE_STORAGE_PATH → config 

## **8.2 Runtime Resolution** 

full_path = BASE_STORAGE_PATH + file_relative_path 

## **8.3 Integrity** 

- SHA256 checksum 

- periodic verification 

- logged discrepancies 

## **9. Access Logs** 

## **9.1 Table** 

CREATE TABLE access_logs ( 

id BIGSERIAL PRIMARY KEY, 

document_id BIGINT REFERENCES documents(id) ON DELETE SET NULL, 

authorization_number VARCHAR(50), 

document_type VARCHAR(5), 

txn_id VARCHAR(100), 

digilocker_id VARCHAR(255), 

request_ip INET, 

user_agent TEXT, 

response_status SMALLINT, 

error_message TEXT, 

processing_time_ms INTEGER, 

created_at TIMESTAMP DEFAULT NOW() 

); 

## **10. Integrity Logs** 

## **10.1 Table** 

CREATE TABLE integrity_logs ( 

id BIGSERIAL PRIMARY KEY, 

document_id BIGINT REFERENCES documents(id) ON DELETE SET NULL, 

issue_type VARCHAR(30), 

stored_checksum VARCHAR(64), 

calculated_checksum VARCHAR(64), 

file_path TEXT, 

action_taken VARCHAR(20), 

created_at TIMESTAMP DEFAULT NOW() 

); 

## **11. Concurrency Model** 

## **11.1 Requirement** 

- URI must be generated **exactly once** 

## **11.2 Mechanism** 

Application must use: 

SELECT * FROM documents WHERE id = ? FOR UPDATE; 

## **11.3 Guarantees** 

- No duplicate URI 

- No race conditions 

- Atomic assignment 

## **12. Migration from Current Schema** 

Your current DB includes: 

- string dates 

- absolute file paths 

- strict enum constraints 

## **12.1 Migration Plan** 

## **Step 1 — Add new DATE columns** 

ALTER TABLE digilocker_documents ADD COLUMN employee_dob_new DATE; 

ALTER TABLE digilocker_documents ADD COLUMN authorization_date_new DATE; 

## **Step 2 — Backfill** 

UPDATE digilocker_documents 

SET employee_dob_new = TO_DATE(employee_dob, 'DD/MM/YYYY'), 

authorization_date_new = TO_DATE(authorization_date, 'DD/MM/YYYY'); 

## **Step 3 — Replace old columns** 

- drop VARCHAR columns 

- rename new columns 

## **Step 4 — Convert file path** 

ALTER TABLE digilocker_documents RENAME COLUMN file_path TO file_relative_path; 

Remove absolute path validation trigger 

## **Step 5 — Relax document_type constraint** 

Drop: 

chk_document_type 

## **Step 6 — Add immutability trigger** 

## **Step 7 — Add lifecycle constraint** 

## **13. What DB Does NOT Handle** 

- HMAC authentication 

- identity validation (DOB/name) 

- business rules 

- DigiLocker request validation 

## **14. Security Considerations** 

- restrict DB access 

- encrypt backups 

- monitor audit logs 

- no secrets stored in DB 

## **15. Performance Characteristics** 

## **Aspect Behavior** 

Lookup indexed, O(log n) 

Writes low volume 

Locks row-level only 

Scaling horizontal read possible 

## **16. Acceptance Criteria** 

DB is production-ready if: 

- ✔ URI/doc_id immutable 

- ✔ no duplicate URI possible 

- ✔ safe concurrent generation 

- ✔ lookup fast 

- ✔ portable storage paths 

- ✔ correct data types 

## **17. Final Alignment Status** 

**Area Status** 

Spec compliance ✔ 

Your original DB ✔ (with fixes) 

Security ✔ Concurrency ✔ Maintainability ✔ 

