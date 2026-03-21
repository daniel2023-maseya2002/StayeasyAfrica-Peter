# stayease/apartments/views.py
from rest_framework import generics, status, viewsets, parsers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.views import APIView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Apartment, ApartmentMedia
from .serializers import (
    ApartmentSerializer, ApartmentCreateUpdateSerializer,
    ApartmentVerifySerializer, ApartmentMediaSerializer
)
from .permissions import (
    IsOwner, IsAdminOrReadOnly, IsOwnerOrReadOnly, 
    CanCreateApartment
)
import logging

logger = logging.getLogger(__name__)
class ApartmentListView(generics.ListCreateAPIView):
    """
    List all apartments or create a new apartment.
    """
    serializer_class = ApartmentSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['district', 'sector', 'availability_status', 'is_furnished', 'has_wifi', 'has_parking']
    search_fields = ['title', 'description', 'address', 'nearby_landmarks']
    ordering_fields = ['price_daily', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.request.method == 'POST':
            permission_classes = [IsAuthenticated, CanCreateApartment]
        else:
            permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filter apartments based on query parameters.
        """
        queryset = Apartment.objects.all().select_related('owner').prefetch_related('media')
        
        # Filter by price range
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        
        if min_price:
            queryset = queryset.filter(price_daily__gte=min_price)
        if max_price:
            queryset = queryset.filter(price_daily__lte=max_price)
        
        # Filter by verification status (only show verified if not admin/owner)
        user = self.request.user
        if not user.is_authenticated or user.role != 'admin':
            queryset = queryset.filter(is_verified=True)
        
        return queryset
    
    def perform_create(self, serializer):
        """
        Set the owner to the current user when creating an apartment.
        """
        serializer.save(owner=self.request.user)


class ApartmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete an apartment.
    """
    queryset = Apartment.objects.all().select_related('owner').prefetch_related('media')
    permission_classes = [IsOwnerOrReadOnly]
    
    def get_serializer_class(self):
        """
        Return different serializers for different actions.
        """
        if self.request.method in ['PUT', 'PATCH']:
            return ApartmentCreateUpdateSerializer
        return ApartmentSerializer
    
    def perform_update(self, serializer):
        """
        Update the apartment.
        """
        serializer.save()
    
    def perform_destroy(self, instance):
        """
        Soft delete or hard delete? We'll do hard delete for now.
        """
        instance.delete()


class ApartmentVerifyView(generics.UpdateAPIView):
    """
    Verify an apartment (admin only).
    """
    queryset = Apartment.objects.all()
    serializer_class = ApartmentVerifySerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    
    def update(self, request, *args, **kwargs):
        """
        Update apartment verification status.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        self.perform_update(serializer)
        
        return Response({
            'message': _('Apartment verified successfully.'),
            'apartment': ApartmentSerializer(instance, context=self.get_serializer_context()).data
        })


class ApartmentMediaUploadView(APIView):
    """
    Upload media files for an apartment.
    Supports single file or multiple files upload.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    
    @swagger_auto_schema(
        operation_description="Upload media files for an apartment",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'file': openapi.Schema(type=openapi.TYPE_FILE, description='Single file upload'),
                'files': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_FILE), description='Multiple files upload'),
            }
        ),
        responses={
            201: "Media uploaded successfully",
            400: "Bad Request",
            403: "Forbidden",
            404: "Apartment not found"
        }
    )
    def post(self, request, apartment_id):
        """
        Handle single or multiple file uploads.
        """
        # Get apartment and check ownership
        apartment = get_object_or_404(Apartment, id=apartment_id)
        
        # Check if user is the owner or admin
        if request.user != apartment.owner and request.user.role != 'admin':
            return Response(
                {'error': _("You don't have permission to upload media for this apartment.")},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if files are present in request
        files = request.FILES.getlist('files') or request.FILES.getlist('file')
        
        if not files:
            return Response(
                {'error': _("No files provided. Please upload at least one file.")},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Limit number of files per upload
        max_files = 10
        if len(files) > max_files:
            return Response(
                {'error': _(f"You can upload a maximum of {max_files} files at once.")},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Process each file
        uploaded_media = []
        errors = []
        
        for file in files:
            # Create serializer for each file
            serializer = ApartmentMediaSerializer(
                data={'file': file},
                context={'request': request}
            )
            
            if serializer.is_valid():
                # Auto-detect media type from file extension
                file_extension = file.name.lower().split('.')[-1]
                image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
                
                media_type = ApartmentMedia.MediaType.IMAGE if file_extension in image_extensions else ApartmentMedia.MediaType.VIDEO
                
                # Save media
                media = ApartmentMedia.objects.create(
                    apartment=apartment,
                    file=file,
                    media_type=media_type
                )
                
                uploaded_media.append(ApartmentMediaSerializer(media, context={'request': request}).data)
            else:
                errors.append({
                    'file': file.name,
                    'errors': serializer.errors
                })
        
        # Prepare response
        response_data = {
            'message': _(f"Successfully uploaded {len(uploaded_media)} file(s)."),
            'uploaded': uploaded_media
        }
        
        if errors:
            response_data['errors'] = errors
            response_data['message'] = _(f"Uploaded {len(uploaded_media)} file(s) with {len(errors)} error(s).")
            status_code = status.HTTP_207_MULTI_STATUS
        else:
            status_code = status.HTTP_201_CREATED
        
        return Response(response_data, status=status_code)

class ApartmentMediaDetailView(generics.RetrieveAPIView):
    """
    Retrieve a specific media file.
    """
    serializer_class = ApartmentMediaSerializer
    permission_classes = [AllowAny]
    queryset = ApartmentMedia.objects.all()
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve media with permission check."""
        media = self.get_object()
        
        # Check if apartment is verified or user has permission
        if not media.apartment.is_verified:
            user = request.user
            if not user.is_authenticated or (user != media.apartment.owner and user.role != 'admin'):
                return Response(
                    {'error': _("You don't have permission to view this media.")},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        serializer = self.get_serializer(media)
        return Response(serializer.data)


class ApartmentMediaDeleteView(generics.DestroyAPIView):
    """
    Delete a specific media file.
    Only owner of the apartment or admin can delete.
    """
    permission_classes = [IsAuthenticated]
    queryset = ApartmentMedia.objects.all()
    
    def destroy(self, request, *args, **kwargs):
        """
        Delete media with permission check.
        """
        media = self.get_object()
        
        # Check if user is the owner of the apartment or admin
        if request.user != media.apartment.owner and request.user.role != 'admin':
            return Response(
                {'error': _("You don't have permission to delete this media.")},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Delete the file from storage
        try:
            if media.file:
                media.file.delete(save=False)
        except Exception as e:
            logger.warning(f"Failed to delete file from storage: {str(e)}")
        
        # Delete database record
        media.delete()
        
        return Response(
            {'message': _("Media deleted successfully.")},
            status=status.HTTP_200_OK
        )

class ApartmentMediaBulkDeleteView(APIView):
    """
    Bulk delete multiple media files from an apartment.
    """
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Bulk delete media files from an apartment",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'media_ids': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_INTEGER)),
            },
            required=['media_ids']
        ),
        responses={
            200: "Media deleted successfully",
            400: "Bad Request",
            403: "Forbidden",
            404: "Media not found"
        }
    )
    def delete(self, request):
        """
        Delete multiple media files.
        """
        media_ids = request.data.get('media_ids', [])
        
        if not media_ids:
            return Response(
                {'error': _("No media IDs provided.")},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get media objects
        media_objects = ApartmentMedia.objects.filter(id__in=media_ids)
        
        if not media_objects.exists():
            return Response(
                {'error': _("No media found with the provided IDs.")},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions for all media
        unauthorized = []
        for media in media_objects:
            if request.user != media.apartment.owner and request.user.role != 'admin':
                unauthorized.append(media.id)
        
        if unauthorized:
            return Response(
                {
                    'error': _("You don't have permission to delete some of the selected media."),
                    'unauthorized_ids': unauthorized
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Delete files from storage and database
        deleted_count = 0
        for media in media_objects:
            try:
                if media.file:
                    media.file.delete(save=False)
            except Exception as e:
                logger.warning(f"Failed to delete file {media.id}: {str(e)}")
            
            media.delete()
            deleted_count += 1
        
        return Response(
            {
                'message': _(f"Successfully deleted {deleted_count} media file(s)."),
                'deleted_count': deleted_count
            },
            status=status.HTTP_200_OK
        )

class ApartmentMediaListView(generics.ListAPIView):
    """
    List all media files for a specific apartment.
    """
    serializer_class = ApartmentMediaSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        """Get media files for the specified apartment."""
        apartment_id = self.kwargs.get('apartment_id')
        apartment = get_object_or_404(Apartment, id=apartment_id)
        
        # If apartment is not verified and user is not owner/admin, return empty
        if not apartment.is_verified:
            user = self.request.user
            if not user.is_authenticated or (user != apartment.owner and user.role != 'admin'):
                return ApartmentMedia.objects.none()
        
        return ApartmentMedia.objects.filter(apartment=apartment).order_by('-uploaded_at')
    
    def list(self, request, *args, **kwargs):
        """Override list to return appropriate response."""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'count': queryset.count(),
            'results': serializer.data
        }, status=status.HTTP_200_OK)
