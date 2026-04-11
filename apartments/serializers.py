# stayease/apartments/serializers.py
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import Apartment, ApartmentMedia
from bookings.models import Booking


class ApartmentMediaSerializer(serializers.ModelSerializer):
    """
    Serializer for apartment media files.
    """
    file_url = serializers.SerializerMethodField(read_only=True)
    apartment_title = serializers.CharField(source='apartment.title', read_only=True)
    
    class Meta:
        model = ApartmentMedia
        fields = [
            'id', 'apartment', 'apartment_title', 'file', 'media_type', 
            'file_url', 'uploaded_at'
        ]
        read_only_fields = ['id', 'apartment', 'uploaded_at']
    
    def get_file_url(self, obj):
        """Get absolute URL for the file."""
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url if obj.file else None
    
    def validate_file(self, value):
        """
        Validate file size and type.
        """
        # Max file size: 50MB for videos, 10MB for images
        max_size_image = 10 * 1024 * 1024  # 10MB
        max_size_video = 50 * 1024 * 1024  # 50MB
        
        # Check file extension
        file_extension = value.name.lower().split('.')[-1]
        image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
        video_extensions = ['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm']
        
        if file_extension in image_extensions:
            if value.size > max_size_image:
                raise serializers.ValidationError(
                    _("Image file size must not exceed 10MB.")
                )
        elif file_extension in video_extensions:
            if value.size > max_size_video:
                raise serializers.ValidationError(
                    _("Video file size must not exceed 50MB.")
                )
        else:
            raise serializers.ValidationError(
                _("Unsupported file format. Please upload an image (jpg, png, gif) or video (mp4, mov).")
            )
        
        return value


class ApartmentSerializer(serializers.ModelSerializer):
    """
    Serializer for apartments with nested media and payment information.
    """
    media = ApartmentMediaSerializer(many=True, read_only=True)
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    owner_full_name = serializers.CharField(source='owner.full_name', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    is_booked = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Apartment
        fields = [
            'id', 'title', 'description', 'price_daily', 'price_weekly', 
            'price_monthly', 'payment_method', 'payment_method_display', 'payment_number',
            'district', 'sector', 'address', 'nearby_landmarks',
            'is_furnished', 'has_wifi', 'has_parking', 'is_verified', 
            'availability_status', 'is_booked', 'views_count',
            'owner', 'owner_email', 'owner_full_name',
            'media', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'owner', 'is_verified', 'is_booked', 'views_count', 'created_at', 'updated_at']
    
    def get_is_booked(self, obj):
        """
        Check if apartment is currently booked.
        Returns True if there is a confirmed booking for current date range.
        """
        today = timezone.now().date()
        
        # Check for any confirmed booking that includes today's date
        is_booked = Booking.objects.filter(
            apartment=obj,
            status=Booking.Status.CONFIRMED,
            payment_status=Booking.PaymentStatus.VERIFIED,
            start_date__lte=today,
            end_date__gte=today
        ).exists()
        
        return is_booked
    
    def validate_price_daily(self, value):
        """Validate daily price is positive."""
        if value <= 0:
            raise serializers.ValidationError(
                _("Daily price must be greater than zero.")
            )
        return value
    
    def validate_payment_number(self, value):
        """Validate payment number format."""
        if not value or not value.strip():
            raise serializers.ValidationError(
                _("Payment number is required.")
            )
        # Basic validation: should be at least 10 digits
        cleaned = ''.join(filter(str.isdigit, value))
        if len(cleaned) < 10:
            raise serializers.ValidationError(
                _("Please enter a valid phone number (minimum 10 digits).")
            )
        return value
    
    def validate(self, data):
        """Validate pricing consistency and payment info."""
        price_daily = data.get('price_daily')
        price_weekly = data.get('price_weekly')
        price_monthly = data.get('price_monthly')
        
        if price_weekly and price_weekly < price_daily * 7:
            raise serializers.ValidationError(
                {"price_weekly": _("Weekly price should not be less than daily price × 7.")}
            )
        
        if price_monthly and price_monthly < price_daily * 30:
            raise serializers.ValidationError(
                {"price_monthly": _("Monthly price should not be less than daily price × 30.")}
            )
        
        # Validate payment information is provided
        if not data.get('payment_method'):
            raise serializers.ValidationError(
                {"payment_method": _("Payment method is required.")}
            )
        
        if not data.get('payment_number'):
            raise serializers.ValidationError(
                {"payment_number": _("Payment number is required.")}
            )
        
        return data


class ApartmentCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating apartments.
    Requires payment_method and payment_number when creating.
    """
    class Meta:
        model = Apartment
        fields = [
            'title', 'description', 'price_daily', 'price_weekly', 
            'price_monthly', 'payment_method', 'payment_number',
            'district', 'sector', 'address', 'nearby_landmarks',
            'is_furnished', 'has_wifi', 'has_parking', 'availability_status'
        ]
    
    def validate_price_daily(self, value):
        """Validate daily price is positive."""
        if value <= 0:
            raise serializers.ValidationError(
                _("Daily price must be greater than zero.")
            )
        return value
    
    def validate_payment_number(self, value):
        """Validate payment number format."""
        if not value or not value.strip():
            raise serializers.ValidationError(
                _("Payment number is required.")
            )
        # Basic validation: should be at least 10 digits
        cleaned = ''.join(filter(str.isdigit, value))
        if len(cleaned) < 10:
            raise serializers.ValidationError(
                _("Please enter a valid phone number (minimum 10 digits).")
            )
        return value
    
    def validate(self, data):
        """Validate pricing consistency and payment info."""
        price_daily = data.get('price_daily')
        price_weekly = data.get('price_weekly')
        price_monthly = data.get('price_monthly')
        
        if price_weekly and price_weekly < price_daily * 7:
            raise serializers.ValidationError(
                {"price_weekly": _("Weekly price should not be less than daily price × 7.")}
            )
        
        if price_monthly and price_monthly < price_daily * 30:
            raise serializers.ValidationError(
                {"price_monthly": _("Monthly price should not be less than daily price × 30.")}
            )
        
        # Validate payment information is provided for creation
        if self.instance is None:  # Creating new apartment
            if not data.get('payment_method'):
                raise serializers.ValidationError(
                    {"payment_method": _("Payment method is required.")}
                )
            if not data.get('payment_number'):
                raise serializers.ValidationError(
                    {"payment_number": _("Payment number is required.")}
                )
        
        return data


class ApartmentVerifySerializer(serializers.ModelSerializer):
    """
    Serializer for admin to verify apartments.
    """
    class Meta:
        model = Apartment
        fields = ['is_verified']
    
    def validate_is_verified(self, value):
        """Ensure is_verified is being set to True."""
        if not value:
            raise serializers.ValidationError(
                _("Verification can only set is_verified to True.")
            )
        return value


class MultipleFileUploadSerializer(serializers.Serializer):
    """
    Serializer for handling multiple file uploads.
    """
    files = serializers.ListField(
        child=serializers.FileField(),
        allow_empty=False,
        write_only=True
    )


class ApartmentAnalyticsSerializer(serializers.ModelSerializer):
    """
    Serializer for apartment analytics (admin only).
    """
    class Meta:
        model = Apartment
        fields = ['id', 'title', 'views_count', 'district', 'created_at']
        read_only_fields = ['id', 'title', 'views_count', 'district', 'created_at']