# stayease/bookings/serializers.py
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import Booking
from apartments.models import Apartment


class BookingSerializer(serializers.ModelSerializer):
    """
    Serializer for bookings.
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_full_name = serializers.CharField(source='user.full_name', read_only=True)
    apartment_title = serializers.CharField(source='apartment.title', read_only=True)
    apartment_owner = serializers.CharField(source='apartment.owner.email', read_only=True)
    nights = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'user', 'user_email', 'user_full_name',
            'apartment', 'apartment_title', 'apartment_owner',
            'start_date', 'end_date', 'nights', 'total_price',
            'status', 'payment_method', 'payment_reference',
            'payment_status', 'phone_number', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'total_price', 'status', 'payment_status',
            'payment_reference', 'created_at', 'updated_at', 'nights'
        ]
    
    def get_nights(self, obj):
        """Calculate number of nights."""
        return obj.get_nights()
    
    def validate(self, data):
        """
        Validate booking dates and availability.
        """
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        apartment = data.get('apartment')
        
        # Validate dates
        if start_date and end_date:
            if end_date <= start_date:
                raise serializers.ValidationError({
                    'end_date': _("End date must be after start date.")
                })
            
            if start_date < timezone.now().date():
                raise serializers.ValidationError({
                    'start_date': _("Start date cannot be in the past.")
                })
        
        # Check for overlapping bookings if apartment is provided
        if apartment and start_date and end_date:
            overlapping = Booking.objects.filter(
                apartment=apartment,
                status=Booking.Status.CONFIRMED,
                start_date__lt=end_date,
                end_date__gt=start_date
            ).exists()
            
            if overlapping:
                raise serializers.ValidationError(
                    _("This apartment is already booked for the selected dates.")
                )
        
        # Calculate total price
        if apartment and start_date and end_date:
            nights = (end_date - start_date).days
            data['total_price'] = apartment.price_daily * nights
        
        return data
    
    def create(self, validated_data):
        """
        Create booking with user from request context.
        """
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class BookingSubmitPaymentSerializer(serializers.ModelSerializer):
    """
    Serializer for submitting payment reference.
    """
    class Meta:
        model = Booking
        fields = ['payment_method', 'payment_reference']
    
    def validate(self, data):
        """
        Validate payment submission.
        """
        booking = self.instance
        
        # Check if booking is in correct state
        if booking.payment_status != Booking.PaymentStatus.PENDING:
            raise serializers.ValidationError(
                _("Payment has already been submitted or verified.")
            )
        
        if booking.status != Booking.Status.PENDING:
            raise serializers.ValidationError(
                _("Cannot submit payment for a cancelled booking.")
            )
        
        return data
    
    def update(self, instance, validated_data):
        """
        Update booking with payment details.
        """
        instance.payment_method = validated_data.get('payment_method', instance.payment_method)
        instance.payment_reference = validated_data.get('payment_reference', instance.payment_reference)
        instance.payment_status = Booking.PaymentStatus.SUBMITTED
        instance.save()
        return instance


class BookingVerifyPaymentSerializer(serializers.ModelSerializer):
    """
    Serializer for verifying payment.
    """
    class Meta:
        model = Booking
        fields = []
    
    def validate(self, data):
        """
        Validate payment verification.
        """
        booking = self.instance
        
        # Check if payment has been submitted
        if booking.payment_status != Booking.PaymentStatus.SUBMITTED:
            raise serializers.ValidationError(
                _("Payment has not been submitted yet.")
            )
        
        if booking.status != Booking.Status.PENDING:
            raise serializers.ValidationError(
                _("Cannot verify payment for a cancelled booking.")
            )
        
        return data
    
    def update(self, instance, validated_data):
        """
        Verify payment and confirm booking.
        """
        instance.payment_status = Booking.PaymentStatus.VERIFIED
        instance.status = Booking.Status.CONFIRMED
        instance.save()
        
        # Update apartment availability status
        instance.apartment.availability_status = 'booked'
        instance.apartment.save()
        
        return instance


class BookingCancelSerializer(serializers.ModelSerializer):
    """
    Serializer for cancelling booking.
    """
    class Meta:
        model = Booking
        fields = []
    
    def validate(self, data):
        """
        Validate booking cancellation.
        """
        booking = self.instance
        
        if not booking.can_cancel():
            raise serializers.ValidationError(
                _("This booking cannot be cancelled.")
            )
        
        return data
    
    def update(self, instance, validated_data):
        """
        Cancel booking.
        """
        instance.cancel()
        
        # If this was the only confirmed booking, update apartment availability
        if instance.status == Booking.Status.CANCELLED:
            other_confirmed = Booking.objects.filter(
                apartment=instance.apartment,
                status=Booking.Status.CONFIRMED,
                end_date__gte=timezone.now().date()
            ).exclude(id=instance.id).exists()
            
            if not other_confirmed:
                instance.apartment.availability_status = 'available'
                instance.apartment.save()
        
        return instance