"""Top-level URL conf — delegates everything to the gsapp."""
from django.urls import include, path

urlpatterns = [
    path("", include("gsapp.urls")),
]
