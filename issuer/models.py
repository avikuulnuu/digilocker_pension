from django.db import models
from django.core.validators import RegexValidator
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector


class Document(models.Model):
    """Core document table — DLTS-compliant identity and storage."""

    authorization_number = models.CharField(max_length=20)
    document_type = models.CharField(
        max_length=5,
        validators=[RegexValidator(r"^[A-Za-z]{1,5}$", "1-5 alpha characters only")],
    )

    # DLTS identifiers — write-once, lazily generated
    digilocker_doc_id = models.CharField(max_length=10, unique=True, null=True, blank=True)
    digilocker_uri = models.CharField(max_length=255, unique=True, null=True, blank=True)

    # Identity attributes for access-control matching
    employee_name = models.TextField()
    employee_dob = models.DateField(null=True, blank=True)
    employee_gender = models.CharField(max_length=10, blank=True, default="")
    employee_mobile = models.CharField(max_length=10, blank=True, null=True)
    ddo_name = models.CharField(max_length=500, blank=True, default="")
    treasury_name = models.CharField(max_length=255, blank=True, null=True)
    treasury_code = models.CharField(max_length=50, blank=True, null=True)
    authorization_date = models.CharField(max_length=10)

    # File metadata
    file_name = models.TextField()
    file_checksum = models.CharField(max_length=64, null=True, blank=True)
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    file_last_checked_at = models.DateTimeField(null=True, blank=True)
    file_exists = models.BooleanField(default=False)

    # State flags
    is_active = models.BooleanField(default=True)
    digilocker_enabled = models.BooleanField(default=True)
    access_count = models.IntegerField(default=0)
    last_accessed_at = models.DateTimeField(null=True, blank=True)

    # External references
    application_number = models.CharField(max_length=50, blank=True, null=True)
    external_system_id = models.BigIntegerField(unique=True)
    external_metadata = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "digilocker_documents"
        constraints = [
            models.UniqueConstraint(
                fields=["authorization_number", "document_type"],
                name="uq_document",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(digilocker_doc_id__isnull=True, digilocker_uri__isnull=True)
                    | models.Q(digilocker_doc_id__isnull=False, digilocker_uri__isnull=False)
                ),
                name="chk_doc_id_uri_pair",
            ),
            models.CheckConstraint(
                condition=models.Q(authorization_date__regex=r"^\d{2}/\d{2}/\d{4}$"),
                name="chk_authorization_date",
            ),
            models.CheckConstraint(
                condition=models.Q(access_count__gte=0),
                name="chk_access_count",
            ),
            models.CheckConstraint(
                condition=models.Q(file_size_bytes__isnull=True) | models.Q(file_size_bytes__gt=0),
                name="chk_file_size",
            ),
        ]
        indexes = [
            models.Index(
                fields=["authorization_number", "document_type"],
                name="idx_auth_lookup",
                condition=models.Q(is_active=True, digilocker_enabled=True),
            ),
            models.Index(fields=["created_at"], name="idx_created"),
            models.Index(fields=["digilocker_uri"], name="idx_digilocker_uri"),
            models.Index(fields=["digilocker_doc_id"], name="idx_digilocker_doc_id"),
            models.Index(fields=["file_exists", "file_last_checked_at"], name="idx_file_verification"),
            models.Index(fields=["employee_mobile"], name="idx_mobile"),
            GinIndex(
                SearchVector("employee_name", config="english"),
                name="idx_employee_name_fts",
            ),
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
    requested_mobile = models.CharField(max_length=10, blank=True, null=True)
    file_path = models.TextField(blank=True, default="")
    file_checksum = models.CharField(max_length=64, blank=True, default="")
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
    authorization_number = models.CharField(max_length=50, blank=True, default="")
    document_type = models.CharField(max_length=10, blank=True, default="")
    stored_file_size = models.BigIntegerField(null=True, blank=True)
    calculated_file_size = models.BigIntegerField(null=True, blank=True)
    request_ip = models.CharField(max_length=45, blank=True, default="")
    digilocker_txn = models.CharField(max_length=100, blank=True, default="")
    digilocker_id = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "integrity_logs"

    def __str__(self):
        return f"[{self.created_at}] {self.issue_type} doc={self.document_id}"
