from django.urls import path

from issuer import manage_views, views

app_name = "issuer"

urlpatterns = [
    path("pull-uri", views.pull_uri_view, name="pull-uri"),
    path("demo", views.demo_ui, name="demo-ui"),
    path("demo/submit", views.demo_submit, name="demo-submit"),
    path("demo/view-doc/<path:uri>", views.demo_view_doc, name="demo-view-doc"),
    path("document/<path:uri>", views.document_fetch_view, name="document-fetch"),
    # Management CRUD
    path("manage/", manage_views.manage_hub, name="manage-hub"),
    path("manage/documents/", manage_views.document_list, name="document-list"),
    path("manage/documents/export/", manage_views.document_export, name="document-export"),
    path("manage/documents/new/", manage_views.document_create, name="document-create"),
    path("manage/documents/<int:pk>/", manage_views.document_detail, name="document-detail"),
    path("manage/documents/<int:pk>/edit/", manage_views.document_update, name="document-update"),
    path("manage/documents/<int:pk>/delete/", manage_views.document_delete, name="document-delete"),
    path("manage/access-logs/", manage_views.accesslog_list, name="accesslog-list"),
    path("manage/access-logs/export/", manage_views.accesslog_export, name="accesslog-export"),
    path("manage/access-logs/new/", manage_views.accesslog_create, name="accesslog-create"),
    path("manage/access-logs/<int:pk>/", manage_views.accesslog_detail, name="accesslog-detail"),
    path("manage/access-logs/<int:pk>/edit/", manage_views.accesslog_update, name="accesslog-update"),
    path("manage/access-logs/<int:pk>/delete/", manage_views.accesslog_delete, name="accesslog-delete"),
    path("manage/integrity-logs/", manage_views.integritylog_list, name="integritylog-list"),
    path("manage/integrity-logs/export/", manage_views.integritylog_export, name="integritylog-export"),
    path("manage/integrity-logs/new/", manage_views.integritylog_create, name="integritylog-create"),
    path("manage/integrity-logs/<int:pk>/", manage_views.integritylog_detail, name="integritylog-detail"),
    path("manage/integrity-logs/<int:pk>/edit/", manage_views.integritylog_update, name="integritylog-update"),
    path("manage/integrity-logs/<int:pk>/delete/", manage_views.integritylog_delete, name="integritylog-delete"),
]
