from django import forms

from issuer.models import AccessLog, Document, IntegrityLog


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = [
            "authorization_number",
            "document_type",
            "digilocker_doc_id",
            "digilocker_uri",
            "employee_name",
            "employee_dob",
            "employee_gender",
            "employee_mobile",
            "ddo_name",
            "treasury_name",
            "treasury_code",
            "authorization_date",
            "file_name",
            "file_checksum",
            "file_size_bytes",
            "file_last_checked_at",
            "file_exists",
            "is_active",
            "digilocker_enabled",
            "access_count",
            "last_accessed_at",
            "application_number",
            "external_system_id",
            "external_metadata",
        ]
        widgets = {
            "employee_name": forms.Textarea(attrs={"rows": 2}),
            "file_name": forms.Textarea(attrs={"rows": 2}),
            "external_metadata": forms.Textarea(attrs={"rows": 4}),
            "employee_dob": forms.DateInput(attrs={"type": "date"}),
            "file_last_checked_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "last_accessed_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class AccessLogForm(forms.ModelForm):
    class Meta:
        model = AccessLog
        fields = [
            "document",
            "authorization_number",
            "document_type",
            "txn_id",
            "digilocker_id",
            "request_ip",
            "requested_mobile",
            "file_path",
            "file_checksum",
            "user_agent",
            "response_status",
            "error_message",
            "processing_time_ms",
        ]
        widgets = {
            "user_agent": forms.Textarea(attrs={"rows": 2}),
            "error_message": forms.Textarea(attrs={"rows": 3}),
            "file_path": forms.Textarea(attrs={"rows": 2}),
        }


class IntegrityLogForm(forms.ModelForm):
    class Meta:
        model = IntegrityLog
        fields = [
            "document",
            "issue_type",
            "stored_checksum",
            "calculated_checksum",
            "file_path",
            "action_taken",
            "authorization_number",
            "document_type",
            "stored_file_size",
            "calculated_file_size",
            "request_ip",
            "digilocker_txn",
            "digilocker_id",
        ]
        widgets = {
            "file_path": forms.Textarea(attrs={"rows": 2}),
        }
