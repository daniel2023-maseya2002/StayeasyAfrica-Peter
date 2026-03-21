# stayease/reviews/models.py
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class Review(models.Model):
    """
    Review model for users to rate and comment on apartments they've booked.
    """
    
    class RatingChoices(models.IntegerChoices):
        ONE_STAR = 1, _('1 Star - Poor')
        TWO_STARS = 2, _('2 Stars - Fair')
        THREE_STARS = 3, _('3 Stars - Good')
        FOUR_STARS = 4, _('4 Stars - Very Good')
        FIVE_STARS = 5, _('5 Stars - Excellent')
    
    # Relationships
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
        help_text=_("User who wrote the review")
    )
    
    apartment = models.ForeignKey(
        'apartments.Apartment',
        on_delete=models.CASCADE,
        related_name='reviews',
        help_text=_("Apartment being reviewed")
    )
    
    # Review details
    rating = models.IntegerField(
        _("rating"),
        choices=RatingChoices.choices,
        help_text=_("Rating from 1 to 5 stars")
    )
    
    comment = models.TextField(
        _("comment"),
        blank=True,
        help_text=_("Detailed review comment (optional)")
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
        verbose_name = _("review")
        verbose_name_plural = _("reviews")
        ordering = ['-created_at']
        unique_together = ['user', 'apartment']  # Ensures one review per user per apartment
        indexes = [
            models.Index(fields=['apartment', 'rating']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['rating']),
        ]
    
    def __str__(self):
        return f"Review by {self.user.email} for {self.apartment.title} - {self.get_rating_display()}"
    
    def clean(self):
        """
        Custom validation for the review model.
        """
        # Validate rating range (already enforced by choices, but adding extra validation)
        if self.rating and not (1 <= self.rating <= 5):
            raise ValidationError({
                'rating': _("Rating must be between 1 and 5.")
            })
        
        # Check if user has actually booked this apartment
        if self.user and self.apartment:
            from bookings.models import Booking
            has_booked = Booking.objects.filter(
                user=self.user,
                apartment=self.apartment,
                status=Booking.Status.CONFIRMED,
                end_date__lte=timezone.now().date()
            ).exists()
            
            if not has_booked:
                raise ValidationError(
                    _("You can only review apartments you have completed a booking for.")
                )
    
    def save(self, *args, **kwargs):
        """
        Override save to perform validation.
        """
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def is_editable(self):
        """
        Check if review can still be edited.
        Reviews can be edited within 30 days of creation.
        """
        return (timezone.now() - self.created_at).days <= 30
    
    def update_rating(self, new_rating):
        """
        Update the rating and save.
        """
        self.rating = new_rating
        self.save()
    
    def update_comment(self, new_comment):
        """
        Update the comment and save.
        """
        self.comment = new_comment
        self.save()