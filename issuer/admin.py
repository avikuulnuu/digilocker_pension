from django.contrib import admin

from issuer.models import AccessLog, Document, IntegrityLog


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "id", "authorization_number", "document_type", "uri",
        "employee_name", "is_active", "digilocker_enabled", "created_at",
    )
    list_filter = ("document_type", "is_active", "digilocker_enabled")
    search_fields = ("authorization_number", "uri", "employee_name")
    readonly_fields = ("doc_id", "uri", "created_at", "updated_at")


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = (
        "id", "txn_id", "document_type", "authorization_number",
        "response_status", "processing_time_ms", "created_at",
    )
    list_filter = ("response_status", "document_type")
    search_fields = ("txn_id", "authorization_number", "digilocker_id")
    readonly_fields = ("created_at",)


@admin.register(IntegrityLog)
class IntegrityLogAdmin(admin.ModelAdmin):
    list_display = ("id", "issue_type", "action_taken", "document", "created_at")
    list_filter = ("issue_type", "action_taken")
    readonly_fields = ("created_at",)
