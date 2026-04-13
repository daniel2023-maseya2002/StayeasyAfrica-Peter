from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Create admin user'

    def handle(self, *args, **kwargs):
        email = "maseyadaniel@gmail.com"
        password = "Smooth1."

        if not User.objects.filter(email=email).exists():
            user = User.objects.create_superuser(
                email=email,
                full_name="Admin",
                password=password,
                role="admin"
            )
            user.is_staff = True
            user.is_superuser = True
            user.save()

            self.stdout.write(self.style.SUCCESS("Admin created successfully"))
        else:
            self.stdout.write("Admin already exists")