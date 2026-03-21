# stayease/reviews/serializers.py
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    """
    Serializer for reviews.
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_full_name = serializers.CharField(source='user.full_name', read_only=True)
    apartment_title = serializers.CharField(source='apartment.title', read_only=True)
    
    class Meta:
        model = Review
        fields = [
            'id', 'user', 'user_email', 'user_full_name',
            'apartment', 'apartment_title',
            'rating', 'comment', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
    
    def validate_rating(self, value):
        """
        Validate rating is between 1 and 5.
        """
        if not (1 <= value <= 5):
            raise serializers.ValidationError(
                _("Rating must be between 1 and 5.")
            )
        return value
    
    def validate(self, data):
        """
        Validate that user hasn't already reviewed this apartment.
        """
        request = self.context.get('request')
        if request and request.method == 'POST':
            user = request.user
            apartment = data.get('apartment')
            
            # Check for existing review
            if Review.objects.filter(user=user, apartment=apartment).exists():
                raise serializers.ValidationError(
                    _("You have already reviewed this apartment.")
                )
            
            # Check if user has completed a booking for this apartment
            from bookings.models import Booking
            from django.utils import timezone
            
            has_completed_booking = Booking.objects.filter(
                user=user,
                apartment=apartment,
                status=Booking.Status.CONFIRMED,
                end_date__lte=timezone.now().date()
            ).exists()
            
            if not has_completed_booking:
                raise serializers.ValidationError(
                    _("You can only review apartments you have completed a booking for.")
                )
        
        return data
    
    def create(self, validated_data):
        """
        Create review with user from request context.
        """
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ApartmentReviewSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for listing reviews on an apartment.
    """
    user_full_name = serializers.CharField(source='user.full_name', read_only=True)
    
    class Meta:
        model = Review
        fields = [
            'id', 'user_full_name', 'rating', 'comment', 'created_at'
        ]