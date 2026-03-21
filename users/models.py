# stayease/users/models.py
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import random
import string



class UserManager(BaseUserManager):
    """Custom user manager for the User model."""

    def create_user(self, email, full_name, password=None, **extra_fields):
        """
        Create and save a regular user with the given email, full name, and password.
        """
        if not email:
            raise ValueError(_("The Email field must be set"))
        email = self.normalize_email(email)
        user = self.model(email=email, full_name=full_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name, password=None, **extra_fields):
        """
        Create and save a superuser with the given email, full name, and password.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", User.Role.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))

        return self.create_user(email, full_name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model using email as the unique identifier.
    Supports three roles: user (guest), owner (landlord), admin (platform manager).
    """

    class Role(models.TextChoices):
        USER = "user", _("User")
        OWNER = "owner", _("Owner")
        ADMIN = "admin", _("Admin")

    class IDType(models.TextChoices):
        NATIONAL_ID = "national_id", _("National ID")
        PASSPORT = "passport", _("Passport")
        STUDENT_ID = "student_id", _("Student ID")

    email = models.EmailField(
        verbose_name=_("email address"),
        unique=True,
        error_messages={
            "unique": _("A user with that email already exists."),
        },
    )
    full_name = models.CharField(_("full name"), max_length=255)
    phone_number = models.CharField(_("phone number"), max_length=20, blank=True)
    role = models.CharField(
        _("role"),
        max_length=10,
        choices=Role.choices,
        default=Role.USER,
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )
    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site."),
    )
    is_verified = models.BooleanField(
        _("verified"),
        default=False,
        help_text=_("Designates whether the user has verified their email address."),
    )
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)
    
    # Identity verification fields
    id_type = models.CharField(
        _("ID type"),
        max_length=20,
        choices=IDType.choices,
        blank=True,
        null=True,
        help_text=_("Type of identification document"),
    )
    id_number = models.CharField(
        _("ID number"),
        max_length=100,
        unique=True,
        blank=True,
        null=True,
        help_text=_("Unique identification number"),
    )
    id_document = models.ImageField(
        _("ID document"),
        upload_to="ids/%Y/%m/%d/",
        blank=True,
        null=True,
        help_text=_("Upload a clear image of your identification document"),
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def __str__(self):
        return self.email

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)

class PasswordResetOTP(models.Model):
    """
    Model to store OTP for password reset functionality.
    """
    email = models.EmailField(_("email address"), db_index=True)
    otp = models.CharField(_("OTP"), max_length=6)
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    is_verified = models.BooleanField(_("verified"), default=False)
    is_used = models.BooleanField(_("used"), default=False)
    
    class Meta:
        verbose_name = _("Password Reset OTP")
        verbose_name_plural = _("Password Reset OTPs")
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.email} - {self.otp} - {self.created_at}"
    
    def is_expired(self, expiry_minutes=10):
        """
        Check if OTP is expired based on creation time.
        """
        expiry_time = self.created_at + timezone.timedelta(minutes=expiry_minutes)
        return timezone.now() > expiry_time
    
    @classmethod
    def generate_otp(cls):
        """
        Generate a random 6-digit OTP.
        """
        return ''.join(random.choices(string.digits, k=6))
    
    @classmethod
    def cleanup_expired_otps(cls):
        """
        Clean up expired OTPs (older than 10 minutes) that are not verified or used.
        """
        expiry_threshold = timezone.now() - timezone.timedelta(minutes=10)
        cls.objects.filter(
            created_at__lt=expiry_threshold,
            is_verified=False,
            is_used=False
        ).delete()