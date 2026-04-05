# stayease/payments/urls.py
from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Admin endpoints
    path('admin/', views.AdminPaymentListView.as_view(), name='admin-payment-list'),

    # Add this line to urlpatterns
    path('owner/', views.OwnerPaymentListView.as_view(), name='owner-payment-list'),
    
    # Payment submission and listing
    path('', views.PaymentSubmitView.as_view(), name='payment-submit'),
    path('my/', views.MyPaymentsView.as_view(), name='my-payments'),
    path('owner/', views.OwnerPaymentsView.as_view(), name='owner-payments'),
    path('statistics/', views.PaymentStatisticsView.as_view(), name='payment-statistics'),
    
    # Payment actions
    path('<int:pk>/', views.PaymentDetailView.as_view(), name='payment-detail'),
    path('<int:pk>/verify/', views.PaymentVerifyView.as_view(), name='payment-verify'),
    path('<int:pk>/reject/', views.PaymentRejectView.as_view(), name='payment-reject'),
]