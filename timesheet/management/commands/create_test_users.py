from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from timesheet.models import UserProfile


class Command(BaseCommand):
    help = 'Create test users (admin, manager, worker) for testing'

    def handle(self, *args, **options):
        # Test users data
        test_users = [
            {
                'username': 'testadmin',
                'email': 'admin@trakka.com',
                'first_name': 'Admin',
                'last_name': 'User',
                'password': 'admin123',
                'role': 'ADMIN',
                'department': 'Management'
            },
            {
                'username': 'testmanager',
                'email': 'manager@trakka.com',
                'first_name': 'Manager',
                'last_name': 'User',
                'password': 'manager123',
                'role': 'MANAGER',
                'department': 'Operations'
            },
            {
                'username': 'testworker',
                'email': 'worker@trakka.com',
                'first_name': 'Worker',
                'last_name': 'User',
                'password': 'worker123',
                'role': 'WORKER',
                'department': 'General'
            }
        ]

        for user_data in test_users:
            username = user_data['username']
            password = user_data['password']
            role = user_data['role']

            # Check if user exists
            if User.objects.filter(username=username).exists():
                user = User.objects.get(username=username)
                self.stdout.write(
                    self.style.WARNING(f'User "{username}" already exists. Skipping...')
                )
                # Update profile just in case
                if hasattr(user, 'profile'):
                    user.profile.role = role
                    user.profile.department = user_data['department']
                    user.profile.save()
                continue

            # Create user
            user = User.objects.create_user(
                username=username,
                email=user_data['email'],
                first_name=user_data['first_name'],
                last_name=user_data['last_name'],
                password=password,
                is_active=True
            )

            # Create profile
            UserProfile.objects.create(
                user=user,
                role=role,
                department=user_data['department']
            )

            self.stdout.write(
                self.style.SUCCESS(f'✓ Created {role}: {username} (password: {password})')
            )

        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('Test users created successfully!'))
        self.stdout.write('='*50)
        self.stdout.write('\nLogin Credentials:\n')
        for user_data in test_users:
            self.stdout.write(
                f"  {user_data['role']:8} | Username: {user_data['username']:12} | Password: {user_data['password']}"
            )
        self.stdout.write('\nYou can now log in at: http://127.0.0.1:8000/login/')
