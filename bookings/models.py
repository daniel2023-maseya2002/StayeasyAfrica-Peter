# stayease/bookings/models.py - Add booking_code field
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .utils import generate_unique_booking_code  # Add this import


class Booking(models.Model):
    """
    Booking model representing reservations made by users for apartments.
    Uses manual payment verification system (MTN/Airtel Money).
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        CONFIRMED = 'confirmed', _('Confirmed')
        CANCELLED = 'cancelled', _('Cancelled')
    
    class PaymentMethod(models.TextChoices):
        MTN = 'mtn', _('MTN Mobile Money')
        AIRTEL = 'airtel', _('Airtel Money')
    
    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        SUBMITTED = 'submitted', _('Submitted')
        VERIFIED = 'verified', _('Verified')
    
    # Relationships
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings',
        help_text=_("User who made the booking")
    )
    
    apartment = models.ForeignKey(
        'apartments.Apartment',
        on_delete=models.CASCADE,
        related_name='bookings',
        help_text=_("Apartment being booked")
    )
    
    # Booking details
    booking_code = models.CharField(
        _("booking code"),
        max_length=50,
        unique=True,
        blank=False,
        # Remove any default= from the field
        help_text=_("Unique booking code (e.g., STE-234-AB-93)")
    )
    
    start_date = models.DateField(
        _("start date"),
        help_text=_("Check-in date")
    )
    
    end_date = models.DateField(
        _("end date"),
        help_text=_("Check-out date")
    )
    
    total_price = models.DecimalField(
        _("total price"),
        max_digits=10,
        decimal_places=2,
        help_text=_("Total price for the booking period")
    )
    
    # Booking status
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text=_("Current status of the booking")
    )
    
    # Payment information
    payment_method = models.CharField(
        _("payment method"),
        max_length=10,
        choices=PaymentMethod.choices,
        blank=True,
        null=True,
        help_text=_("Mobile money provider for payment")
    )
    
    payment_reference = models.CharField(
        _("payment reference"),
        max_length=100,
        blank=True,
        null=True,
        help_text=_("Transaction reference number from mobile money")
    )
    
    payment_status = models.CharField(
        _("payment status"),
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        help_text=_("Status of the payment verification")
    )
    
    # Contact information
    phone_number = models.CharField(
        _("phone number"),
        max_length=20,
        help_text=_("Phone number for payment confirmation")
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _("created at"),
        default=timezone.now,
        editable=False
    )
    
    updated_at = models.DateTimeField(
        _("updated at"),
        auto_now=True
    )
    
    class Meta:
        verbose_name = _("booking")
        verbose_name_plural = _("bookings")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['apartment', 'start_date', 'end_date']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['booking_code']),  # Add index for booking_code
        ]
    
    def __str__(self):
        code = self.booking_code or f"#{self.id}"
        return f"Booking {code} - {self.user.email} - {self.apartment.title}"
    
    def clean(self):
        """
        Custom validation for the booking model.
        """
        # Validate dates
        if self.start_date and self.end_date:
            if self.end_date <= self.start_date:
                raise ValidationError({
                    'end_date': _("End date must be after start date.")
                })
            
            if self.start_date < timezone.now().date():
                raise ValidationError({
                    'start_date': _("Start date cannot be in the past.")
                })
        
        # Validate total price is positive
        if self.total_price and self.total_price <= 0:
            raise ValidationError({
                'total_price': _("Total price must be greater than zero.")
            })
    
    def save(self, *args, **kwargs):
        """
        Override save to generate booking code, perform validation, and calculate price.
        """
        # Generate booking code if not provided
        if not self.booking_code or self.booking_code == 'TEMP-000':
            from .utils import generate_unique_booking_code
            self.booking_code = generate_unique_booking_code(Booking)
        
        # Calculate total price if not provided
        if not self.total_price and self.start_date and self.end_date and self.apartment:
            nights = (self.end_date - self.start_date).days
            self.total_price = self.apartment.price_daily * nights
        
        super().save(*args, **kwargs)
    
    def get_nights(self):
        """
        Calculate number of nights for the booking.
        """
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return 0
    
    def can_cancel(self):
        """
        Check if booking can be cancelled.
        Bookings can only be cancelled if they're pending or confirmed.
        """
        return self.status in [self.Status.PENDING, self.Status.CONFIRMED]
    
    def cancel(self):
        """
        Cancel the booking.
        """
        if self.can_cancel():
            self.status = self.Status.CANCELLED
            self.save()
            return True
        return False
    
    def mark_payment_submitted(self, reference):
        """
        Mark payment as submitted with transaction reference.
        """
        self.payment_reference = reference
        self.payment_status = self.PaymentStatus.SUBMITTED
        self.save()
    
    def verify_payment(self):
        """
        Verify payment and confirm booking.
        """
        self.payment_status = self.PaymentStatus.VERIFIED
        self.status = self.Status.CONFIRMED
        self.save()
    
    def is_active(self):
        """
        Check if booking is active (not cancelled and dates are valid).
        """
        return self.status == self.Status.CONFIRMED and self.end_date >= timezone.now().date()