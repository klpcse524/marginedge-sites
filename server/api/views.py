from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import update_last_login
from django.contrib.auth.hashers import make_password
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.authtoken.models import Token
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from functools import wraps
from .models import CustomUser, Order, Invoice, Vendor, Restaurant
from .serializers import CustomUserSerializer, OrderSerializer, InvoiceSerializer, VendorSerializer, UserSerializer, RestaurantSerializer
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.views import APIView
from .hybrid_invoice_extractor import extract_invoice_data_hybrid
import json
import logging
from datetime import datetime

class InvoiceView(APIView):
    def get(self, request):
        invoices = Invoice.objects.all()
        serializer = InvoiceSerializer(invoices, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = InvoiceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

def role_required(allowed_roles=[]):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.is_authenticated and request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            return JsonResponse({"error": "Unauthorized"}, status=403)
        return wrapper
    return decorator

@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    email = request.data.get("email")
    password = request.data.get("password")
    try:
        user = CustomUser.objects.get(email=email)
    except CustomUser.DoesNotExist:
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

@api_view(["POST"])
@permission_classes([IsAuthenticated])
@role_required(["superuser"])
def create_restaurant(request):
    data = request.data
    name = data.get("name")
    address = data.get("address")
    if not name or not address:
        return Response({"error": "Name and address are required."}, status=400)
    restaurant = Restaurant.objects.create(name=name, address=address)
    return Response({"message": "Restaurant created successfully.", "restaurant_id": restaurant.id})

@api_view(["POST"])
@permission_classes([IsAuthenticated])
@role_required(["admin"])
def register_user(request):
    data = request.data
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    role = data.get("role", "user")
    restaurant_id = data.get("restaurant_id")
    if not username or not email or not password or not restaurant_id:
        return Response({"error": "All fields are required."}, status=400)
    try:
        restaurant = Restaurant.objects.get(id=restaurant_id)
    except Restaurant.DoesNotExist:
        return Response({"error": "Invalid restaurant ID."}, status=400)
    user = CustomUser.objects.create(
        username=username,
        email=email,
        password=make_password(password),
        role=role,
        restaurant=restaurant,
    )
    return Response({"message": "User registered successfully."}, status=201)

class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

class RestaurantViewSet(viewsets.ModelViewSet):
    queryset = Restaurant.objects.all()
    serializer_class = RestaurantSerializer
    permission_classes = [IsAuthenticated]

class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.all().order_by('-created_at')
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

class CustomUserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all().order_by('-created_at')
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CustomAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({'token': token.key})

# New pending_invoices endpoint:
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def pending_invoices(request):
    invoices = Invoice.objects.filter(status="Pending Review")
    serializer = InvoiceSerializer(invoices, many=True)
    return Response(serializer.data)

logger = logging.getLogger(__name__)

class InvoiceUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        print("Received Authorization header:", auth_header)  # Debug: log header

        file_obj = request.FILES.get('invoice_file')
        if not file_obj:
            return Response({"error": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            parsed_data = extract_invoice_data_hybrid(file_obj)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # (rest of your code...)
        
        # Reset the file pointer for saving.
        file_obj.seek(0)
        
        vendor_name = parsed_data.get("vendor_name", "")[:255]
        invoice_number = parsed_data.get("invoice_number", "")
        
        # Check for duplicate invoice using vendor name and invoice number.
        existing_invoice = Invoice.objects.filter(
            vendor__vendor_name__iexact=vendor_name,
            invoice_number=invoice_number
        ).first()
        if existing_invoice:
            return Response({
                "message": "Invoice already existed.",
                "invoice_id": existing_invoice.id
            }, status=status.HTTP_200_OK)
        
        # Update or create Vendor record.
        vendor = Vendor.objects.filter(vendor_name__iexact=vendor_name).first()
        if vendor:
            vendor.invoice_number = invoice_number
            vendor.invoice_date = parsed_data.get("invoice_date", "1970-01-01")
            vendor.amount = parsed_data.get("amount", "0.00")
            vendor.invoice_file = file_obj
            vendor.status = "Processing"
            vendor.save()
        else:
            vendor = Vendor.objects.create(
                vendor_name=vendor_name,
                invoice_number=invoice_number,
                invoice_date=parsed_data.get("invoice_date", "1970-01-01"),
                amount=parsed_data.get("amount", "0.00"),
                invoice_file=file_obj,
                status="Pending Review",
                is_validated=False
            )
        
        # Reset file pointer again for invoice saving.
        file_obj.seek(0)
        
        # Set invoice status based on vendor validation.
        invoice_status = "Approved" if vendor.is_validated else "Pending Review"
        
        invoice = Invoice.objects.create(
            vendor=vendor,
            vendor_name=vendor.vendor_name,
            invoice_number=vendor.invoice_number,
            invoice_date=vendor.invoice_date,
            amount=vendor.amount,
            invoice_file=file_obj,
            status=invoice_status,
        )
        return Response({"message": "Invoice uploaded successfully.", "invoice_id": invoice.id}, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_orders(request):
    orders = Order.objects.all()
    serializer = OrderSerializer(orders, many=True)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_order(request):
    serializer = OrderSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_detail(request, order_id):
    try:
        order = Order.objects.get(order_id=order_id)
        serializer = OrderSerializer(order)
        return Response(serializer.data)
    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=404)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_invoices(request):
    invoices = Invoice.objects.all().order_by("-id")
    serializer = InvoiceSerializer(invoices, many=True)
    return Response(serializer.data)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_invoice(request):
    serializer = InvoiceSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_invoice(request):
    file = request.FILES.get("invoice_file")
    if not file:
        return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)
    invoice = Invoice.objects.create(invoice_file=file)
    return Response({"message": "Invoice uploaded successfully", "file_url": invoice.invoice_file.url}, status=status.HTTP_201_CREATED)

@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def edit_invoice(request, invoice_id):
    try:
        invoice = Invoice.objects.get(id=invoice_id)
    except Invoice.DoesNotExist:
        return Response({"error": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return Response({"error": "Invalid JSON payload."}, status=status.HTTP_400_BAD_REQUEST)

    serializer = InvoiceSerializer(invoice, data=data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    else:
        # Log the errors to help debug which fields are causing issues
        print("Serializer errors:", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_invoice(request, invoice_id):
    try:
        invoice = Invoice.objects.get(id=invoice_id)
        invoice.delete()
        return Response({"message": "Invoice deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
    except Invoice.DoesNotExist:
        return Response({"error": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_invoices(request):
    invoices = Invoice.objects.all()
    serializer = InvoiceSerializer(invoices, many=True)
    return Response(serializer.data)

@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def review_invoice(request, invoice_id):
    try:
        invoice = Invoice.objects.get(id=invoice_id)
    except Invoice.DoesNotExist:
        return Response({"error": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND)
    
    data = json.loads(request.body)
    serializer = InvoiceSerializer(invoice, data=data, partial=True)
    if serializer.is_valid():
        serializer.save()
        vendor = invoice.vendor
        if data.get("approved_vendor"):
            vendor.is_validated = True
            vendor.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
