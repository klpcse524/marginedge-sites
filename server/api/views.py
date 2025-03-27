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
from .models import CustomUser, Order, Invoice
from .serializers import CustomUserSerializer, OrderSerializer, InvoiceSerializer
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.authtoken.views import ObtainAuthToken
import json

from .models import Restaurant, Vendor, Invoice, Order, CustomUser
from .serializers import (
    UserSerializer, RestaurantSerializer, VendorSerializer, 
    InvoiceSerializer, OrderSerializer
)

from rest_framework.parsers import JSONParser
from rest_framework.views import APIView


class InvoiceView(APIView):  # ✅ This will now be recognized
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

# -------------------------------------
# 🛠️ Role-based access decorator
# -------------------------------------
def role_required(allowed_roles=[]):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.is_authenticated and request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            return JsonResponse({"error": "Unauthorized"}, status=403)
        return wrapper
    return decorator

# -------------------------------------
# 🔐 LOGIN API (Uses Email & Password)
# -------------------------------------
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
def login_view(request):
    username = request.data.get("username")
    password = request.data.get("password")

    user = authenticate(username=username, password=password)
    if user:
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key})
    return Response({"error": "Invalid credentials"}, status=401)

# -------------------------------------
# 🏢 CREATE RESTAURANT (Superuser Only)
# -------------------------------------
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

# -------------------------------------
# 👤 REGISTER USER (Admin Can Create Users)
# -------------------------------------
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

    # Validate restaurant exists
    try:
        restaurant = Restaurant.objects.get(id=restaurant_id)
    except Restaurant.DoesNotExist:
        return Response({"error": "Invalid restaurant ID."}, status=400)

    # Create User
    user = CustomUser.objects.create(
        username=username,
        email=email,
        password=make_password(password),  # Hash password
        role=role,
        restaurant=restaurant,
    )

    return Response({"message": "User registered successfully."}, status=201)

# -------------------------------------
# 👥 USER MANAGEMENT (View Users)
# -------------------------------------
class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

# -------------------------------------
# 🏢 RESTAURANT MANAGEMENT (View & Manage)
# -------------------------------------
class RestaurantViewSet(viewsets.ModelViewSet):
    queryset = Restaurant.objects.all()
    serializer_class = RestaurantSerializer
    permission_classes = [IsAuthenticated]

class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated]

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
# -------------------------------------
# 📦 ORDERS MANAGEMENT (CRUD Operations)
# -------------------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_orders(request):
    """ Fetch all orders """
    orders = Order.objects.all()
    serializer = OrderSerializer(orders, many=True)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_order(request):
    """ Create a new order """
    serializer = OrderSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_detail(request, order_id):
    """ Fetch a specific order by ID """
    try:
        order = Order.objects.get(order_id=order_id)
        serializer = OrderSerializer(order)
        return Response(serializer.data)
    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=404)

@api_view(["POST"])
@permission_classes([AllowAny])
def user_login(request):
    email = request.data.get("email")
    password = request.data.get("password")

    if not email or not password:
        return Response({"error": "Email and password are required"}, status=status.HTTP_400_BAD_REQUEST)

    print(f"DEBUG: Attempting login for email={email}")

    # Authenticate user by email
    try:
        user = CustomUser.objects.get(email=email)
    except CustomUser.DoesNotExist:
        print("DEBUG: User not found")
        return Response({"error": "Invalid credentials. Please try again."}, status=status.HTTP_401_UNAUTHORIZED)

    if not user.check_password(password):
        print("DEBUG: Incorrect password")
        return Response({"error": "Invalid credentials. Please try again."}, status=status.HTTP_401_UNAUTHORIZED)

    print(f"DEBUG: User {user.email} authenticated successfully")

    # Generate JWT token
    refresh = RefreshToken.for_user(user)
    update_last_login(None, user)

    return Response({
        "refresh": str(refresh),
        "access": str(refresh.access_token),
        "user": {
            "id": user.id,
            "email": user.email,
            "role": getattr(user, "role", "user")
        }
    })

# 📝 Fetch all invoices
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_invoices(request):
    invoices = Invoice.objects.all().order_by("-id")
    serializer = InvoiceSerializer(invoices, many=True)
    return Response(serializer.data)

# 📝 Create a new invoice (manual entry)
@api_view(['POST'])
@permission_classes([IsAuthenticated])  # ✅ Require authentication
def create_invoice(request):
    serializer = InvoiceSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)

# 📂 Upload invoice file
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_invoice(request):
    file = request.FILES.get("invoice_file")
    if not file:
        return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

    # Save the uploaded file (Modify this based on your storage settings)
    invoice = Invoice.objects.create(invoice_file=file)
    return Response({"message": "Invoice uploaded successfully", "file_url": invoice.invoice_file.url}, status=status.HTTP_201_CREATED)

# ✏️ Edit invoice
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def edit_invoice(request, invoice_id):
    try:
        invoice = Invoice.objects.get(id=invoice_id)
        data = json.loads(request.body)
        serializer = InvoiceSerializer(invoice, data=data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    except Invoice.DoesNotExist:
        return Response({"error": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND)

# ❌ Delete invoice
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
@permission_classes([IsAuthenticated])  # Require authentication
def list_invoices(request):
    invoices = Invoice.objects.all()
    serializer = InvoiceSerializer(invoices, many=True)
    return Response(serializer.data)

@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_invoices(request):
    invoices = Invoice.objects.all()
    serializer = InvoiceSerializer(invoices, many=True)
    return Response(serializer.data)