# stayease/apartments/urls.py
from django.urls import path
from . import views

app_name = 'apartments'

urlpatterns = [
    # Apartment endpoints
    path('', views.ApartmentListView.as_view(), name='apartment-list'),
    path('<int:pk>/', views.ApartmentDetailView.as_view(), name='apartment-detail'),
    path('<int:pk>/verify/', views.ApartmentVerifyView.as_view(), name='apartment-verify'),
    
    # Media endpoints
    path('<int:apartment_id>/media/upload/', views.ApartmentMediaUploadView.as_view(), name='apartment-media-upload'),
    path('media/<int:media_id>/delete/', views.ApartmentMediaDeleteView.as_view(), name='apartment-media-delete'),
    path('<int:apartment_id>/media/', views.ApartmentMediaListView.as_view(), name='apartment-media-list'),
    path('media/<int:pk>/', views.ApartmentMediaDetailView.as_view(), name='apartment-media-detail'),
    path('media/bulk-delete/', views.ApartmentMediaBulkDeleteView.as_view(), name='apartment-media-bulk-delete'),
]