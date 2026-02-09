import pytest
from django.contrib.auth.models import User

from timesheet.models import Project, UserProfile, WeeklyTimesheet


@pytest.fixture
def worker_user(db):
    """Create a worker user"""
    user = User.objects.create_user(username="worker", password="testpass123")
    UserProfile.objects.create(user=user, role="WORKER", department="Engineering")
    return user


@pytest.fixture
def manager_user(db):
    """Create a manager user"""
    user = User.objects.create_user(username="manager", password="testpass123")
    UserProfile.objects.create(user=user, role="MANAGER", department="Management")
    return user


@pytest.fixture
def admin_user(db):
    """Create an admin user"""
    user = User.objects.create_user(username="admin", password="testpass123")
    UserProfile.objects.create(user=user, role="ADMIN", department="Management")
    return user


@pytest.fixture
def project(db, admin_user):
    """Create a test project"""
    return Project.objects.create(
        name="Test Project",
        description="A test project",
        created_by=admin_user,
        is_active=True,
    )


@pytest.fixture
def weekly_timesheet(db, worker_user):
    """Create a weekly timesheet"""
    from datetime import date, timedelta

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    return WeeklyTimesheet.objects.create(
        user=worker_user,
        week_start_date=week_start,
        week_end_date=week_end,
        status="DRAFT",
    )
