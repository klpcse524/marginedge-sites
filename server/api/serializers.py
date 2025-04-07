# api/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Vendor, Invoice, CustomUser

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'role']

class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = '__all__'

class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = '__all__'

class InvoiceSerializer(serializers.ModelSerializer):
    vendor = VendorSerializer(read_only=True)
    vendor_id = serializers.PrimaryKeyRelatedField(
        queryset=Vendor.objects.all(),
        source='vendor',
        write_only=True,
        required=False
    )
    id = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Invoice
        fields = ['id', 'vendor', 'vendor_id', 'invoice_number', 'invoice_date', 'amount', 'invoice_file', 'status', 'created_at']
