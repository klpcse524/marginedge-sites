# Generated by Django 5.1.7 on 2025-03-28 15:03

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0007_rename_name_vendor_invoice_number_vendor_amount_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="vendor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="invoices",
                to="api.vendor",
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="amount",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True
            ),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="invoice_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="invoice_number",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="status",
            field=models.CharField(default="Processing", max_length=50),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="vendor_name",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="vendor",
            name="amount",
            field=models.DecimalField(decimal_places=2, max_digits=10),
        ),
        migrations.AlterField(
            model_name="vendor",
            name="invoice_date",
            field=models.DateField(
                blank=True, default=django.utils.timezone.now, null=True
            ),
        ),
        migrations.AlterField(
            model_name="vendor",
            name="invoice_number",
            field=models.CharField(max_length=100),
        ),
    ]
