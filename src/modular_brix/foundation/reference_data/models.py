import uuid

from django.db import models


class Country(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    iso2 = models.CharField(max_length=2, unique=True)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)


class Currency(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    iso3 = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=120)
    decimal_places = models.PositiveSmallIntegerField(default=2)
    is_active = models.BooleanField(default=True)


class Unit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=24, unique=True)
    label = models.CharField(max_length=80)
    is_active = models.BooleanField(default=True)


class TaxCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=32)
    label = models.CharField(max_length=120)
    rate = models.DecimalField(max_digits=6, decimal_places=3)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["code", "valid_from"], name="uq_tax_code_valid_from")
        ]


class PaymentTerm(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=32, unique=True)
    label = models.CharField(max_length=120)
    days = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)
