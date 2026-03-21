# stayease/payments/views.py
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.contrib.auth import get_user_model
import logging

from .models import Payment
from .serializers import (
    PaymentSerializer, PaymentVerifySerializer, PaymentRejectSerializer
)
from .permissions import IsBookingOwner, CanVerifyPayment
from utils.email_utils import EmailNotificationService
logger = logging.getLogger(__name__)
User = get_user_model()


class PaymentSubmitView(generics.CreateAPIView):
    """
    Submit a new payment for a booking.
    """
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Submit payment for a booking",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['booking_id', 'payment_method', 'transaction_id'],
            properties={
                'booking_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the booking'),
                'payment_method': openapi.Schema(type=openapi.TYPE_STRING, enum=['mtn', 'airtel'], description='Payment method'),
                'transaction_id': openapi.Schema(type=openapi.TYPE_STRING, description='Transaction reference from mobile money'),
            }
        ),
        responses={
            201: "Payment submitted successfully",
            400: "Bad Request",
            403: "Forbidden",
            404: "Not Found"
        }
    )
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """
        Create payment with validation and send notifications.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create payment
        payment = serializer.save()
        
        # Get all admin emails
        admin_emails = User.objects.filter(
            role='admin',
            is_active=True
        ).values_list('email', flat=True)
        
        # Send email notifications (non-blocking)
        try:
            EmailNotificationService.send_payment_submitted_email(
                payment=payment,
                admin_emails=list(admin_emails)
            )
            logger.info(f"Payment submission email sent for payment #{payment.id}")
        except Exception as e:
            # Log error but don't rollback transaction
            logger.error(f"Failed to send payment submission email for payment #{payment.id}: {str(e)}")
        
        return Response({
            'message': _('Payment submitted successfully.'),
            'payment': PaymentSerializer(payment, context=self.get_serializer_context()).data
        }, status=status.HTTP_201_CREATED)


class MyPaymentsView(generics.ListAPIView):
    """
    List all payments for the logged-in user.
    """
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'payment_method']
    search_fields = ['transaction_id', 'booking__apartment__title']
    ordering_fields = ['created_at', 'amount', 'verified_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Return payments for bookings owned by the current user.
        """
        return Payment.objects.filter(
            booking__user=self.request.user
        ).select_related('booking', 'booking__user', 'booking__apartment', 'booking__apartment__owner')


class OwnerPaymentsView(generics.ListAPIView):
    """
    List all payments for apartments owned by the logged-in user.
    """
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'payment_method', 'booking__apartment']
    search_fields = ['transaction_id', 'booking__user__email', 'booking__user__full_name']
    ordering_fields = ['created_at', 'amount', 'verified_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Return payments for apartments owned by the current user.
        """
        user = self.request.user
        
        # Admin can see all payments
        if user.role == 'admin':
            return Payment.objects.all().select_related(
                'booking', 'booking__user', 'booking__apartment', 'booking__apartment__owner'
            )
        
        # Owners see payments for their apartments
        return Payment.objects.filter(
            booking__apartment__owner=user
        ).select_related('booking', 'booking__user', 'booking__apartment', 'booking__apartment__owner')


class PaymentDetailView(generics.RetrieveAPIView):
    """
    Retrieve payment details.
    """
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Payment.objects.all().select_related(
        'booking', 'booking__user', 'booking__apartment', 'booking__apartment__owner'
    )
    
    def check_object_permissions(self, request, obj):
        """
        Check if user has permission to view this payment.
        """
        # Booking owner can view
        if obj.booking.user == request.user:
            return True
        
        # Apartment owner can view
        if obj.booking.apartment.owner == request.user:
            return True
        
        # Admin can view
        if request.user.role == 'admin':
            return True
        
        self.permission_denied(request, message=_("You don't have permission to view this payment."))


class PaymentVerifyView(generics.UpdateAPIView):
    """
    Verify payment (admin or apartment owner only).
    """
    serializer_class = PaymentVerifySerializer
    permission_classes = [permissions.IsAuthenticated, CanVerifyPayment]
    queryset = Payment.objects.all()
    
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
    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        """
        Partial update to verify payment.
        """
        return self.partial_update(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """
        Update payment to verified and confirm booking.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            self.perform_update(serializer)
            
            # Send email notifications (non-blocking)
            try:
                EmailNotificationService.send_payment_verified_email(
                    payment=instance
                )
                logger.info(f"Payment verification email sent for payment #{instance.id}")
            except Exception as e:
                logger.error(f"Failed to send payment verification email for payment #{instance.id}: {str(e)}")
        
        return Response({
            'message': _('Payment verified and booking confirmed successfully.'),
            'payment': PaymentSerializer(instance, context=self.get_serializer_context()).data
        })


class PaymentRejectView(generics.UpdateAPIView):
    """
    Reject payment (admin or apartment owner only).
    """
    serializer_class = PaymentRejectSerializer
    permission_classes = [permissions.IsAuthenticated, CanVerifyPayment]
    queryset = Payment.objects.all()
    
    @swagger_auto_schema(
        operation_description="Reject payment",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'rejection_reason': openapi.Schema(
                    type=openapi.TYPE_STRING, 
                    description='Reason for rejection (optional)'
                ),
            }
        ),
        responses={
            200: "Payment rejected successfully",
            400: "Bad Request",
            403: "Forbidden",
            404: "Not Found"
        }
    )
    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        """
        Partial update to reject payment.
        """
        return self.partial_update(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """
        Update payment to rejected.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            self.perform_update(serializer)
            
            # Get rejection reason if provided
            rejection_reason = serializer.validated_data.get('rejection_reason')
            
            # Send email notifications (non-blocking)
            try:
                EmailNotificationService.send_payment_rejected_email(
                    payment=instance,
                    rejection_reason=rejection_reason
                )
                logger.info(f"Payment rejection email sent for payment #{instance.id}")
            except Exception as e:
                logger.error(f"Failed to send payment rejection email for payment #{instance.id}: {str(e)}")
        
        return Response({
            'message': _('Payment rejected successfully.'),
            'payment': PaymentSerializer(instance, context=self.get_serializer_context()).data
        })


class PaymentStatisticsView(APIView):
    """
    Get payment statistics (admin only).
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_permissions(self):
        """
        Only admin can access statistics.
        """
        if self.request.user.role != 'admin':
            self.permission_denied(
                self.request,
                message=_("Only admin can access payment statistics.")
            )
        return super().get_permissions()
    
    @swagger_auto_schema(
        operation_description="Get payment statistics (admin only)",
        responses={
            200: "Payment statistics",
            403: "Forbidden"
        }
    )
    def get(self, request):
        """
        Return payment statistics.
        """
        from django.db.models import Sum
        from django.utils import timezone
        from datetime import timedelta
        
        # Date range (last 30 days by default)
        days = request.query_params.get('days', 30)
        try:
            days = int(days)
        except ValueError:
            days = 30
        
        start_date = timezone.now() - timedelta(days=days)
        
        # Base queryset
        payments = Payment.objects.filter(created_at__gte=start_date)
        
        # Statistics
        stats = {
            'period_days': days,
            'total_payments': payments.count(),
            'total_amount': payments.aggregate(total=Sum('amount'))['total'] or 0,
            'by_status': {
                'pending': payments.filter(status=Payment.Status.PENDING).count(),
                'submitted': payments.filter(status=Payment.Status.SUBMITTED).count(),
                'verified': payments.filter(status=Payment.Status.VERIFIED).count(),
                'rejected': payments.filter(status=Payment.Status.REJECTED).count(),
            },
            'by_method': {
                'mtn': payments.filter(payment_method=Payment.PaymentMethod.MTN).count(),
                'airtel': payments.filter(payment_method=Payment.PaymentMethod.AIRTEL).count(),
            },
            'verified_amount': payments.filter(
                status=Payment.Status.VERIFIED
            ).aggregate(total=Sum('amount'))['total'] or 0,
        }
        
        return Response(stats)