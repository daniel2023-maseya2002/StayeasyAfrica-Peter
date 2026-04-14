from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Create admin user'

    def handle(self, *args, **kwargs):
        email = "maseyadaniel@gmail.com"
        password = "Smooth1."

        if User.objects.filter(email=email).exists():
            self.stdout.write("Admin already exists")
            return

        try:
            user = User.objects.create(
                email=email,
                full_name="Daniel Maseya",
                role="admin",
                is_staff=True,
                is_superuser=True,
            )
            user.set_password(password)  # 🔐 hash password properly
            user.save()

            self.stdout.write(self.style.SUCCESS("Admin created successfully"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error creating admin: {e}"))