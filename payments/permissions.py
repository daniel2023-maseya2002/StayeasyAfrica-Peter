# stayease/payments/permissions.py
from rest_framework import permissions


class IsBookingOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of a booking to submit payment.
    """
    def has_permission(self, request, view):
        if view.action == 'create' or request.method == 'POST':
            booking_id = request.data.get('booking_id')
            if booking_id:
                from bookings.models import Booking
                try:
                    booking = Booking.objects.get(id=booking_id)
                    return booking.user == request.user
                except Booking.DoesNotExist:
                    return False
        return True
    
    def has_object_permission(self, request, view, obj):
        # Only booking owner can access
        return obj.booking.user == request.user


class CanVerifyPayment(permissions.BasePermission):
    """
    Custom permission for verifying/rejecting payments.
    Only admin or apartment owner can verify/reject payments.
    """
    def has_object_permission(self, request, view, obj):
        # Check if user is authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin can verify/reject any payment
        if request.user.role == 'admin':
            return True
        
        # Apartment owner can verify/reject payments for their apartments
        return obj.booking.apartment.owner == request.user


class IsAdmin(permissions.BasePermission):
    """
    Custom permission to only allow admin users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'admin'
    
    def has_object_permission(self, request, view, obj):
        return request.user and request.user.is_authenticated and request.user.role == 'admin'