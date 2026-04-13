from django.db import models
from django.core.validators import RegexValidator


class Document(models.Model):
    """Core document table — DLTS-compliant identity and storage."""

    authorization_number = models.CharField(max_length=50)
    document_type = models.CharField(
        max_length=5,
        validators=[RegexValidator(r"^[A-Za-z]{1,5}$", "1-5 alpha characters only")],
    )

    # DLTS identifiers — write-once, lazily generated
    doc_id = models.CharField(max_length=10, unique=True, null=True, blank=True)
    uri = models.CharField(max_length=255, unique=True, null=True, blank=True)

    # Identity attributes for access-control matching
    employee_name = models.TextField(blank=True, default="")
    employee_dob = models.DateField(null=True, blank=True)

    # File metadata
    file_relative_path = models.TextField()
    file_checksum = models.CharField(max_length=64, blank=True, default="")
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    file_last_checked_at = models.DateTimeField(null=True, blank=True)

    # State flags
    is_active = models.BooleanField(default=True)
    digilocker_enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "documents"
        constraints = [
            models.UniqueConstraint(
                fields=["authorization_number", "document_type"],
                name="uq_documents_business",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(doc_id__isnull=True, uri__isnull=True)
                    | models.Q(doc_id__isnull=False, uri__isnull=False)
                ),
                name="chk_doc_id_uri_pair",
            ),
        ]
        indexes = [
            models.Index(
                fields=["authorization_number", "document_type"],
                name="idx_documents_lookup",
                condition=models.Q(is_active=True, digilocker_enabled=True),
            ),
            models.Index(fields=["uri"], name="idx_documents_uri"),
            models.Index(fields=["doc_id"], name="idx_documents_doc_id"),
        ]

    def __str__(self):
        return f"{self.document_type}/{self.authorization_number}"


class AccessLog(models.Model):
    """Audit log for every DigiLocker API request."""

    document = models.ForeignKey(
        Document, on_delete=models.SET_NULL, null=True, blank=True
    )
    authorization_number = models.CharField(max_length=50, blank=True, default="")
    document_type = models.CharField(max_length=5, blank=True, default="")
    txn_id = models.CharField(max_length=100, blank=True, default="")
    digilocker_id = models.CharField(max_length=255, blank=True, default="")
    request_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    response_status = models.SmallIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    processing_time_ms = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "access_logs"
        indexes = [
            models.Index(fields=["created_at"], name="idx_access_logs_created"),
            models.Index(fields=["txn_id"], name="idx_access_logs_txn"),
        ]

    def __str__(self):
        return f"[{self.created_at}] txn={self.txn_id} status={self.response_status}"


class IntegrityLog(models.Model):
    """Log for file integrity check failures."""

    document = models.ForeignKey(
        Document, on_delete=models.SET_NULL, null=True, blank=True
    )
    issue_type = models.CharField(max_length=30)
    stored_checksum = models.CharField(max_length=64, blank=True, default="")
    calculated_checksum = models.CharField(max_length=64, blank=True, default="")
    file_path = models.TextField(blank=True, default="")
    action_taken = models.CharField(max_length=20, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "integrity_logs"

    def __str__(self):
        return f"[{self.created_at}] {self.issue_type} doc={self.document_id}"
