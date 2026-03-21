# stayease/utils/email_utils.py
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils.translation import gettext_lazy as _
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
        """
        subject = _('New Booking - StayEase Africa')
        
        # Get owner email
        owner_email = booking.apartment.owner.email
        
        # Prepare context
        context = {
            'booking_id': booking.id,
            'apartment_title': booking.apartment.title,
            'user_email': booking.user.email,
            'user_full_name': booking.user.full_name,
            'start_date': booking.start_date,
            'end_date': booking.end_date,
            'nights': booking.get_nights(),
            'total_price': booking.total_price,
            'phone_number': booking.phone_number,
            'apartment_location': f"{booking.apartment.district}, {booking.apartment.sector}",
            'booking_created_at': booking.created_at,
            'company_name': 'StayEase Africa',
            'support_email': settings.DEFAULT_FROM_EMAIL,
            'dashboard_url': settings.FRONTEND_URL + '/dashboard',
        }
        
        # Send to apartment owner
        recipients = [owner_email] if owner_email else []
        
        # Add admin emails
        recipients.extend(admin_emails)
        
        return EmailNotificationService.send_notification_email(
            subject=subject,
            template_name='booking_created.html',
            context=context,
            to_emails=recipients,
        )
    
    @staticmethod
    def send_payment_submitted_email(payment, admin_emails):
        """
        Send notification when payment is submitted.
        """
        subject = _('Payment Submitted - StayEase Africa')
        
        # Get owner email
        owner_email = payment.booking.apartment.owner.email
        
        # Prepare context
        context = {
            'booking_id': payment.booking.id,
            'payment_id': payment.id,
            'apartment_title': payment.booking.apartment.title,
            'user_email': payment.booking.user.email,
            'user_full_name': payment.booking.user.full_name,
            'amount': payment.amount,
            'payment_method': payment.get_payment_method_display(),
            'transaction_id': payment.transaction_id,
            'submitted_at': payment.created_at,
            'company_name': 'StayEase Africa',
            'support_email': settings.DEFAULT_FROM_EMAIL,
            'dashboard_url': settings.FRONTEND_URL + '/dashboard',
            'verify_url': f"{settings.FRONTEND_URL}/admin/payments/{payment.id}/verify",
        }
        
        # Send to apartment owner
        recipients = [owner_email] if owner_email else []
        
        # Add admin emails
        recipients.extend(admin_emails)
        
        return EmailNotificationService.send_notification_email(
            subject=subject,
            template_name='payment_submitted.html',
            context=context,
            to_emails=recipients,
        )
    
    @staticmethod
    def send_payment_verified_email(payment):
        """
        Send notification when payment is verified.
        """
        subject = _('Payment Verified - StayEase Africa')
        
        # Get user and owner emails
        user_email = payment.booking.user.email
        owner_email = payment.booking.apartment.owner.email
        
        # Prepare context
        context = {
            'booking_id': payment.booking.id,
            'payment_id': payment.id,
            'apartment_title': payment.booking.apartment.title,
            'user_full_name': payment.booking.user.full_name,
            'owner_full_name': payment.booking.apartment.owner.full_name,
            'amount': payment.amount,
            'payment_method': payment.get_payment_method_display(),
            'transaction_id': payment.transaction_id,
            'verified_at': payment.verified_at,
            'start_date': payment.booking.start_date,
            'end_date': payment.booking.end_date,
            'company_name': 'StayEase Africa',
            'support_email': settings.DEFAULT_FROM_EMAIL,
            'dashboard_url': settings.FRONTEND_URL + '/dashboard',
        }
        
        # Send to both user and owner
        recipients = [user_email, owner_email]
        
        return EmailNotificationService.send_notification_email(
            subject=subject,
            template_name='payment_verified.html',
            context=context,
            to_emails=recipients,
        )
    
    @staticmethod
    def send_payment_rejected_email(payment, rejection_reason=None):
        """
        Send notification when payment is rejected.
        """
        subject = _('Payment Rejected - StayEase Africa')
        
        # Get user and owner emails
        user_email = payment.booking.user.email
        owner_email = payment.booking.apartment.owner.email
        
        # Prepare context
        context = {
            'booking_id': payment.booking.id,
            'payment_id': payment.id,
            'apartment_title': payment.booking.apartment.title,
            'user_full_name': payment.booking.user.full_name,
            'owner_full_name': payment.booking.apartment.owner.full_name,
            'amount': payment.amount,
            'payment_method': payment.get_payment_method_display(),
            'transaction_id': payment.transaction_id,
            'rejected_at': payment.verified_at,
            'rejection_reason': rejection_reason or _('Payment could not be verified.'),
            'company_name': 'StayEase Africa',
            'support_email': settings.DEFAULT_FROM_EMAIL,
            'dashboard_url': settings.FRONTEND_URL + '/dashboard',
        }
        
        # Send to both user and owner
        recipients = [user_email, owner_email]
        
        return EmailNotificationService.send_notification_email(
            subject=subject,
            template_name='payment_rejected.html',
            context=context,
            to_emails=recipients,
        )