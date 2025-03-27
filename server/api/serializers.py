from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Restaurant, Vendor, CustomUser, Invoice, Order
from api.models import Invoice
from datetime import datetime

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'role']

class RestaurantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = '__all__'

class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = '__all__'

class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = '__all__'

class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = '__all__'

class InvoiceSerializer(serializers.ModelSerializer):
    invoice_file = serializers.FileField(required=False, allow_null=True)
    
    class Meta:
        model = Invoice
        fields = '__all__'
