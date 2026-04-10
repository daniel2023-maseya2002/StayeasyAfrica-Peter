# stayease/bookings/serializers.py
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import Booking
from apartments.models import Apartment
import random
import string


class BookingSerializer(serializers.ModelSerializer):
    """
    Serializer for bookings with enhanced details including location and payment number.
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_full_name = serializers.CharField(source='user.full_name', read_only=True)
    user_phone = serializers.CharField(source='user.phone_number', read_only=True)
    
    apartment_title = serializers.CharField(source='apartment.title', read_only=True)
    apartment_owner = serializers.CharField(source='apartment.owner.email', read_only=True)
    apartment_owner_phone = serializers.CharField(source='apartment.owner.phone_number', read_only=True)
    apartment_district = serializers.CharField(source='apartment.district', read_only=True)
    apartment_sector = serializers.CharField(source='apartment.sector', read_only=True)
    apartment_address = serializers.CharField(source='apartment.address', read_only=True)
    
    nights = serializers.SerializerMethodField(read_only=True)
    
    # Get payment status from the related Payment model
    payment_status = serializers.CharField(source='payment.status', read_only=True, default='pending')
    payment_id = serializers.IntegerField(source='payment.id', read_only=True)
    payment_amount = serializers.DecimalField(source='payment.amount', read_only=True, max_digits=10, decimal_places=2)
    payment_method_display = serializers.CharField(source='payment.get_payment_method_display', read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'booking_code',
            'user', 'user_email', 'user_full_name', 'user_phone',
            'apartment', 'apartment_title', 'apartment_owner', 'apartment_owner_phone',
            'apartment_district', 'apartment_sector', 'apartment_address',
            'start_date', 'end_date', 'nights', 'total_price',
            'status', 'payment_method', 'payment_reference',
            'payment_status', 'payment_id', 'payment_amount', 'payment_method_display',
            'phone_number', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'booking_code', 'user', 'total_price', 'status', 'payment_status',
            'payment_reference', 'created_at', 'updated_at', 'nights',
            'payment_id', 'payment_amount', 'payment_method_display',
            'apartment_owner_phone', 'apartment_district', 'apartment_sector', 'apartment_address'
        ]
    
    def get_nights(self, obj):
        """Calculate number of nights."""
        return obj.get_nights()
    
    def check_double_booking(self, apartment, start_date, end_date, exclude_booking=None):
        """
        Check if the apartment is already booked for the given dates.
        Returns True if double booking exists, False otherwise.
        Only confirmed bookings with verified payments block dates.
        """
        queryset = Booking.objects.filter(
            apartment=apartment,
            status=Booking.Status.CONFIRMED,
            payment_status=Booking.PaymentStatus.VERIFIED,
            start_date__lt=end_date,
            end_date__gt=start_date
        )
        
        # Exclude current booking when updating
        if exclude_booking:
            queryset = queryset.exclude(id=exclude_booking.id)
        
        return queryset.exists()
    
    def validate(self, data):
        """
        Validate booking dates and availability with double booking prevention.
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
        
        # Check for overlapping confirmed bookings (double booking prevention)
        if apartment and start_date and end_date:
            if self.check_double_booking(apartment, start_date, end_date):
                raise serializers.ValidationError(
                    _("Selected dates are already booked. Please choose different dates.")
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
    
    def update(self, instance, validated_data):
        """
        Update booking with double booking validation.
        """
        # Check for double booking when updating dates
        start_date = validated_data.get('start_date', instance.start_date)
        end_date = validated_data.get('end_date', instance.end_date)
        apartment = validated_data.get('apartment', instance.apartment)
        
        if self.check_double_booking(apartment, start_date, end_date, exclude_booking=instance):
            raise serializers.ValidationError(
                _("Selected dates are already booked. Please choose different dates.")
            )
        
        return super().update(instance, validated_data)


class BookingLookupSerializer(serializers.Serializer):
    """
    Serializer for booking lookup by email and booking code.
    """
    email = serializers.EmailField(required=True)
    booking_code = serializers.CharField(max_length=50, required=True)
    
    def validate(self, attrs):
        """
        Validate that a booking exists with the given email and booking code.
        """
        email = attrs.get('email')
        booking_code = attrs.get('booking_code')
        
        try:
            booking = Booking.objects.select_related('user', 'apartment', 'apartment__owner').get(
                user__email=email,
                booking_code=booking_code
            )
            attrs['booking'] = booking
        except Booking.DoesNotExist:
            raise serializers.ValidationError(
                _("No booking found with the provided email and booking code.")
            )
        
        return attrs


class BookingLookupResponseSerializer(serializers.Serializer):
    """
    Serializer for booking lookup response with enhanced details.
    """
    id = serializers.IntegerField()
    booking_code = serializers.CharField()
    apartment_title = serializers.CharField()
    apartment_district = serializers.CharField()
    apartment_sector = serializers.CharField()
    apartment_address = serializers.CharField()
    owner_phone_number = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    booking_status = serializers.CharField()
    payment_status = serializers.CharField()
    nights = serializers.IntegerField()
    user_name = serializers.CharField()
    user_email = serializers.EmailField()
    phone_number = serializers.CharField()


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
        
        if instance.apartment:
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
        
        if instance.status == Booking.Status.CANCELLED and instance.apartment:
            other_confirmed = Booking.objects.filter(
                apartment=instance.apartment,
                status=Booking.Status.CONFIRMED,
                end_date__gte=timezone.now().date()
            ).exclude(id=instance.id).exists()
            
            if not other_confirmed:
                instance.apartment.availability_status = 'available'
                instance.apartment.save()
        
        return instance


# Booking code generator functions
def generate_booking_code():
    """
    Generate a unique booking code in format: STE-XXX-XX-XX
    Example: STE-234-AB-93
    """
    digits_1 = ''.join(random.choices(string.digits, k=3))
    letters = ''.join(random.choices(string.ascii_uppercase, k=2))
    digits_2 = ''.join(random.choices(string.digits, k=2))
    
    code = f"STE-{digits_1}-{letters}-{digits_2}"
    
    return code


def generate_unique_booking_code(BookingModel):
    """
    Generate a unique booking code that doesn't exist in the database.
    """
    from django.utils import timezone
    max_attempts = 10
    
    for _ in range(max_attempts):
        code = generate_booking_code()
        if not BookingModel.objects.filter(booking_code=code).exists():
            return code
    
    # If we hit max attempts, add timestamp to ensure uniqueness
    timestamp = timezone.now().strftime('%H%M%S')
    return f"STE-{timestamp[-3:]}-{generate_booking_code()[-5:]}"