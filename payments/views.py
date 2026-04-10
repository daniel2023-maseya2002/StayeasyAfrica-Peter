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
from django.utils import timezone

from .models import Payment
from .serializers import (
    PaymentSerializer, PaymentVerifySerializer, PaymentRejectSerializer
)
from .permissions import IsBookingOwner, CanVerifyPayment, IsAdmin
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


# stayease/payments/views.py - Update the PaymentVerifyView class

class PaymentVerifyView(APIView):
    """
    Verify payment (apartment owner only).
    Updates payment status to 'verified' and booking status to 'confirmed'.
    Also updates booking.payment_status to 'verified'.
    """
    permission_classes = [permissions.IsAuthenticated, CanVerifyPayment]
    
    @swagger_auto_schema(
        operation_description="Verify payment and confirm booking",
        responses={
            200: "Payment verified and booking confirmed",
            400: "Bad Request",
            403: "Forbidden",
            404: "Not Found"
        }
    )
    @transaction.atomic
    def patch(self, request, pk):
        """
        Verify payment and update booking status.
        """
        try:
            payment = Payment.objects.select_related('booking', 'booking__apartment').get(pk=pk)
        except Payment.DoesNotExist:
            return Response(
                {'error': _('Payment not found.')},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permission (owner of the apartment)
        self.check_object_permissions(request, payment)
        
        # Check if payment can be verified
        if payment.status != Payment.Status.SUBMITTED:
            return Response(
                {'error': _('Only submitted payments can be verified.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if payment.booking.status != 'pending':
            return Response(
                {'error': _('Only pending bookings can be confirmed.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update payment status
        payment.status = Payment.Status.VERIFIED
        payment.verified_at = timezone.now()
        payment.save()
        
        # Update booking status AND payment_status
        booking = payment.booking
        booking.status = 'confirmed'
        booking.payment_status = 'verified'  # IMPORTANT: Update the booking's payment_status
        booking.save()
        
        # Send email notification to user
        try:
            EmailNotificationService.send_payment_verified_email(payment=payment)
            logger.info(f"Payment verification email sent for payment #{payment.id}")
        except Exception as e:
            logger.error(f"Failed to send payment verification email for payment #{payment.id}: {str(e)}")
        
        return Response({
            'message': _('Payment verified and booking confirmed successfully.'),
            'payment': {
                'id': payment.id,
                'status': payment.status,
                'verified_at': payment.verified_at
            },
            'booking': {
                'id': booking.id,
                'status': booking.status,
                'payment_status': booking.payment_status
            }
        }, status=status.HTTP_200_OK)


class PaymentRejectView(APIView):
    """
    Reject payment (apartment owner only).
    Updates payment status to 'rejected'. Booking remains pending.
    """
    permission_classes = [permissions.IsAuthenticated, CanVerifyPayment]
    
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
            200: "Payment rejected",
            400: "Bad Request",
            403: "Forbidden",
            404: "Not Found"
        }
    )
    @transaction.atomic
    def patch(self, request, pk):
        """
        Reject payment and send notification.
        """
        try:
            payment = Payment.objects.select_related('booking', 'booking__apartment').get(pk=pk)
        except Payment.DoesNotExist:
            return Response(
                {'error': _('Payment not found.')},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permission (owner of the apartment)
        self.check_object_permissions(request, payment)
        
        # Check if payment can be rejected
        if payment.status == Payment.Status.VERIFIED:
            return Response(
                {'error': _('Verified payments cannot be rejected.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if payment.status == Payment.Status.REJECTED:
            return Response(
                {'error': _('Payment is already rejected.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get rejection reason if provided
        rejection_reason = request.data.get('rejection_reason', None)
        
        # Update payment status
        payment.status = Payment.Status.REJECTED
        payment.verified_at = timezone.now()
        payment.save()
        
        # Update booking payment_status to 'rejected' (optional - depends on your business logic)
        booking = payment.booking
        booking.payment_status = 'rejected'
        booking.save()
        
        # Send email notification to user
        try:
            EmailNotificationService.send_payment_rejected_email(
                payment=payment,
                rejection_reason=rejection_reason
            )
            logger.info(f"Payment rejection email sent for payment #{payment.id}")
        except Exception as e:
            logger.error(f"Failed to send payment rejection email for payment #{payment.id}: {str(e)}")
        
        return Response({
            'message': _('Payment rejected successfully.'),
            'payment': {
                'id': payment.id,
                'status': payment.status,
                'verified_at': payment.verified_at
            },
            'booking': {
                'id': booking.id,
                'payment_status': booking.payment_status
            }
        }, status=status.HTTP_200_OK)


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


class AdminPaymentListView(generics.ListAPIView):
    """
    List all payments for admin.
    """
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'payment_method']
    search_fields = ['transaction_id', 'booking__user__email', 'booking__apartment__title']
    ordering_fields = ['created_at', 'amount', 'verified_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Payment.objects.all().select_related(
            'booking', 'booking__user', 'booking__apartment'
        )


class OwnerPaymentListView(generics.ListAPIView):
    """
    List payments for apartments owned by the logged-in user.
    """
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'payment_method']
    search_fields = ['transaction_id', 'booking__user__email']
    ordering_fields = ['created_at', 'amount', 'verified_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Payment.objects.filter(
            booking__apartment__owner=self.request.user
        ).select_related('booking', 'booking__user', 'booking__apartment')