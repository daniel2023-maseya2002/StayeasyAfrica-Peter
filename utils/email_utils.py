# stayease/utils/email_utils.py
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class EmailNotificationService:
    """
    Service class for sending email notifications.
    """
    
    @staticmethod
    def send_notification_email(
        subject,
        template_name,
        context,
        to_emails,
        from_email=None,
        bcc=None,
        attachments=None
    ):
        """
        Send a notification email with HTML and plain text versions.
        
        Args:
            subject: Email subject
            template_name: Name of the HTML template (without path)
            context: Dictionary of context variables for the template
            to_emails: List of recipient email addresses
            from_email: Sender email (defaults to DEFAULT_FROM_EMAIL)
            bcc: List of BCC email addresses
            attachments: List of attachments (optional)
        
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not to_emails:
            logger.warning("No recipients provided for email notification")
            return False
        
        # Ensure to_emails is a list
        if isinstance(to_emails, str):
            to_emails = [to_emails]
        
        # Remove duplicates and empty strings
        to_emails = list(set([email for email in to_emails if email]))
        
        if not to_emails:
            logger.warning("No valid recipients after filtering")
            return False
        
        try:
            # Prepare template path
            template_path = f'emails/{template_name}'
            
            # Render HTML content
            html_content = render_to_string(template_path, context)
            
            # Create plain text version by stripping HTML tags
            text_content = strip_tags(html_content)
            
            # Create email message
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email or settings.DEFAULT_FROM_EMAIL,
                to=to_emails,
                bcc=bcc,
            )
            
            # Attach HTML version
            email.attach_alternative(html_content, "text/html")
            
            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    email.attach(
                        attachment['filename'],
                        attachment['content'],
                        attachment.get('mimetype', 'application/octet-stream')
                    )
            
            # Send email
            email.send(fail_silently=False)
            
            logger.info(f"Email sent successfully to {to_emails} - Subject: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False
    
    @staticmethod
    def send_booking_created_email(booking, admin_emails):
        """
        Send notification when a booking is created.
        Includes booking code, apartment location, and owner payment number.
        """
        subject = _('Booking Created - StayEase Africa')
        
        # Get apartment and owner details
        apartment = booking.apartment
        owner = apartment.owner
        
        # Build location string
        location_parts = []
        if apartment.district:
            location_parts.append(apartment.district)
        if apartment.sector:
            location_parts.append(apartment.sector)
        elif apartment.address:
            location_parts.append(apartment.address)
        
        location = ", ".join(location_parts) if location_parts else "Location provided upon confirmation"
        
        # Get owner's phone number for payment
        owner_phone = owner.phone_number if owner.phone_number else "Not provided"
        
        # Format dates
        start_date = booking.start_date.strftime("%B %d, %Y")
        end_date = booking.end_date.strftime("%B %d, %Y")
        
        # Format total price
        total_price = f"${float(booking.total_price):,.2f}"
        
        # Prepare plain text context for fallback
        plain_text_content = f"""
StayEase Africa - Booking Confirmation

Dear {booking.user.full_name or booking.user.email},

Your booking has been successfully created.

Booking Details:
----------------------------------------
Booking Code: {booking.booking_code}
Apartment: {apartment.title}
Location: {location}
Owner Payment Number: {owner_phone}
Check-in Date: {start_date}
Check-out Date: {end_date}
Nights: {booking.get_nights()}
Total Price: {total_price}
----------------------------------------

Payment Instructions:
Please send the total amount of {total_price} to the payment number above using MTN Mobile Money or Airtel Money.

After sending the payment:
1. Go to "My Bookings" in your account
2. Click "Submit Payment" for this booking
3. Enter your transaction reference number

Your booking will be confirmed once the payment is verified.

Need Help?
Contact us at support@stayeaseafrica.com

Thank you for choosing StayEase Africa!
        """
        
        # Prepare context for HTML template
        context = {
            'booking_id': booking.id,
            'booking_code': booking.booking_code,
            'apartment_title': apartment.title,
            'apartment_location': location,
            'owner_phone_number': owner_phone,
            'user_full_name': booking.user.full_name or booking.user.email,
            'user_email': booking.user.email,
            'start_date': start_date,
            'end_date': end_date,
            'nights': booking.get_nights(),
            'total_price': total_price,
            'phone_number': booking.phone_number,
            'booking_created_at': booking.created_at,
            'company_name': 'StayEase Africa',
            'support_email': settings.DEFAULT_FROM_EMAIL,
            'dashboard_url': f"{settings.FRONTEND_URL}/my-bookings",
            'current_year': timezone.now().year,
        }
        
        # Send to user (customer)
        user_recipients = [booking.user.email]
        
        # Send to apartment owner
        owner_recipients = [owner.email] if owner.email else []
        
        # Send to admins
        admin_recipients = admin_emails if admin_emails else []
        
        # Send email to user
        try:
            # For user, use the HTML template
            template_path = 'emails/booking_created.html'
            html_content = render_to_string(template_path, context)
            text_content = strip_tags(html_content)
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=user_recipients,
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)
            logger.info(f"Booking confirmation email sent to {booking.user.email} for booking #{booking.id}")
        except Exception as e:
            logger.error(f"Failed to send booking email to user {booking.user.email}: {str(e)}")
            # Fallback to plain text
            try:
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=plain_text_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=user_recipients,
                )
                email.send(fail_silently=False)
            except Exception as fallback_error:
                logger.error(f"Fallback email also failed: {str(fallback_error)}")
        
        # Send notification to apartment owner
        if owner_recipients:
            owner_subject = _('New Booking Received - StayEase Africa')
            owner_context = {
                'booking_code': booking.booking_code,
                'apartment_title': apartment.title,
                'user_name': booking.user.full_name or booking.user.email,
                'user_email': booking.user.email,
                'user_phone': booking.phone_number,
                'start_date': start_date,
                'end_date': end_date,
                'nights': booking.get_nights(),
                'total_price': total_price,
                'dashboard_url': f"{settings.FRONTEND_URL}/owner/bookings",
            }
            
            owner_plain_text = f"""
New Booking Received!

Booking Code: {booking.booking_code}
Guest: {booking.user.full_name or booking.user.email}
Contact: {booking.phone_number}
Apartment: {apartment.title}
Dates: {start_date} to {end_date}
Nights: {booking.get_nights()}
Total Price: {total_price}

Please log in to your dashboard to manage this booking.
            """
            
            try:
                email = EmailMultiAlternatives(
                    subject=owner_subject,
                    body=owner_plain_text,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=owner_recipients,
                )
                email.send(fail_silently=False)
                logger.info(f"Booking notification sent to owner {owner.email} for booking #{booking.id}")
            except Exception as e:
                logger.error(f"Failed to send booking notification to owner: {str(e)}")
        
        # Send notification to admins
        if admin_recipients:
            admin_subject = f'New Booking Created - {booking.booking_code}'
            admin_context = {
                'booking_code': booking.booking_code,
                'booking_id': booking.id,
                'apartment_title': apartment.title,
                'user_name': booking.user.full_name or booking.user.email,
                'user_email': booking.user.email,
                'user_phone': booking.phone_number,
                'start_date': start_date,
                'end_date': end_date,
                'total_price': total_price,
                'admin_url': f"{settings.FRONTEND_URL}/admin/bookings",
            }
            
            admin_plain_text = f"""
New booking created:

Booking ID: {booking.id}
Booking Code: {booking.booking_code}
User: {booking.user.email}
Apartment: {apartment.title}
Dates: {start_date} to {end_date}
Total: {total_price}

View in admin panel.
            """
            
            try:
                email = EmailMultiAlternatives(
                    subject=admin_subject,
                    body=admin_plain_text,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=admin_recipients,
                )
                email.send(fail_silently=False)
                logger.info(f"Admin notification sent for booking #{booking.id}")
            except Exception as e:
                logger.error(f"Failed to send admin notification: {str(e)}")
        
        return True
    
    @staticmethod
    def send_payment_submitted_email(payment, admin_emails):
        """
        Send notification when payment is submitted.
        """
        subject = _('Payment Submitted - StayEase Africa')
        
        # Get owner email
        owner_email = payment.booking.apartment.owner.email
        
        # Format amount
        amount = f"${float(payment.amount):,.2f}"
        
        # Prepare plain text content
        plain_text_content = f"""
Payment has been submitted for booking.

Booking Code: {payment.booking.booking_code}
Apartment: {payment.booking.apartment.title}
Amount: {amount}
Transaction ID: {payment.transaction_id}
Payment Method: {payment.get_payment_method_display()}

The apartment owner will verify your payment shortly.
        """
        
        # Prepare context
        context = {
            'booking_id': payment.booking.id,
            'booking_code': payment.booking.booking_code,
            'payment_id': payment.id,
            'apartment_title': payment.booking.apartment.title,
            'user_email': payment.booking.user.email,
            'user_full_name': payment.booking.user.full_name,
            'amount': amount,
            'payment_method': payment.get_payment_method_display(),
            'transaction_id': payment.transaction_id,
            'submitted_at': payment.created_at,
            'company_name': 'StayEase Africa',
            'support_email': settings.DEFAULT_FROM_EMAIL,
            'dashboard_url': f"{settings.FRONTEND_URL}/my-bookings",
        }
        
        # Send to user
        user_recipients = [payment.booking.user.email]
        
        try:
            email = EmailMultiAlternatives(
                subject=subject,
                body=plain_text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=user_recipients,
            )
            email.send(fail_silently=False)
            logger.info(f"Payment submitted email sent to user for payment #{payment.id}")
        except Exception as e:
            logger.error(f"Failed to send payment submitted email to user: {str(e)}")
        
        # Send to owner
        if owner_email:
            owner_subject = _('Payment Submitted - Action Required')
            owner_plain_text = f"""
A guest has submitted payment for their booking.

Booking Code: {payment.booking.booking_code}
Guest: {payment.booking.user.email}
Apartment: {payment.booking.apartment.title}
Amount: {amount}
Transaction ID: {payment.transaction_id}
Payment Method: {payment.get_payment_method_display()}

Please verify this payment in your dashboard.
            """
            
            try:
                email = EmailMultiAlternatives(
                    subject=owner_subject,
                    body=owner_plain_text,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[owner_email],
                )
                email.send(fail_silently=False)
                logger.info(f"Payment submitted notification sent to owner for payment #{payment.id}")
            except Exception as e:
                logger.error(f"Failed to send payment submitted email to owner: {str(e)}")
        
        # Send to admins
        if admin_emails:
            admin_subject = f'Payment Submitted - Booking {payment.booking.booking_code}'
            admin_plain_text = f"""
Payment submitted for review.

Booking Code: {payment.booking.booking_code}
Guest: {payment.booking.user.email}
Apartment: {payment.booking.apartment.title}
Amount: {amount}
Transaction ID: {payment.transaction_id}
            """
            
            try:
                email = EmailMultiAlternatives(
                    subject=admin_subject,
                    body=admin_plain_text,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=admin_emails,
                )
                email.send(fail_silently=False)
                logger.info(f"Payment submitted notification sent to admins for payment #{payment.id}")
            except Exception as e:
                logger.error(f"Failed to send payment submitted email to admins: {str(e)}")
        
        return True
    
    @staticmethod
    def send_payment_verified_email(payment):
        """
        Send notification when payment is verified.
        """
        subject = _('Payment Verified - StayEase Africa')
        
        # Format amount
        amount = f"${float(payment.amount):,.2f}"
        
        # Format dates
        start_date = payment.booking.start_date.strftime("%B %d, %Y")
        end_date = payment.booking.end_date.strftime("%B %d, %Y")
        
        plain_text_content = f"""
Great news! Your payment has been verified.

Booking Code: {payment.booking.booking_code}
Apartment: {payment.booking.apartment.title}
Amount: {amount}
Your booking is now CONFIRMED!

Stay Details:
Check-in: {start_date}
Check-out: {end_date}
Nights: {payment.booking.get_nights()}

Get ready for your stay! You can find more details in your dashboard.
        """
        
        # Send to user
        user_recipients = [payment.booking.user.email]
        
        try:
            email = EmailMultiAlternatives(
                subject=subject,
                body=plain_text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=user_recipients,
            )
            email.send(fail_silently=False)
            logger.info(f"Payment verified email sent to user for payment #{payment.id}")
        except Exception as e:
            logger.error(f"Failed to send payment verified email to user: {str(e)}")
        
        # Also notify owner
        owner_email = payment.booking.apartment.owner.email
        if owner_email:
            owner_subject = _('Payment Verified - Booking Confirmed')
            owner_plain_text = f"""
You have verified a payment.

Booking Code: {payment.booking.booking_code}
Guest: {payment.booking.user.email}
Apartment: {payment.booking.apartment.title}
Amount: {amount}
The booking is now CONFIRMED.
            """
            
            try:
                email = EmailMultiAlternatives(
                    subject=owner_subject,
                    body=owner_plain_text,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[owner_email],
                )
                email.send(fail_silently=False)
                logger.info(f"Payment verified notification sent to owner for payment #{payment.id}")
            except Exception as e:
                logger.error(f"Failed to send payment verified email to owner: {str(e)}")
        
        return True
    
    @staticmethod
    def send_payment_rejected_email(payment, rejection_reason=None):
        """
        Send notification when payment is rejected.
        """
        subject = _('Payment Update - StayEase Africa')
        
        # Format amount
        amount = f"${float(payment.amount):,.2f}"
        
        reason_text = f"\nReason: {rejection_reason}" if rejection_reason else ""
        
        plain_text_content = f"""
Your payment was not verified.

Booking Code: {payment.booking.booking_code}
Apartment: {payment.booking.apartment.title}
Amount: {amount}{reason_text}

Please contact support for assistance or submit a new payment.
        """
        
        # Send to user
        user_recipients = [payment.booking.user.email]
        
        try:
            email = EmailMultiAlternatives(
                subject=subject,
                body=plain_text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=user_recipients,
            )
            email.send(fail_silently=False)
            logger.info(f"Payment rejected email sent to user for payment #{payment.id}")
        except Exception as e:
            logger.error(f"Failed to send payment rejected email to user: {str(e)}")
        
        # Also notify owner
        owner_email = payment.booking.apartment.owner.email
        if owner_email:
            owner_subject = _('Payment Rejected')
            owner_plain_text = f"""
You have rejected a payment.

Booking Code: {payment.booking.booking_code}
Guest: {payment.booking.user.email}
Apartment: {payment.booking.apartment.title}
Amount: {amount}
            """
            
            try:
                email = EmailMultiAlternatives(
                    subject=owner_subject,
                    body=owner_plain_text,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[owner_email],
                )
                email.send(fail_silently=False)
                logger.info(f"Payment rejected notification sent to owner for payment #{payment.id}")
            except Exception as e:
                logger.error(f"Failed to send payment rejected email to owner: {str(e)}")
        
        return True