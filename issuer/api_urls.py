from django.urls import path

from issuer import views

urlpatterns = [
    path("health", views.health_view, name="health"),
    path("pulluri", views.pull_uri_view, name="pull-uri"),
    path("pulldoc", views.pull_doc_disabled_view, name="pull-doc-disabled"),
    path("pull-doc", views.pull_doc_disabled_view, name="pull-doc-disabled-alt"),
    path("document/<path:uri>", views.document_fetch_disabled_view, name="document-fetch-disabled"),
]
