from django.urls import path

from issuer import manage_auth, manage_views, views

app_name = "issuer"

urlpatterns = [
    path("pull-uri", views.pull_uri_view, name="pull-uri"),
    path("demo", views.demo_ui, name="demo-ui"),
    path("demo/submit", views.demo_submit, name="demo-submit"),
    path("demo/view-doc/<path:uri>", views.demo_view_doc, name="demo-view-doc"),
    path("document/<path:uri>", views.document_fetch_view, name="document-fetch"),
    # Management console (login/logout are public; all other manage routes require auth)
    path("manage/login/", manage_auth.ManagePortalLoginView.as_view(), name="manage-login"),
    path("manage/logout/", manage_auth.manage_logout, name="manage-logout"),
    path("manage/", manage_views.manage_hub, name="manage-hub"),
    path("manage/documents/", manage_views.document_list, name="document-list"),
    path("manage/documents/export/", manage_views.document_export, name="document-export"),
    path("manage/documents/<int:pk>/file/", manage_views.document_view_file, name="document-view-file"),
    path("manage/documents/<int:pk>/", manage_views.document_detail, name="document-detail"),
    path("manage/access-logs/export/", manage_views.accesslog_export, name="accesslog-export"),
    path("manage/access-logs/<int:pk>/", manage_views.accesslog_detail, name="accesslog-detail"),
    path("manage/access-logs/", manage_views.accesslog_list, name="accesslog-list"),
    path("manage/integrity-logs/export/", manage_views.integritylog_export, name="integritylog-export"),
    path("manage/integrity-logs/<int:pk>/", manage_views.integritylog_detail, name="integritylog-detail"),
    path("manage/integrity-logs/", manage_views.integritylog_list, name="integritylog-list"),
    path("manage/kpi-report/download/", manage_views.kpi_report_download, name="kpi-report-download"),
    path("manage/kpi-report/", manage_views.kpi_report, name="kpi-report"),
    path("manage/tools/decode-pdf/", manage_views.decode_pdf_tool, name="decode-pdf-tool"),
    path(
        "manage/tools/decode-pdf/view/<str:token>/",
        manage_views.decode_pdf_view,
        name="decode-pdf-view",
    ),
]
