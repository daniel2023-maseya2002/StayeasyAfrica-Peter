# stayease/payments/models.py
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class Payment(models.Model):
    """
    Payment model for tracking manual payments (MTN/Airtel Money).
    Each booking has exactly one payment record.
    """
    
    class PaymentMethod(models.TextChoices):
        MTN = 'mtn', _('MTN Mobile Money')
        AIRTEL = 'airtel', _('Airtel Money')
    
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        SUBMITTED = 'submitted', _('Submitted')
        VERIFIED = 'verified', _('Verified')
        REJECTED = 'rejected', _('Rejected')
    
    # Relationship - One booking has one payment
    booking = models.OneToOneField(
        'bookings.Booking',
        on_delete=models.CASCADE,
        related_name='payment',
        help_text=_("The booking associated with this payment")
    )
    
    # Payment details
    amount = models.DecimalField(
        _("amount"),
        max_digits=10,
        decimal_places=2,
        help_text=_("Payment amount")
    )
    
    payment_method = models.CharField(
        _("payment method"),
        max_length=10,
        choices=PaymentMethod.choices,
        help_text=_("Mobile money provider")
    )
    
    transaction_id = models.CharField(
        _("transaction ID"),
        max_length=100,
        blank=True,
        null=True,
        help_text=_("Transaction reference from mobile money SMS")
    )
    
    # Payment status
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text=_("Current status of the payment")
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _("created at"),
        default=timezone.now,
        editable=False
    )
    
    verified_at = models.DateTimeField(
        _("verified at"),
        blank=True,
        null=True,
        help_text=_("When the payment was verified or rejected")
    )
    
    class Meta:
        verbose_name = _("payment")
        verbose_name_plural = _("payments")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['booking', 'status']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['payment_method', 'status']),
        ]
    
    def __str__(self):
        return f"Payment {self.id} - Booking {self.booking.id} - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        """
        Override save to handle verification timestamp.
        """
        # Update verified_at when status changes to verified or rejected
        if self.status in [self.Status.VERIFIED, self.Status.REJECTED]:
            if not self.verified_at:
                self.verified_at = timezone.now()
        else:
            # Clear verified_at if status is not verified or rejected
            self.verified_at = None
        
        super().save(*args, **kwargs)
    
    def submit(self, transaction_id):
        """
        Mark payment as submitted with transaction ID.
        """
        self.transaction_id = transaction_id
        self.status = self.Status.SUBMITTED
        self.save()
    
    def verify(self):
        """
        Mark payment as verified.
        """
        self.status = self.Status.VERIFIED
        self.verified_at = timezone.now()
        self.save()
    
    def reject(self, reason=None):
        """
        Mark payment as rejected.
        """
        self.status = self.Status.REJECTED
        self.verified_at = timezone.now()
        self.save()
        
        # Optionally store rejection reason if added later
        if reason:
            # Could add a rejection_reason field if needed
            pass
    
    def is_pending(self):
        """Check if payment is pending."""
        return self.status == self.Status.PENDING
    
    def is_submitted(self):
        """Check if payment is submitted."""
        return self.status == self.Status.SUBMITTED
    
    def is_verified(self):
        """Check if payment is verified."""
        return self.status == self.Status.VERIFIED
    
    def is_rejected(self):
        """Check if payment is rejected."""
        return self.status == self.Status.REJECTED