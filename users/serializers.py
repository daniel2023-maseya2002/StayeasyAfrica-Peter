# stayease/users/serializers.py
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from .models import User, PasswordResetOTP
from django.contrib.auth import get_user_model

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    Handles user creation with role validation and password hashing.
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        validators=[validate_password]
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = [
            'email', 'full_name', 'phone_number', 'password',
            'confirm_password', 'role', 'id_type', 'id_number', 'id_document'
        ]
        extra_kwargs = {
            'id_document': {'required': False},
            'phone_number': {'required': False, 'allow_blank': True},
            'id_type': {'required': False, 'allow_null': True},
            'id_number': {'required': False, 'allow_null': True},
        }

    def validate(self, attrs):
        """Validate passwords match and role is not admin."""
        # Check password match
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError(
                {"confirm_password": _("Password fields didn't match.")}
            )
        
        # Remove confirm_password from attrs
        attrs.pop('confirm_password')
        
        # Validate role
        role = attrs.get('role')
        if role == User.Role.ADMIN:
            raise serializers.ValidationError(
                {"role": _("Admin registration is not allowed through this endpoint.")}
            )
        
        # Validate that if id_type is provided, id_number must also be provided
        id_type = attrs.get('id_type')
        id_number = attrs.get('id_number')
        
        if id_type and not id_number:
            raise serializers.ValidationError(
                {"id_number": _("ID number is required when ID type is provided.")}
            )
        
        if id_number and not id_type:
            raise serializers.ValidationError(
                {"id_type": _("ID type is required when ID number is provided.")}
            )
        
        return attrs

    def validate_id_number(self, value):
        """Validate id_number uniqueness."""
        if value:
            # Check if id_number already exists
            if User.objects.filter(id_number=value).exists():
                raise serializers.ValidationError(
                    _("A user with this ID number already exists.")
                )
        return value

    def create(self, validated_data):
        """Create user with hashed password."""
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login.
    Validates email and password, returns user object.
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        """Validate user credentials."""
        email = attrs.get('email')
        password = attrs.get('password')
        
        # Normalize email
        if email:
            email = email.lower().strip()
        
        # Authenticate user
        user = authenticate(request=self.context.get('request'), 
                           email=email, password=password)
        
        if not user:
            raise serializers.ValidationError(
                _("Unable to log in with provided credentials."),
                code='authorization'
            )
        
        if not user.is_active:
            raise serializers.ValidationError(
                _("User account is disabled."),
                code='authorization'
            )
        
        attrs['user'] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for listing and updating user data.
    Excludes sensitive fields like password.
    """
    class Meta:
        model = User
        fields = [
            'id', 'email', 'full_name', 'phone_number', 'role',
            'id_type', 'id_number', 'id_document', 'is_verified',
            'is_active', 'date_joined'
        ]
        read_only_fields = ['id', 'date_joined']
        extra_kwargs = {
            'id_document': {'required': False},
            'phone_number': {'required': False},
            'id_type': {'required': False, 'allow_null': True},
            'id_number': {'required': False, 'allow_null': True},
            'is_verified': {'read_only': True},  # Should be changed via verification process
        }


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for admin to create users.
    Allows creating any role including admin.
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        validators=[validate_password]
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = [
            'email', 'full_name', 'phone_number', 'password',
            'confirm_password', 'role', 'id_type', 'id_number', 
            'id_document', 'is_active', 'is_verified'
        ]
        extra_kwargs = {
            'id_document': {'required': False},
            'phone_number': {'required': False},
            'id_type': {'required': False, 'allow_null': True},
            'id_number': {'required': False, 'allow_null': True},
            'is_active': {'required': False},
            'is_verified': {'required': False},
        }

    def validate(self, attrs):
        """Validate passwords match."""
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError(
                {"confirm_password": _("Password fields didn't match.")}
            )
        
        attrs.pop('confirm_password')
        
        # Validate that if id_type is provided, id_number must also be provided
        id_type = attrs.get('id_type')
        id_number = attrs.get('id_number')
        
        if id_type and not id_number:
            raise serializers.ValidationError(
                {"id_number": _("ID number is required when ID type is provided.")}
            )
        
        if id_number and not id_type:
            raise serializers.ValidationError(
                {"id_type": _("ID type is required when ID number is provided.")}
            )
        
        return attrs

    def validate_id_number(self, value):
        """Validate id_number uniqueness."""
        if value:
            if User.objects.filter(id_number=value).exists():
                raise serializers.ValidationError(
                    _("A user with this ID number already exists.")
                )
        return value

    def validate_email(self, value):
        """Validate email uniqueness."""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                _("A user with this email already exists.")
            )
        return value

    def create(self, validated_data):
        """Create user with hashed password."""
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user data.
    Handles partial updates and password changes.
    """
    current_password = serializers.CharField(
        write_only=True,
        required=False,
        style={'input_type': 'password'}
    )
    new_password = serializers.CharField(
        write_only=True,
        required=False,
        style={'input_type': 'password'},
        validators=[validate_password]
    )
    confirm_new_password = serializers.CharField(
        write_only=True,
        required=False,
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = [
            'email', 'full_name', 'phone_number', 'role',
            'id_type', 'id_number', 'id_document', 'is_active',
            'current_password', 'new_password', 'confirm_new_password'
        ]
        extra_kwargs = {
            'email': {'required': False},
            'full_name': {'required': False},
            'phone_number': {'required': False},
            'role': {'required': False},
            'id_type': {'required': False, 'allow_null': True},
            'id_number': {'required': False, 'allow_null': True},
            'id_document': {'required': False},
            'is_active': {'required': False},
        }

    def validate(self, attrs):
        """Validate password change if requested."""
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_new_password')
        current_password = attrs.get('current_password')
        
        if new_password or confirm_password:
            if not current_password:
                raise serializers.ValidationError(
                    {"current_password": _("Current password is required to change password.")}
                )
            
            if new_password != confirm_password:
                raise serializers.ValidationError(
                    {"confirm_new_password": _("New password fields didn't match.")}
                )
        
        # Validate ID fields consistency
        id_type = attrs.get('id_type')
        id_number = attrs.get('id_number')
        
        if id_type and not id_number:
            raise serializers.ValidationError(
                {"id_number": _("ID number is required when ID type is provided.")}
            )
        
        if id_number and not id_type:
            raise serializers.ValidationError(
                {"id_type": _("ID type is required when ID number is provided.")}
            )
        
        return attrs

    def validate_id_number(self, value):
        """Validate id_number uniqueness excluding current user."""
        if value:
            if User.objects.filter(id_number=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError(
                    _("A user with this ID number already exists.")
                )
        return value

    def validate_email(self, value):
        """Validate email uniqueness excluding current user."""
        if value:
            if User.objects.filter(email=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError(
                    _("A user with this email already exists.")
                )
        return value

    def update(self, instance, validated_data):
        """Update user with optional password change."""
        new_password = validated_data.pop('new_password', None)
        current_password = validated_data.pop('current_password', None)
        validated_data.pop('confirm_new_password', None)
        
        # Verify current password if changing password
        if new_password:
            if not instance.check_password(current_password):
                raise serializers.ValidationError(
                    {"current_password": _("Current password is incorrect.")}
                )
            instance.set_password(new_password)
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance

class RequestOTPSerializer(serializers.Serializer):
    """
    Serializer for requesting password reset OTP.
    """
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        """
        Validate that user exists with this email.
        """
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                _("No user found with this email address.")
            )
        return value


class VerifyOTPSerializer(serializers.Serializer):
    """
    Serializer for verifying OTP.
    """
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(min_length=6, max_length=6, required=True)
    
    def validate(self, attrs):
        """
        Validate OTP is correct and not expired.
        """
        email = attrs.get('email')
        otp = attrs.get('otp')
        
        try:
            otp_record = PasswordResetOTP.objects.filter(
                email=email,
                otp=otp,
                is_verified=False,
                is_used=False
            ).latest('created_at')
        except PasswordResetOTP.DoesNotExist:
            raise serializers.ValidationError(
                {"otp": _("Invalid or expired OTP.")}
            )
        
        # Check if OTP is expired
        if otp_record.is_expired():
            otp_record.delete()
            raise serializers.ValidationError(
                {"otp": _("OTP has expired. Please request a new one.")}
            )
        
        attrs['otp_record'] = otp_record
        return attrs


class ResetPasswordSerializer(serializers.Serializer):
    """
    Serializer for resetting password using verified OTP.
    """
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(min_length=6, max_length=6, required=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password]
    )
    confirm_new_password = serializers.CharField(
        required=True,
        write_only=True
    )
    
    def validate(self, attrs):
        """
        Validate OTP and password match.
        """
        # Validate passwords match
        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError(
                {"confirm_new_password": _("Passwords don't match.")}
            )
        
        # Validate OTP
        email = attrs.get('email')
        otp = attrs.get('otp')
        
        try:
            otp_record = PasswordResetOTP.objects.get(
                email=email,
                otp=otp,
                is_verified=True,
                is_used=False
            )
        except PasswordResetOTP.DoesNotExist:
            raise serializers.ValidationError(
                {"otp": _("Invalid OTP or OTP not verified.")}
            )
        
        # Check if OTP is expired
        if otp_record.is_expired():
            otp_record.delete()
            raise serializers.ValidationError(
                {"otp": _("OTP has expired. Please request a new one.")}
            )
        
        # Check if user exists
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"email": _("User not found.")}
            )
        
        attrs['otp_record'] = otp_record
        attrs['user'] = user
        return attrs
    
    def save(self):
        """
        Reset user password and invalidate OTP.
        """
        user = self.validated_data['user']
        new_password = self.validated_data['new_password']
        otp_record = self.validated_data['otp_record']
        
        # Update user password
        user.set_password(new_password)
        user.save()
        
        # Mark OTP as used
        otp_record.is_used = True
        otp_record.save()
        
        # Clean up any other unused OTPs for this email
        PasswordResetOTP.objects.filter(
            email=user.email,
            is_used=False
        ).delete()
        
        return user