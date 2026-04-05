# stayease/users/views.py


from rest_framework import status, generics, mixins
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from drf_yasg.utils import swagger_auto_schema
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.utils.html import strip_tags
from drf_yasg import openapi
from django.conf import settings
from django.template.loader import render_to_string
import logging
import os
from django.utils import timezone
from django.contrib.sites.models import Site
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer,
    UserCreateSerializer, UserUpdateSerializer, RequestOTPSerializer, VerifyOTPSerializer, ResetPasswordSerializer
)
from .models import User, PasswordResetOTP
from .permissions import IsAdmin, IsOwnerOrSelf, IsAdminOrReadOnly

logger = logging.getLogger(__name__)


class RegisterView(generics.CreateAPIView):
    """
    User registration endpoint.
    Creates a new user and returns JWT tokens.
    """
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Register a new user (guest or owner)",
        request_body=RegisterSerializer,
        responses={
            201: openapi.Response('User created successfully', UserSerializer),
            400: 'Bad Request'
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        user_data = UserSerializer(user).data
        
        return Response(
            {
                'user': user_data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                },
                'message': _('User registered successfully.'),
            },
            status=status.HTTP_201_CREATED
        )


class LoginView(APIView):
    """
    User login endpoint.
    Authenticates user and returns JWT tokens.
    """
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Login with email and password",
        request_body=LoginSerializer,
        responses={
            200: openapi.Response('Login successful'),
            401: 'Unauthorized'
        }
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        user_data = UserSerializer(user).data
        
        return Response(
            {
                'user': user_data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                },
                'message': _('Login successful.'),
            },
            status=status.HTTP_200_OK
        )


class LogoutView(APIView):
    """
    User logout endpoint.
    Blacklists the refresh token.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
                return Response(
                    {'message': _('Successfully logged out.')},
                    status=status.HTTP_200_OK
                )
            return Response(
                {'error': _('Refresh token is required.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class UserListView(generics.ListAPIView):
    """
    List all users (Admin only).
    Supports filtering and search.
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    queryset = User.objects.all().order_by('-date_joined')
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by role
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        
        # Filter by verification status
        is_verified = self.request.query_params.get('is_verified')
        if is_verified is not None:
            is_verified_bool = is_verified.lower() == 'true'
            queryset = queryset.filter(is_verified=is_verified_bool)
        
        # Search by email or full_name
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(email__icontains=search) |
                models.Q(full_name__icontains=search)
            )
        
        return queryset


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a user.
    - Admin can access any user
    - Regular users can only access their own profile
    """
    permission_classes = [IsAuthenticated, IsOwnerOrSelf]
    queryset = User.objects.all()
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UserUpdateSerializer
        return UserSerializer
    
    def perform_destroy(self, instance):
        """Soft delete by deactivating user instead of hard delete."""
        instance.is_active = False
        instance.save()
        return Response(
            {'message': _('User deactivated successfully.')},
            status=status.HTTP_200_OK
        )


class AdminUserCreateView(generics.CreateAPIView):
    """
    Admin endpoint to create users.
    Can create any role including admin.
    """
    serializer_class = UserCreateSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def perform_create(self, serializer):
        user = serializer.save()
        return user


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    View and update current user's profile.
    Convenience endpoint for accessing own profile.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserUpdateSerializer
    
    def get_object(self):
        return self.request.user
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UserUpdateSerializer
        return UserSerializer
    


class RequestOTPView(APIView):
    """
    Request OTP for password reset.
    """
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_description="Request OTP for password reset",
        request_body=RequestOTPSerializer,
        responses={
            200: "OTP sent successfully",
            400: "Bad Request"
        }
    )
    def post(self, request):
        serializer = RequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        # Clean up expired OTPs before creating new one
        PasswordResetOTP.cleanup_expired_otps()
        
        # Check if there's already a verified OTP for this email
        existing_verified = PasswordResetOTP.objects.filter(
            email=email,
            is_verified=True,
            is_used=False
        ).exists()
        
        if existing_verified:
            return Response(
                {
                    'error': _('An active verified OTP already exists. '
                              'Please use it to reset your password or wait for it to expire.')
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate new OTP
        otp = PasswordResetOTP.generate_otp()
        
        # Save OTP to database
        otp_record = PasswordResetOTP.objects.create(
            email=email,
            otp=otp
        )
        
        # Send OTP via email
        try:
            self.send_otp_via_email(request, email, otp)
            
            return Response(
                {
                    'message': _('OTP sent successfully. Please check your email.'),
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Failed to send OTP email to {email}: {str(e)}")
            # Delete the OTP record if email sending fails
            otp_record.delete()
            return Response(
                {
                    'error': _('Failed to send OTP email. Please try again later.')
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get_logo_url(self, request):
        """
        Get the logo URL for the email template.
        Returns either a full URL with domain or None if logo not found.
        """
        try:
            # Get the current site domain
            current_site = Site.objects.get_current()
            domain = current_site.domain
            protocol = 'https' if request.is_secure() else 'http'
            
            # Build the full URL for the logo
            # Method 1: If using Django's media URL
            if settings.MEDIA_URL:
                logo_relative_path = 'logo.png'
                logo_url = f"{protocol}://{domain}{settings.MEDIA_URL}{logo_relative_path}"
                
                # Check if file exists
                logo_full_path = os.path.join(settings.MEDIA_ROOT, 'logo.png')
                if os.path.exists(logo_full_path):
                    return logo_url
            
            # Method 2: If using static files
            if settings.STATIC_URL:
                logo_url = f"{protocol}://{domain}{settings.STATIC_URL}images/logo.png"
                return logo_url
            
            # Method 3: Embed logo as base64 (if file is small)
            logo_full_path = os.path.join(settings.MEDIA_ROOT, 'logo.png')
            if os.path.exists(logo_full_path):
                import base64
                with open(logo_full_path, 'rb') as logo_file:
                    logo_data = base64.b64encode(logo_file.read()).decode('utf-8')
                    return f"data:image/png;base64,{logo_data}"
            
            return None
            
        except Exception as e:
            logger.warning(f"Could not get logo URL: {str(e)}")
            return None
    
    def send_otp_via_email(self, request, email, otp):
        """
        Send OTP via email with HTML template and logo.
        """
        subject = _('StayEase Africa - Password Reset Code')
        
        # Get logo URL
        logo_url = self.get_logo_url(request)
        
        # Context for the email template
        context = {
            'otp': otp,
            'email': email,
            'logo_url': logo_url,
            'year': timezone.now().year,
            'company_name': 'StayEase Africa',
            'support_email': 'support@stayeaseafrica.com',
            'reset_url': f"{request.build_absolute_uri('/')}reset-password?email={email}",  # Frontend reset URL
        }
        
        # Render HTML template
        try:
            html_message = render_to_string('emails/otp_email.html', context)
        except Exception as e:
            logger.error(f"Failed to render email template: {str(e)}")
            # Fallback to simple text email
            html_message = None
        
        # Create plain text version
        plain_message = f"""
        StayEase Africa - Password Reset Code
        
        Hello,
        
        We received a request to reset the password for your account associated with {email}.
        
        Your OTP code is: {otp}
        
        This code is valid for 10 minutes.
        
        If you didn't request this password reset, please ignore this email.
        
        Best regards,
        StayEase Africa Team
        """
        
        # Create email message
        email_message = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        
        # Attach HTML version if available
        if html_message:
            email_message.attach_alternative(html_message, "text/html")
        
        # Send email
        email_message.send(fail_silently=False)
        
        # Log success
        logger.info(f"Password reset OTP sent to {email}")
    


class VerifyOTPView(APIView):
    """
    Verify OTP for password reset.
    """
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_description="Verify OTP for password reset",
        request_body=VerifyOTPSerializer,
        responses={
            200: "OTP verified successfully",
            400: "Bad Request"
        }
    )
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        otp_record = serializer.validated_data['otp_record']
        
        # Mark OTP as verified
        otp_record.is_verified = True
        otp_record.save()
        
        return Response(
            {
                'message': _('OTP verified successfully. You can now reset your password.')
            },
            status=status.HTTP_200_OK
        )


class ResetPasswordView(APIView):
    """
    Reset password using verified OTP.
    """
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_description="Reset password using verified OTP",
        request_body=ResetPasswordSerializer,
        responses={
            200: "Password reset successfully",
            400: "Bad Request"
        }
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Reset password
        serializer.save()
        
        return Response(
            {
                'message': _('Password reset successfully. You can now login with your new password.')
            },
            status=status.HTTP_200_OK
        )

# Add this to your users/views.py temporarily
class TestAuthView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        return Response({
            'authenticated': True,
            'user_id': request.user.id,
            'user_email': request.user.email,
            'user_role': request.user.role,
        })