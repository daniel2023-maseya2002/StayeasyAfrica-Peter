import random
import string
from django.utils import timezone

def generate_booking_code():
    """
    Generate a unique booking code in format: STE-XXX-XX-XX
    Example: STE-234-AB-93
    """
    # Format: STE-XXX-XX-XX
    # STE = StayEase prefix
    # XXX = 3 random digits
    # XX = 2 random uppercase letters  
    # XX = 2 random digits
    
    digits_1 = ''.join(random.choices(string.digits, k=3))
    letters = ''.join(random.choices(string.ascii_uppercase, k=2))
    digits_2 = ''.join(random.choices(string.digits, k=2))
    
    code = f"STE-{digits_1}-{letters}-{digits_2}"
    
    return code

def generate_unique_booking_code(BookingModel):
    """
    Generate a unique booking code that doesn't exist in the database.
    """
    max_attempts = 10
    
    for _ in range(max_attempts):
        code = generate_booking_code()
        if not BookingModel.objects.filter(booking_code=code).exists():
            return code
    
    # If we hit max attempts, add timestamp to ensure uniqueness
    timestamp = timezone.now().strftime('%H%M%S')
    return f"STE-{timestamp[-3:]}-{code[-5:]}"