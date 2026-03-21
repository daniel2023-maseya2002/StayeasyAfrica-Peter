# stayease/bookings/urls.py
from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    # Booking CRUD
    path('', views.BookingCreateView.as_view(), name='booking-create'),
    path('my/', views.MyBookingsView.as_view(), name='my-bookings'),
    path('owner/', views.OwnerBookingsView.as_view(), name='owner-bookings'),
    path('<int:pk>/', views.BookingDetailView.as_view(), name='booking-detail'),
    
    # Payment actions
    path('<int:pk>/submit-payment/', views.SubmitPaymentView.as_view(), name='submit-payment'),
    path('<int:pk>/verify/', views.VerifyPaymentView.as_view(), name='verify-payment'),
    path('<int:pk>/cancel/', views.CancelBookingView.as_view(), name='cancel-booking'),
    
    # Availability check
    path('check-availability/', views.ApartmentAvailabilityView.as_view(), name='check-availability'),
]