# stayease/apartments/permissions.py
from rest_framework import permissions
from .models import Apartment


class IsOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of an apartment to edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner of the apartment
        return obj.owner == request.user


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to allow admin full access, others read-only.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and request.user.role == 'admin'
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.role == 'admin'


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to allow owners to edit, others read-only.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner
        return obj.owner == request.user


class CanCreateApartment(permissions.BasePermission):
    """
    Custom permission to only allow users with role 'owner' to create apartments.
    """
    def has_permission(self, request, view):
        # Check if it's a POST request (create operation)
        if request.method == 'POST':
            return request.user and request.user.is_authenticated and request.user.role == 'owner'
        return True