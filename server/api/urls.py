from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import CustomUserViewSet, OrderViewSet, InvoiceViewSet, create_invoice, VendorViewSet, InvoiceUploadView, pending_invoices
from rest_framework.routers import DefaultRouter
from django.conf import settings
from django.conf.urls.static import static


router = DefaultRouter()
router.register(r'users', CustomUserViewSet, basename='users')
router.register(r'orders', OrderViewSet, basename='orders')
router.register(r'invoices', InvoiceViewSet, basename="invoice")
router.register(r'vendors', VendorViewSet, basename='vendor')


urlpatterns = [
    path("", include(router.urls)),
    path("users/", CustomUserViewSet.as_view({'get': 'list', 'post': 'create'}), name="customuser-list"),
    path("orders/", OrderViewSet.as_view({'get': 'list'}), name="list_orders"),
    path("invoices/", InvoiceViewSet.as_view({'get': 'list'}), name="list_invoices"),
    path('api/invoices/', create_invoice, name='create_invoice'),
    
    # ✅ Ensure Token URLs are correct
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("upload_invoice/", InvoiceUploadView.as_view(), name="upload_invoice"),
    path("pending_invoices/", pending_invoices, name="pending_invoices"),
]

