# stayease/payments/serializers.py
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from .models import Payment
from bookings.models import Booking


class PaymentSerializer(serializers.ModelSerializer):
    """
    Serializer for payments.
    """
    booking_id = serializers.IntegerField(write_only=True, required=False)
    booking_reference = serializers.CharField(source='booking.id', read_only=True)
    user_email = serializers.EmailField(source='booking.user.email', read_only=True)
    user_full_name = serializers.CharField(source='booking.user.full_name', read_only=True)
    apartment_title = serializers.CharField(source='booking.apartment.title', read_only=True)
    apartment_owner = serializers.CharField(source='booking.apartment.owner.email', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'booking', 'booking_id', 'booking_reference',
            'user_email', 'user_full_name', 'apartment_title', 'apartment_owner',
            'amount', 'payment_method', 'transaction_id', 'status',
            'created_at', 'verified_at'
        ]
        read_only_fields = [
            'id', 'booking', 'amount', 'status', 'created_at', 'verified_at',
            'booking_reference', 'user_email', 'user_full_name', 'apartment_title', 'apartment_owner'
        ]
    
    def validate_booking_id(self, value):
        """
        Validate that booking exists and belongs to the current user.
        """
        try:
            booking = Booking.objects.get(id=value)
        except Booking.DoesNotExist:
            raise serializers.ValidationError(
                _("Booking with this ID does not exist.")
            )
        
        # Check if booking belongs to current user
        user = self.context['request'].user
        if booking.user != user:
            raise serializers.ValidationError(
                _("You can only submit payment for your own bookings.")
            )
        
        # Check if payment already exists for this booking
        if hasattr(booking, 'payment'):
            raise serializers.ValidationError(
                _("Payment has already been submitted for this booking.")
            )
        
        # Check if booking is in pending state
        if booking.status != Booking.Status.PENDING:
            raise serializers.ValidationError(
                _("Cannot submit payment for a booking that is not pending.")
            )
        
        return value
    
    def validate_transaction_id(self, value):
        """
        Validate transaction ID is provided and not empty.
        """
        if not value or not value.strip():
            raise serializers.ValidationError(
                _("Transaction ID is required.")
            )
        return value.strip()
    
    def create(self, validated_data):
        """
        Create payment with amount from booking.
        """
        booking_id = validated_data.pop('booking_id')
        booking = Booking.objects.get(id=booking_id)
        
        payment = Payment.objects.create(
            booking=booking,
            amount=booking.total_price,
            payment_method=validated_data.get('payment_method'),
            transaction_id=validated_data.get('transaction_id'),
            status=Payment.Status.SUBMITTED
        )
        
        return payment


class PaymentVerifySerializer(serializers.ModelSerializer):
    """
    Serializer for verifying payment.
    """
    class Meta:
        model = Payment
        fields = []
    
    def validate(self, data):
        """
        Validate payment can be verified.
        """
        payment = self.instance
        
        if payment.status != Payment.Status.SUBMITTED:
            raise serializers.ValidationError(
                _("Only submitted payments can be verified.")
            )
        
        if payment.booking.status != Booking.Status.PENDING:
            raise serializers.ValidationError(
                _("Cannot verify payment for a booking that is not pending.")
            )
        
        return data
    
    def update(self, instance, validated_data):
        """
        Verify payment and update booking status.
        """
        # Update payment
        instance.verify()
        
        # Update booking status
        instance.booking.verify_payment()
        
        return instance


class PaymentRejectSerializer(serializers.ModelSerializer):
    """
    Serializer for rejecting payment.
    """
    rejection_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=_("Reason for rejecting the payment")
    )
    
    class Meta:
        model = Payment
        fields = ['rejection_reason']
    
    def validate(self, data):
        """
        Validate payment can be rejected.
        """
        payment = self.instance
        
        if payment.status == Payment.Status.VERIFIED:
            raise serializers.ValidationError(
                _("Cannot reject a verified payment.")
            )
        
        if payment.status == Payment.Status.REJECTED:
            raise serializers.ValidationError(
                _("Payment is already rejected.")
            )
        
        return data
    
    def update(self, instance, validated_data):
        """
        Reject payment.
        """
        instance.reject()
        
        # Optionally store rejection reason if field exists
        # Could extend Payment model with rejection_reason field
        rejection_reason = validated_data.get('rejection_reason')
        if rejection_reason:
            # Store in a log or add field to model
            pass
        
        return instance