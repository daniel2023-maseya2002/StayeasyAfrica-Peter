# stayease/apartments/urls.py
from django.urls import path
from . import views

app_name = 'apartments'

urlpatterns = [
    # Apartment endpoints
    path('', views.ApartmentListView.as_view(), name='apartment-list'),
    path('<int:pk>/', views.ApartmentDetailView.as_view(), name='apartment-detail'),
    path('<int:pk>/verify/', views.ApartmentVerifyView.as_view(), name='apartment-verify'),
    
    # Owner endpoints
    path('owner/', views.OwnerApartmentListView.as_view(), name='owner-apartment-list'),
    
    # Analytics endpoint (admin only)
    path('analytics/', views.ApartmentAnalyticsView.as_view(), name='apartment-analytics'),
    
    # Media endpoints
    # List media for an apartment
    path('<int:apartment_id>/media/', views.ApartmentMediaListView.as_view(), name='apartment-media-list'),
    
    # Upload media for an apartment
    path('<int:apartment_id>/media/upload/', views.ApartmentMediaUploadView.as_view(), name='apartment-media-upload'),
    
    # Get specific media file
    path('media/<int:pk>/', views.ApartmentMediaDetailView.as_view(), name='apartment-media-detail'),
    
    # Delete specific media file
    path('media/<int:pk>/delete/', views.ApartmentMediaDeleteView.as_view(), name='apartment-media-delete'),
    
    # Bulk delete media files
    path('media/bulk-delete/', views.ApartmentMediaBulkDeleteView.as_view(), name='apartment-media-bulk-delete'),
]