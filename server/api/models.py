from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.utils.timezone import now

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

# Define Vendor Model Before Invoice
class Vendor(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name
    
# Define Invoice Model Before Order
STATUS_CHOICES = (
    ('Processing', 'Processing'),
    ('Review', 'Review'),
    ('Pending for Approval', 'Pending for Approval'),
    ('approved', 'Approved'),
    ('Paid', 'Paid'),
    ('Closed', 'Closed'),
)

class Invoice(models.Model):
    vendor_name = models.CharField(max_length=255)
    invoice_number = models.CharField(max_length=255)
    invoice_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    invoice_file = models.FileField(upload_to='invoices/', null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Processing')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.invoice_number
    
# Define Order Model
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

# class CustomUser(AbstractUser):
#     # Add extra fields if needed
#     pass

# class CustomUser(AbstractUser):
#     groups = models.ManyToManyField(Group, related_name="customuser_set", blank=True)
#     user_permissions = models.ManyToManyField(Permission, related_name="customuser_set", blank=True)

#     def __str__(self):
#         return self.username