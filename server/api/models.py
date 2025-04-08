# api/models.py
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.db.models import Sum
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

# -------------------------------
# Custom User Model (Users remain)
# -------------------------------
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

# -------------------------------
# Vendor Model
# -------------------------------
class Vendor(models.Model):
    vendor_name = models.CharField(max_length=500, unique=True)
    account_number = models.CharField(max_length=100, blank=True, null=True)  # Customer registered number at vendor
    items_supplied = models.TextField(blank=True, null=True)  # e.g., comma-separated list or JSON array
    category = models.CharField(max_length=255, blank=True, null=True)
    total_amount_purchased = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    address_line_1 = models.CharField(max_length=255, blank=True, null=True)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=50, blank=True, null=True)
    bank_account_number = models.CharField(max_length=100, blank=True, null=True)
    routing_number = models.CharField(max_length=100, blank=True, null=True)
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    account_payee = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.vendor_name

    def update_totals(self):
        total = self.invoices.aggregate(total=Sum('amount'))['total'] or 0
        print(f"Updating totals for vendor {self.vendor_name}: {total}")  # Debug output
        self.total_amount_purchased = total
        self.save()

# -------------------------------
# Invoice Model
# -------------------------------
class Invoice(models.Model):
    STATUS_CHOICES = (
        ('Pending for review', 'Pending for review'),
        ('Pending for approval', 'Pending for approval'),
        ('Approved', 'Approved'),
        ('Paid', 'Paid'),
        ('Closed', 'Closed'),
    )
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='invoices')
    invoice_number = models.CharField(max_length=100)
    invoice_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    invoice_file = models.FileField(upload_to='invoices/', blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Pending for review')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (('vendor', 'invoice_number'),)

    def __str__(self):
        return f"Invoice {self.invoice_number} ({self.vendor.vendor_name})"
    
@receiver(post_save, sender=Invoice)
def update_vendor_total_on_save(sender, instance, **kwargs):
    # When an invoice is saved (created or updated), update its vendor totals.
    if instance.vendor:
        instance.vendor.update_totals()

@receiver(post_delete, sender=Invoice)
def update_vendor_total_on_delete(sender, instance, **kwargs):
    # When an invoice is deleted, update its vendor totals.
    if instance.vendor:
        instance.vendor.update_totals()
