# api/urls.py
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    CustomUserViewSet, 
    InvoiceViewSet, 
    VendorViewSet, 
    InvoiceUploadView, 
    pending_invoices,
    login_view
)
from rest_framework.routers import DefaultRouter
from django.conf import settings
from django.conf.urls.static import static

router = DefaultRouter()
router.register(r'users', CustomUserViewSet, basename='users')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'vendors', VendorViewSet, basename='vendor')

urlpatterns = [
    path("", include(router.urls)),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("upload_invoice/", InvoiceUploadView.as_view(), name="upload_invoice"),
    path("pending_invoices/", pending_invoices, name="pending_invoices"),
    path("login/", login_view, name="login"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
