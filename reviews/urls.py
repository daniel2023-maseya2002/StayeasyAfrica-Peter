# stayease/reviews/urls.py
from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    # Review creation and listing
    path('', views.ReviewCreateView.as_view(), name='review-create'),
    path('<int:pk>/', views.ReviewDetailView.as_view(), name='review-detail'),
    
    # Apartment reviews (nested under apartments)
    path('apartments/<int:apartment_id>/reviews/', views.ApartmentReviewsView.as_view(), name='apartment-reviews'),
    path('apartments/<int:apartment_id>/rating/', views.ApartmentRatingView.as_view(), name='apartment-rating'),
]