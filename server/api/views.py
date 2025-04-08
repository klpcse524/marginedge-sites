# api/views.py
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from .models import CustomUser, Invoice, Vendor
from .serializers import CustomUserSerializer, UserSerializer, InvoiceSerializer, VendorSerializer
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
import json
import logging
from datetime import datetime
from .hybrid_invoice_extractor import extract_invoice_data_hybrid

logger = logging.getLogger(__name__)

# -------------------------------
# Authentication Endpoints
# -------------------------------
@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    email = request.data.get("email")
    password = request.data.get("password")
    try:
        user = get_user_model().objects.get(email=email)
    except get_user_model().DoesNotExist:
        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
    if not user.check_password(password):
        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
    refresh = RefreshToken.for_user(user)
    return Response({
        "refresh": str(refresh),
        "access": str(refresh.access_token),
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role,
        }
    })

class CustomUserViewSet(viewsets.ModelViewSet):
    queryset = get_user_model().objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [IsAuthenticated]

# -------------------------------
# Vendor Endpoints
# -------------------------------
class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.all().order_by('-id')
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

# -------------------------------
# Invoice Endpoints
# -------------------------------
class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all().order_by('-created_at')
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        # Check if vendor_name is provided in the request data.
        vendor_name = request.data.get("vendor_name")
        if vendor_name and instance.vendor:
            # Update the vendor record.
            instance.vendor.vendor_name = vendor_name
            instance.vendor.save()

        # Remove vendor_name from the request data so it doesn't conflict with the read-only field.
        mutable_data = request.data.copy()
        if "vendor_name" in mutable_data:
            mutable_data.pop("vendor_name")

        serializer = self.get_serializer(instance, data=mutable_data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Optionally, update vendor totals.
        if instance.vendor:
            instance.vendor.update_totals()

        return Response(serializer.data)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def pending_invoices(request):
    invoices = Invoice.objects.filter(status="Pending for review")
    serializer = InvoiceSerializer(invoices, many=True)
    return Response(serializer.data)

# -------------------------------
# Invoice File Upload Endpoint
# -------------------------------
def process_invoice_file(invoice_file):
    """
    Placeholder function for processing the invoice file.
    Replace this with your actual OCR/NER/NLP logic.
    It should return a dictionary containing both vendor and invoice details.
    """
    return {
        'vendor_name': 'Demo Vendor',
        'account_number': '123456',
        'items_supplied': 'Item A, Item B',
        'category': 'Office Supplies',
        'address_line_1': '123 Main St',
        'address_line_2': '',
        'city': 'Anytown',
        'state': 'State',
        'zip_code': '12345',
        'contact_email': 'vendor@example.com',
        'contact_phone': '555-1234',
        'bank_account_number': '987654321',
        'routing_number': '111000',
        'bank_name': 'Demo Bank',
        'account_payee': 'Demo Vendor Payee',
        'invoice_number': 'INV-001',
        'invoice_date': datetime.today().date(),
        'amount': 100.00,
        'status': 'Pending for review',
    }

from django.db import IntegrityError

class InvoiceUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        invoice_file = request.FILES.get('invoice_file')
        if not invoice_file:
            return Response({"error": "No file uploaded."}, status=400)
        
        try:
            # Extract data from invoice
            extracted = extract_invoice_data_hybrid(invoice_file)
            
            # Create or update vendor
            vendor, created = Vendor.objects.get_or_create(
                vendor_name=extracted['vendor_name'],
                defaults={
                    "account_number": extracted.get('account_number'),
                    "contact_email": extracted.get('contact_email'),
                    "contact_phone": extracted.get('contact_phone'),
                    "address_line_1": extracted.get('address_line_1'),
                    "address_line_2": extracted.get('address_line_2'),
                    "city": extracted.get('city'),
                    "state": extracted.get('state'),
                    "zip_code": extracted.get('zip_code'),
                    "bank_account_number": extracted.get('bank_account_number'),
                    "routing_number": extracted.get('routing_number'),
                    "bank_name": extracted.get('bank_name'),
                    "account_payee": extracted.get('account_payee'),
                    "category": self.determine_vendor_category(extracted['vendor_name'])
                }
            )
            
            # Check if an invoice with this vendor and invoice_number already exists (case-insensitive)
            existing_invoice = Invoice.objects.filter(
                vendor=vendor,
                invoice_number__iexact=extracted['invoice_number']
            ).first()
            
            if existing_invoice:
                return Response({
                "message": "Invoice already exists",
                "invoice_id": existing_invoice.id,
                "is_new": False
                }, status=200)
            
            # Try to create the invoice
            try:
                invoice = Invoice.objects.create(
                    vendor=vendor,
                    invoice_number=extracted['invoice_number'],
                    invoice_date=extracted['invoice_date'],
                    amount=extracted['amount'],
                    status="Pending for review",
                    invoice_file=invoice_file
                )
            except IntegrityError:
                # If a duplicate is raised, fetch the existing invoice and return it
                existing_invoice = Invoice.objects.filter(
                    vendor=vendor,
                    invoice_number__iexact=extracted['invoice_number']
                ).first()
                if existing_invoice:
                    return Response({
                    "message": "Invoice already exists",
                    "invoice_id": existing_invoice.id,
                    "is_new": False
                    }, status=200)
                else:
                    raise
            
            vendor.update_totals()
            
            return Response({
            "message": "Invoice processed successfully",
            "invoice_id": invoice.id,
            "is_new": True,
            "extracted_data": extracted
            }, status=201)
            
        except Exception as e:
            logger.error(f"Invoice processing error: {str(e)}", exc_info=True)
            return Response({
                "error": "Failed to process invoice",
                "details": str(e)
            }, status=400)
    
    def determine_vendor_category(self, vendor_name):
        """Simple heuristic to categorize vendors"""
        vendor_name = vendor_name.lower()
        categories = {
            'food': ['meat', 'produce', 'dairy', 'seafood', 'bakery'],
            'beverage': ['wine', 'beer', 'liquor', 'beverage'],
            'supplies': ['paper', 'cleaning', 'chemical', 'uniform'],
            'equipment': ['kitchen', 'appliance', 'repair']
        }
        for category, keywords in categories.items():
            if any(keyword in vendor_name for keyword in keywords):
                return category.capitalize()
        return "Other"

