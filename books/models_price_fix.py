# books/models.py — PRICE VALIDATION FIX
# Add MinValueValidator to the price field and enforce in clean()/save()

from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db import models

# ---------------------------------------------------------------------------
# In class Book: replace the price field and enhance save() / add clean()
# ---------------------------------------------------------------------------

# BEFORE:
#   price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

# AFTER:
price = models.DecimalField(
    max_digits=10,
    decimal_places=2,
    default=Decimal("0.00"),
    validators=[MinValueValidator(Decimal("0.00"))],
    help_text="Book price in ETB. Must be >= 0.",
)

# ---------------------------------------------------------------------------
# Add (or merge into) the Book model methods:
# ---------------------------------------------------------------------------

def clean(self):
    """Business-rule validation (called by full_clean / ModelForms)."""
    super().clean()
    if self.price is not None and self.price < 0:
        raise ValidationError({"price": "Book price cannot be negative."})
    if getattr(self, "is_free", False):
        self.price = Decimal("0.00")


def save(self, *args, **kwargs):
    # Enforce non-negative price even if clean() was skipped
    if self.price is not None and self.price < 0:
        raise ValidationError("Book price cannot be negative.")
    if getattr(self, "is_free", False) or self.price == 0:
        self.price = Decimal("0.00")
        # optionally: self.is_free = True
    super().save(*args, **kwargs)
