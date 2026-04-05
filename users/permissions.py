# stayease/users/permissions.py
from rest_framework import permissions
from .models import User
from rest_framework import permissions
import logging

logger = logging.getLogger(__name__)


class IsAdmin(permissions.BasePermission):
    """
    Custom permission to only allow admin users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == User.Role.ADMIN
    
    def has_object_permission(self, request, view, obj):
        return request.user and request.user.is_authenticated and request.user.role == User.Role.ADMIN


class IsOwnerOrSelf(permissions.BasePermission):
    """
    Custom permission to allow users to access only their own data.
    Admin has full access.
    """
    def has_permission(self, request, view):
        # For list operations, check if user is authenticated
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Admin can access any user
        if request.user.role == User.Role.ADMIN:
            return True
        
        # Users can only access their own data
        return obj == request.user


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to allow admin full access, others read-only.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_authenticated and request.user.role == User.Role.ADMIN
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return obj == request.user or request.user.role == User.Role.ADMIN
        return request.user.role == User.Role.ADMIN or obj == request.user
    
class IsAdmin(permissions.BasePermission):
    """
    Custom permission to only allow admin users.
    """
    def has_permission(self, request, view):
        logger.info(f"=== IsAdmin Check ===")
        logger.info(f"User authenticated: {request.user.is_authenticated if request.user else False}")
        if request.user and request.user.is_authenticated:
            logger.info(f"User email: {request.user.email}")
            logger.info(f"User role: {getattr(request.user, 'role', None)}")
            logger.info(f"User role type: {type(getattr(request.user, 'role', None))}")
        
        result = request.user and request.user.is_authenticated and request.user.role == User.Role.ADMIN
        logger.info(f"Result: {result}")
        return result
    
    def has_object_permission(self, request, view, obj):
        return request.user and request.user.is_authenticated and request.user.role == User.Role.ADMIN
