from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.conf import settings
from django.conf.urls.static import static
import os

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),  # Ensure your API URLs are correctly defined in api/urls.py
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),  # Login
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),  # Refresh token
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]
    urlpatterns += static('/invoices/', document_root=os.path.join(settings.BASE_DIR, 'invoices'))
