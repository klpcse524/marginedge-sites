from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
import sys

# Define Restaurant Model First
class Restaurant(models.Model):
    name = models.CharField(max_length=255, unique=True)
    address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# Define Custom User Model
class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('user', 'User'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    groups = models.ManyToManyField(Group, related_name="customuser_set", blank=True)
    user_permissions = models.ManyToManyField(Permission, related_name="customuser_set", blank=True)

    def __str__(self):
        return self.username

# Define Vendor Model with vendor validation flag.
STATUS_CHOICES = (
    ('Processing', 'Processing'),
    ('Review', 'Review'),
    ('Pending for Approval', 'Pending for Approval'),
    ('Approved', 'Approved'),
    ('Paid', 'Paid'),
    ('Closed', 'Closed'),
)

class Vendor(models.Model):
    vendor_name = models.CharField(max_length=255)
    invoice_number = models.CharField(max_length=100, blank=True, null=True)
    invoice_date = models.DateField(blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    invoice_file = models.FileField(upload_to='invoices/', blank=True, null=True)
    status = models.CharField(max_length=50, default="Processing")
    created_at = models.DateTimeField(auto_now_add=True)
    is_validated = models.BooleanField(default=False)  # Vendor review flag
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    account_number = models.CharField(max_length=100, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=50, blank=True, null=True)
    bank_account_number = models.CharField(max_length=100, blank=True, null=True)
    routing_number = models.CharField(max_length=100, blank=True, null=True)
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    payee_name = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.vendor_name} - {self.invoice_number}"

# Define Invoice Model
class Invoice(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="invoices", null=True, blank=True)
    vendor_name = models.CharField(max_length=255, blank=True, null=True)
    invoice_number = models.CharField(max_length=100, blank=True, null=True)
    invoice_date = models.DateField(blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    invoice_file = models.FileField(upload_to='invoices/', blank=True, null=True)
    status = models.CharField(max_length=50, default="Processing")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (('vendor', 'invoice_number'),)

    def __str__(self):
        return f"Invoice {self.invoice_number} ({self.vendor_name})"

# Define Order Model (unchanged)
class Order(models.Model):
    ORDER_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ]
    order_id = models.CharField(max_length=20, unique=True)
    customer_name = models.CharField(max_length=255)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=ORDER_STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.order_id} - {self.customer_name}"

@receiver(post_save, sender=Vendor)
def sync_vendor_to_invoice(sender, instance, **kwargs):
    # Disabled auto-sync to allow view logic to control record creation.
    pass