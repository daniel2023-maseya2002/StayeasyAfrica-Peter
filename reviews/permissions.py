# stayease/reviews/permissions.py
from rest_framework import permissions


class IsReviewOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of a review to edit/delete it.
    """
    def has_object_permission(self, request, view, obj):
        # Only the review owner can modify or delete
        return obj.user == request.user


class CanCreateReview(permissions.BasePermission):
    """
    Custom permission to only allow users who have completed a booking to create a review.
    """
    def has_permission(self, request, view):
        if view.action == 'create' or request.method == 'POST':
            apartment_id = request.data.get('apartment')
            if apartment_id:
                from bookings.models import Booking
                from django.utils import timezone
                
                # Check if user has a confirmed and completed booking for this apartment
                has_booked = Booking.objects.filter(
                    user=request.user,
                    apartment_id=apartment_id,
                    status=Booking.Status.CONFIRMED,
                    end_date__lte=timezone.now().date()
                ).exists()
                
                return has_booked
        return True