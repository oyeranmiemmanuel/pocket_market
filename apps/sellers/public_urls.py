"""
Public-facing seller storefront URLs - deliberately separate from
apps.sellers.urls (the seller dashboard, mounted at /seller/...).

This needs its own root-level include at /store/ since /store/<slug>/ is
a different prefix from the rest of this app's URLs. Add this one line
to your project's root urls.py:

    path("store/", include("apps.sellers.public_urls")),

(The dashboard include should already look like
`path("seller/", include("apps.sellers.urls"))` - this is a second,
separate include for the same app, not a replacement.)
"""

from django.urls import path

from . import views

app_name = "store"

urlpatterns = [
    path("<slug:slug>/", views.public_store_view, name="detail"),
]
