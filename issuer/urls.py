from django.urls import path

from issuer import views

app_name = "issuer"

urlpatterns = [
    path("pull-uri", views.pull_uri_view, name="pull-uri"),
    path("document/<path:uri>", views.document_fetch_view, name="document-fetch"),
]
