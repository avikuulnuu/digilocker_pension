from django.urls import path

from issuer import views

app_name = "issuer"

urlpatterns = [
    path("pull-uri", views.pull_uri_view, name="pull-uri"),
    path("demo", views.demo_ui, name="demo-ui"),
    path("demo/submit", views.demo_submit, name="demo-submit"),
    path("demo/view-doc/<path:uri>", views.demo_view_doc, name="demo-view-doc"),
    path("document/<path:uri>", views.document_fetch_view, name="document-fetch"),
]
