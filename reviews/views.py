# stayease/reviews/views.py
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from django.utils.translation import gettext_lazy as _
from django.db.models import Avg
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Review
from .serializers import ReviewSerializer, ApartmentReviewSerializer
from .permissions import IsReviewOwner, CanCreateReview
from apartments.models import Apartment


class ReviewCreateView(generics.CreateAPIView):
    """
    Create a new review for an apartment.
    Only users with completed bookings can create reviews.
    """
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated, CanCreateReview]
    
    @swagger_auto_schema(
        operation_description="Create a review for an apartment",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['apartment', 'rating'],
            properties={
                'apartment': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the apartment'),
                'rating': openapi.Schema(type=openapi.TYPE_INTEGER, description='Rating (1-5)'),
                'comment': openapi.Schema(type=openapi.TYPE_STRING, description='Review comment (optional)'),
            }
        ),
        responses={
            201: "Review created successfully",
            400: "Bad Request",
            403: "Forbidden",
            404: "Not Found"
        }
    )
    def post(self, request, *args, **kwargs):
        """
        Create a new review.
        """
        return super().post(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        """
        Create review with current user.
        """
        serializer.save(user=self.request.user)


class ApartmentReviewsView(generics.ListAPIView):
    """
    List all reviews for a specific apartment.
    """
    serializer_class = ApartmentReviewSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['rating']
    ordering_fields = ['created_at', 'rating']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Return reviews for the specified apartment.
        """
        apartment_id = self.kwargs.get('apartment_id')
        return Review.objects.filter(
            apartment_id=apartment_id
        ).select_related('user', 'apartment')
    
    def list(self, request, *args, **kwargs):
        """
        Return reviews with average rating.
        """
        response = super().list(request, *args, **kwargs)
        
        # Add average rating to response
        apartment_id = self.kwargs.get('apartment_id')
        reviews = self.get_queryset()
        average_rating = reviews.aggregate(avg=Avg('rating'))['avg']
        
        return Response({
            'apartment_id': apartment_id,
            'average_rating': round(average_rating, 1) if average_rating else None,
            'total_reviews': reviews.count(),
            'reviews': response.data
        })


class ReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a review.
    Only the review owner can update or delete.
    """
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated, IsReviewOwner]
    queryset = Review.objects.all().select_related('user', 'apartment')
    
    def get_serializer_class(self):
        """
        Return different serializers for different actions.
        """
        if self.request.method in ['PUT', 'PATCH']:
            return ReviewSerializer
        return ReviewSerializer
    
    @swagger_auto_schema(
        operation_description="Update a review",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'rating': openapi.Schema(type=openapi.TYPE_INTEGER, description='Rating (1-5)'),
                'comment': openapi.Schema(type=openapi.TYPE_STRING, description='Review comment'),
            }
        ),
        responses={
            200: "Review updated successfully",
            400: "Bad Request",
            403: "Forbidden",
            404: "Not Found"
        }
    )
    def put(self, request, *args, **kwargs):
        """
        Update a review.
        """
        return self.update(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_description="Partially update a review",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'rating': openapi.Schema(type=openapi.TYPE_INTEGER, description='Rating (1-5)'),
                'comment': openapi.Schema(type=openapi.TYPE_STRING, description='Review comment'),
            }
        ),
        responses={
            200: "Review updated successfully",
            400: "Bad Request",
            403: "Forbidden",
            404: "Not Found"
        }
    )
    def patch(self, request, *args, **kwargs):
        """
        Partially update a review.
        """
        return self.partial_update(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_description="Delete a review",
        responses={
            204: "Review deleted successfully",
            403: "Forbidden",
            404: "Not Found"
        }
    )
    def delete(self, request, *args, **kwargs):
        """
        Delete a review.
        """
        return self.destroy(request, *args, **kwargs)
    
    def perform_update(self, serializer):
        """
        Update review.
        """
        serializer.save()
    
    def perform_destroy(self, instance):
        """
        Delete review.
        """
        instance.delete()


class ApartmentRatingView(generics.RetrieveAPIView):
    """
    Get average rating and review count for an apartment.
    """
    permission_classes = [permissions.AllowAny]
    
    @swagger_auto_schema(
        operation_description="Get average rating for an apartment",
        responses={
            200: "Rating statistics",
            404: "Apartment not found"
        }
    )
    def get(self, request, apartment_id):
        """
        Return rating statistics for an apartment.
        """
        try:
            apartment = Apartment.objects.get(id=apartment_id)
        except Apartment.DoesNotExist:
            return Response(
                {'error': _('Apartment not found.')},
                status=status.HTTP_404_NOT_FOUND
            )
        
        reviews = apartment.reviews.all()
        average_rating = reviews.aggregate(avg=Avg('rating'))['avg']
        rating_distribution = {
            '5_stars': reviews.filter(rating=5).count(),
            '4_stars': reviews.filter(rating=4).count(),
            '3_stars': reviews.filter(rating=3).count(),
            '2_stars': reviews.filter(rating=2).count(),
            '1_star': reviews.filter(rating=1).count(),
        }
        
        return Response({
            'apartment_id': apartment.id,
            'apartment_title': apartment.title,
            'average_rating': round(average_rating, 1) if average_rating else None,
            'total_reviews': reviews.count(),
            'rating_distribution': rating_distribution
        })