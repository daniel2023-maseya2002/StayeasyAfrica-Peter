# stayease/bookings/views.py
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import Booking
from .serializers import (
    BookingSerializer, BookingSubmitPaymentSerializer,
    BookingVerifyPaymentSerializer, BookingCancelSerializer
)
from .permissions import (
    IsBookingOwner, IsApartmentOwnerOrAdmin, CanVerifyPayment, IsAdmin
)
from django.contrib.auth import get_user_model
from utils.email_utils import EmailNotificationService
from django.db import transaction

User = get_user_model()
class BookingCreateView(generics.CreateAPIView):
    """
    Create a new booking.
    """
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @transaction.atomic
    def perform_create(self, serializer):
        """
        Create booking and send notifications.
        """
        # Create booking
        booking = serializer.save(user=self.request.user)
        
        # Get all admin emails
        admin_emails = User.objects.filter(
            role='admin',
            is_active=True
        ).values_list('email', flat=True)
        
        # Send email notifications
        EmailNotificationService.send_booking_created_email(
            booking=booking,
            admin_emails=list(admin_emails)
        )
        
        return booking

class MyBookingsView(generics.ListAPIView):
    """
    List all bookings for the logged-in user.
    """
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'payment_status']
    search_fields = ['apartment__title', 'payment_reference']
    ordering_fields = ['start_date', 'created_at', 'total_price']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Return bookings for the current user.
        """
        return Booking.objects.filter(
            user=self.request.user
        ).select_related('user', 'apartment', 'apartment__owner')


class OwnerBookingsView(generics.ListAPIView):
    """
    List bookings for apartments owned by the logged-in user.
    """
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'payment_status', 'apartment']
    search_fields = ['user__email', 'user__full_name', 'payment_reference']
    ordering_fields = ['start_date', 'created_at', 'total_price']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Return bookings for apartments owned by the current user.
        """
        user = self.request.user
        
        # Admin can see all bookings
        if user.role == 'admin':
            return Booking.objects.all().select_related('user', 'apartment', 'apartment__owner')
        
        # Owners see bookings for their apartments
        return Booking.objects.filter(
            apartment__owner=user
        ).select_related('user', 'apartment', 'apartment__owner')


class BookingDetailView(generics.RetrieveAPIView):
    """
    Retrieve booking details.
    """
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Booking.objects.all().select_related('user', 'apartment', 'apartment__owner')
    
    def get_permissions(self):
        """
        Allow booking owner and apartment owner/admin to view.
        """
        if self.request.method == 'GET':
            return [permissions.IsAuthenticated()]
        return super().get_permissions()
    
    def check_object_permissions(self, request, obj):
        """
        Check if user has permission to view this booking.
        """
        # Booking owner can view
        if obj.user == request.user:
            return True
        
        # Apartment owner can view
        if obj.apartment.owner == request.user:
            return True
        
        # Admin can view
        if request.user.role == 'admin':
            return True
        
        self.permission_denied(request, message=_("You don't have permission to view this booking."))


class SubmitPaymentView(generics.UpdateAPIView):
    """
    Submit payment reference for a booking.
    """
    serializer_class = BookingSubmitPaymentSerializer
    permission_classes = [permissions.IsAuthenticated, IsBookingOwner]
    queryset = Booking.objects.all()
    
    @swagger_auto_schema(
        operation_description="Submit payment reference for booking",
        request_body=BookingSubmitPaymentSerializer,
        responses={
            200: "Payment submitted successfully",
            400: "Bad Request",
            403: "Forbidden",
            404: "Not Found"
        }
    )
    def patch(self, request, *args, **kwargs):
        """
        Partial update to submit payment.
        """
        return self.partial_update(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """
        Update booking with payment details.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            'message': _('Payment reference submitted successfully.'),
            'booking': BookingSerializer(instance, context=self.get_serializer_context()).data
        })


class VerifyPaymentView(generics.UpdateAPIView):
    """
    Verify payment and confirm booking (admin or apartment owner only).
    """
    serializer_class = BookingVerifyPaymentSerializer
    permission_classes = [permissions.IsAuthenticated, CanVerifyPayment]
    queryset = Booking.objects.all()
    
    @swagger_auto_schema(
        operation_description="Verify payment and confirm booking",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={}
        ),
        responses={
            200: "Payment verified successfully",
            400: "Bad Request",
            403: "Forbidden",
            404: "Not Found"
        }
    )
    def patch(self, request, *args, **kwargs):
        """
        Partial update to verify payment.
        """
        return self.partial_update(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """
        Update booking to verified and confirmed.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            'message': _('Payment verified and booking confirmed successfully.'),
            'booking': BookingSerializer(instance, context=self.get_serializer_context()).data
        })


class CancelBookingView(generics.UpdateAPIView):
    """
    Cancel a booking.
    """
    serializer_class = BookingCancelSerializer
    permission_classes = [permissions.IsAuthenticated, IsBookingOwner]
    queryset = Booking.objects.all()
    
    @swagger_auto_schema(
        operation_description="Cancel a booking",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={}
        ),
        responses={
            200: "Booking cancelled successfully",
            400: "Bad Request",
            403: "Forbidden",
            404: "Not Found"
        }
    )
    def patch(self, request, *args, **kwargs):
        """
        Partial update to cancel booking.
        """
        return self.partial_update(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """
        Update booking to cancelled.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            'message': _('Booking cancelled successfully.'),
            'booking': BookingSerializer(instance, context=self.get_serializer_context()).data
        })


class ApartmentAvailabilityView(APIView):
    """
    Check apartment availability for specific dates.
    """
    permission_classes = [permissions.AllowAny]
    
    @swagger_auto_schema(
        operation_description="Check if apartment is available for given dates",
        manual_parameters=[
            openapi.Parameter('apartment_id', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=True),
            openapi.Parameter('start_date', openapi.IN_QUERY, type=openapi.TYPE_STRING, format='date', required=True),
            openapi.Parameter('end_date', openapi.IN_QUERY, type=openapi.TYPE_STRING, format='date', required=True),
        ],
        responses={
            200: "Availability status",
            400: "Bad Request"
        }
    )
    def get(self, request):
        """
        Check if apartment is available for given dates.
        """
        apartment_id = request.query_params.get('apartment_id')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if not all([apartment_id, start_date, end_date]):
            return Response(
                {'error': _('apartment_id, start_date, and end_date are required.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from datetime import datetime
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': _('Invalid date format. Use YYYY-MM-DD.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if end_date <= start_date:
            return Response(
                {'error': _('End date must be after start date.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check for overlapping confirmed bookings
        overlapping = Booking.objects.filter(
            apartment_id=apartment_id,
            status=Booking.Status.CONFIRMED,
            start_date__lt=end_date,
            end_date__gt=start_date
        ).exists()
        
        return Response({
            'available': not overlapping,
            'apartment_id': apartment_id,
            'start_date': start_date,
            'end_date': end_date,
            'message': _('Apartment is available for these dates.') if not overlapping else _('Apartment is already booked for these dates.')
        })

class AdminBookingListView(generics.ListAPIView):
    """
    List all bookings for admin.
    """
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'payment_status']
    search_fields = ['user__email', 'apartment__title']
    ordering_fields = ['created_at', 'start_date', 'total_price']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Booking.objects.all().select_related('user', 'apartment')

class OwnerBookingListView(generics.ListAPIView):
    """
    List bookings for apartments owned by the logged-in user.
    """
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'payment_status']
    search_fields = ['user__email', 'apartment__title']
    ordering_fields = ['created_at', 'start_date', 'total_price']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Booking.objects.filter(
            apartment__owner=self.request.user
        ).select_related('user', 'apartment', 'apartment__owner')