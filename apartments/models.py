# stayease/apartments/models.py
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class Apartment(models.Model):
    """
    Apartment model representing properties listed by owners.
    """
    
    class AvailabilityStatus(models.TextChoices):
        AVAILABLE = 'available', _('Available')
        BOOKED = 'booked', _('Booked')
    
    class PaymentMethod(models.TextChoices):
        MTN = 'mtn', _('MTN Mobile Money')
        AIRTEL = 'airtel', _('Airtel Money')
    
    # Basic information
    title = models.CharField(
        _("title"),
        max_length=255,
        help_text=_("Title of the apartment listing")
    )
    description = models.TextField(
        _("description"),
        help_text=_("Detailed description of the apartment")
    )
    
    # Pricing
    price_daily = models.DecimalField(
        _("daily price"),
        max_digits=10,
        decimal_places=2,
        help_text=_("Price per night")
    )
    price_weekly = models.DecimalField(
        _("weekly price"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Price per week (optional)")
    )
    price_monthly = models.DecimalField(
        _("monthly price"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Price per month (optional)")
    )
    
    # Payment information
    payment_method = models.CharField(
        _("payment method"),
        max_length=10,
        choices=PaymentMethod.choices,
        help_text=_("Preferred mobile money provider for receiving payments")
    )
    
    payment_number = models.CharField(
        _("payment number"),
        max_length=20,
        help_text=_("Phone number for receiving mobile money payments")
    )
    
    # Location
    district = models.CharField(
        _("district"),
        max_length=100,
        help_text=_("District where the apartment is located")
    )
    sector = models.CharField(
        _("sector"),
        max_length=100,
        help_text=_("Sector or neighborhood")
    )
    address = models.TextField(
        _("address"),
        help_text=_("Full street address")
    )
    nearby_landmarks = models.TextField(
        _("nearby landmarks"),
        blank=True,
        help_text=_("Notable landmarks near the apartment")
    )
    
    # Features
    is_furnished = models.BooleanField(
        _("furnished"),
        default=False,
        help_text=_("Whether the apartment comes with furniture")
    )
    has_wifi = models.BooleanField(
        _("WiFi"),
        default=False,
        help_text=_("Whether WiFi is available")
    )
    has_parking = models.BooleanField(
        _("parking"),
        default=False,
        help_text=_("Whether parking is available")
    )
    
    # Status
    is_verified = models.BooleanField(
        _("verified"),
        default=False,
        help_text=_("Whether the apartment has been verified by admin")
    )
    availability_status = models.CharField(
        _("availability status"),
        max_length=20,
        choices=AvailabilityStatus.choices,
        default=AvailabilityStatus.AVAILABLE,
        help_text=_("Current availability status of the apartment")
    )
    
    # Relationships
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='apartments',
        limit_choices_to={'role': 'owner'},
        help_text=_("Owner of the apartment")
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
        verbose_name = _("apartment")
        verbose_name_plural = _("apartments")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'created_at']),
            models.Index(fields=['district', 'sector']),
            models.Index(fields=['availability_status']),
            models.Index(fields=['payment_method']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.district}"
    
    def save(self, *args, **kwargs):
        """
        Override save to ensure price validation.
        """
        # Validate that at least daily price is set
        if self.price_daily <= 0:
            raise ValueError(_("Daily price must be greater than zero."))
        
        # Ensure weekly price is not less than daily price * 7
        if self.price_weekly and self.price_weekly < self.price_daily * 7:
            self.price_weekly = self.price_daily * 7
        
        # Ensure monthly price is not less than daily price * 30
        if self.price_monthly and self.price_monthly < self.price_daily * 30:
            self.price_monthly = self.price_daily * 30
        
        super().save(*args, **kwargs)

    @property
    def average_rating(self):
        """
        Calculate average rating from all reviews.
        """
        from django.db.models import Avg
        avg = self.reviews.aggregate(Avg('rating'))['rating__avg']
        return round(avg, 1) if avg else None
    
    @property
    def total_reviews(self):
        """
        Get total number of reviews.
        """
        return self.reviews.count()


class ApartmentMedia(models.Model):
    """
    Media files for apartments (images and videos).
    """
    
    class MediaType(models.TextChoices):
        IMAGE = 'image', _('Image')
        VIDEO = 'video', _('Video')
    
    # Relationships
    apartment = models.ForeignKey(
        Apartment,
        on_delete=models.CASCADE,
        related_name='media',
        help_text=_("Apartment this media belongs to")
    )
    
    # File
    file = models.FileField(
        _("file"),
        upload_to='apartments/media/%Y/%m/%d/',
        help_text=_("Upload image or video file")
    )
    
    # Media type
    media_type = models.CharField(
        _("media type"),
        max_length=10,
        choices=MediaType.choices,
        default=MediaType.IMAGE,
        help_text=_("Type of media file")
    )
    
    # Timestamp
    uploaded_at = models.DateTimeField(
        _("uploaded at"),
        default=timezone.now,
        editable=False
    )
    
    class Meta:
        verbose_name = _("apartment media")
        verbose_name_plural = _("apartment media")
        ordering = ['uploaded_at']
        indexes = [
            models.Index(fields=['apartment', 'uploaded_at']),
            models.Index(fields=['media_type']),
        ]
    
    def __str__(self):
        return f"{self.get_media_type_display()} for {self.apartment.title} - {self.uploaded_at.date()}"
    
    def save(self, *args, **kwargs):
        """
        Override save to auto-detect media type from file extension.
        """
        if not self.media_type and self.file:
            # Auto-detect media type from file extension
            file_extension = self.file.name.lower().split('.')[-1]
            image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
            video_extensions = ['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm']
            
            if file_extension in image_extensions:
                self.media_type = self.MediaType.IMAGE
            elif file_extension in video_extensions:
                self.media_type = self.MediaType.VIDEO
        
        super().save(*args, **kwargs)