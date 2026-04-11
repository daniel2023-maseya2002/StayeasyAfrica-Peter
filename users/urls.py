# stayease/users/urls.py
from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # Authentication endpoints
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),

     
    # Password reset endpoints
    path('auth/password-reset/request-otp/', views.RequestOTPView.as_view(), name='request-otp'),
    path('auth/password-reset/verify-otp/', views.VerifyOTPView.as_view(), name='verify-otp'),
    path('auth/password-reset/reset-password/', views.ResetPasswordView.as_view(), name='reset-password'),
    
    # User management endpoints
    path('', views.UserListView.as_view(), name='user-list'),
    path('create/', views.AdminUserCreateView.as_view(), name='admin-user-create'),
    path('profile/', views.UserProfileView.as_view(), name='user-profile'),
    path('<int:pk>/', views.UserDetailView.as_view(), name='user-detail'),

    path('test-auth/', views.TestAuthView.as_view(), name='test-auth'),

    path('auth/google/', views.GoogleLoginView.as_view(), name='google-login'),
]