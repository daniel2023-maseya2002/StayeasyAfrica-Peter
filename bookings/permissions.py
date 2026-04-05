# stayease/bookings/permissions.py
from rest_framework import permissions


class IsBookingOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of a booking to access it.
    """
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class IsApartmentOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to allow apartment owners or admin to access.
    """
    def has_object_permission(self, request, view, obj):
        # Admin can access all
        if request.user.role == 'admin':
            return True
        # Apartment owner can access bookings for their apartments
        return obj.apartment.owner == request.user


class CanVerifyPayment(permissions.BasePermission):
    """
    Custom permission for verifying payments.
    Only admin or apartment owner can verify payments.
    """
    def has_object_permission(self, request, view, obj):
        # Admin can verify any payment
        if request.user.role == 'admin':
            return True
        # Apartment owner can verify payments for their apartments
        return obj.apartment.owner == request.user

class IsAdmin(permissions.BasePermission):
    """
    Custom permission to only allow admin users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'admin'