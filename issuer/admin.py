from django.contrib import admin

from issuer.models import AccessLog, Document, IntegrityLog


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "id", "authorization_number", "document_type", "uri",
        "employee_name", "employee_gender", "employee_mobile", "employee_dob",
        "ddo_name", "treasury_name", "treasury_code", "authorization_date",
        "file_relative_path", "file_exists", "file_checksum", "file_size_bytes",
        "is_active", "digilocker_enabled", "access_count", "last_accessed_at",
        "application_number", "external_system_id", "created_at",
    )
    list_filter = ("document_type", "is_active", "digilocker_enabled", "employee_gender", "file_exists")
    search_fields = ("authorization_number", "uri", "employee_name", "employee_mobile", "application_number", "external_system_id")
    readonly_fields = ("doc_id", "uri", "created_at", "updated_at", "file_size_bytes", "last_accessed_at")


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = (
        "id", "txn_id", "document_type", "authorization_number",
        "requested_mobile", "file_path", "file_checksum",
        "response_status", "processing_time_ms", "created_at",
    )
    list_filter = ("response_status", "document_type")
    search_fields = ("txn_id", "authorization_number", "digilocker_id", "requested_mobile", "file_path", "file_checksum")
    readonly_fields = ("created_at",)


@admin.register(IntegrityLog)
class IntegrityLogAdmin(admin.ModelAdmin):
    list_display = (
        "id", "issue_type", "action_taken", "document", "authorization_number", "document_type", "digilocker_txn", "digilocker_id", "request_ip", "stored_file_size", "calculated_file_size", "created_at"
    )
    list_filter = ("issue_type", "action_taken", "document_type")
    search_fields = ("authorization_number", "digilocker_txn", "digilocker_id", "request_ip")
    readonly_fields = ("created_at",)
