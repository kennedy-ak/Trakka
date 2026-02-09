from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import (ProjectForm, TimeEntryForm, TimerStartForm,
                    UserProfileForm, UserRegistrationForm)
from .models import (Project, TimeEntry, TimerSession, UserProfile,
                     WeeklyTimesheet)


class UserModelTests(TestCase):
    """Tests for UserProfile model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_user_profile_creation(self):
        """Test that UserProfile can be created"""
        profile = UserProfile.objects.create(
            user=self.user, role="WORKER", department="Engineering"
        )
        self.assertEqual(profile.user, self.user)
        self.assertEqual(profile.role, "WORKER")
        self.assertEqual(profile.department, "Engineering")

    def test_user_profile_str(self):
        """Test UserProfile string representation"""
        profile = UserProfile.objects.create(
            user=self.user, role="MANAGER", department="Sales"
        )
        self.assertEqual(str(profile), "testuser - MANAGER")


class ProjectModelTests(TestCase):
    """Tests for Project model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="adminuser", password="testpass123"
        )
        self.project = Project.objects.create(
            name="Test Project",
            description="A test project",
            created_by=self.user,
            budget_hours=100,
        )

    def test_project_creation(self):
        """Test that Project can be created"""
        self.assertEqual(self.project.name, "Test Project")
        self.assertEqual(self.project.created_by, self.user)
        self.assertTrue(self.project.is_active)
        self.assertEqual(self.project.budget_hours, 100)

    def test_project_total_hours(self):
        """Test total_hours property"""
        user = User.objects.create_user(username="worker", password="pass")
        TimeEntry.objects.create(
            user=user,
            project=self.project,
            date=date.today(),
            duration_minutes=120,
            description="Test work",
        )
        self.assertEqual(self.project.total_hours, 2.0)

    def test_project_total_hours_approved(self):
        """Test total_hours_approved property"""
        user = User.objects.create_user(username="worker", password="pass")
        TimeEntry.objects.create(
            user=user,
            project=self.project,
            date=date.today(),
            duration_minutes=180,
            description="Test work",
            status="APPROVED",
        )
        self.assertEqual(self.project.total_hours_approved, 3.0)

    def test_project_members(self):
        """Test project members many-to-many relationship"""
        worker = User.objects.create_user(username="worker", password="pass")
        self.project.members.add(worker)
        self.assertIn(worker, self.project.members.all())


class TimeEntryModelTests(TestCase):
    """Tests for TimeEntry model"""

    def setUp(self):
        self.user = User.objects.create_user(username="worker", password="pass")
        self.admin = User.objects.create_user(username="admin", password="pass")
        self.project = Project.objects.create(
            name="Test Project", created_by=self.admin
        )

    def test_time_entry_creation(self):
        """Test that TimeEntry can be created"""
        entry = TimeEntry.objects.create(
            user=self.user,
            project=self.project,
            date=date.today(),
            duration_minutes=60,
            description="Test work",
        )
        self.assertEqual(entry.user, self.user)
        self.assertEqual(entry.project, self.project)
        self.assertEqual(entry.status, "PENDING")

    def test_duration_hours_property(self):
        """Test duration_hours property"""
        entry = TimeEntry.objects.create(
            user=self.user,
            project=self.project,
            date=date.today(),
            duration_minutes=90,
            description="Test work",
        )
        self.assertEqual(entry.duration_hours, 1.5)

    def test_time_entry_default_entry_type(self):
        """Test default entry type is MANUAL"""
        entry = TimeEntry.objects.create(
            user=self.user,
            project=self.project,
            date=date.today(),
            duration_minutes=60,
            description="Test work",
        )
        self.assertEqual(entry.entry_type, "MANUAL")

    def test_time_entry_status_choices(self):
        """Test status choices"""
        entry = TimeEntry.objects.create(
            user=self.user,
            project=self.project,
            date=date.today(),
            duration_minutes=60,
            description="Test work",
        )
        entry.status = "APPROVED"
        entry.save()
        self.assertEqual(entry.status, "APPROVED")


class WeeklyTimesheetModelTests(TestCase):
    """Tests for WeeklyTimesheet model"""

    def setUp(self):
        self.user = User.objects.create_user(username="worker", password="pass")
        self.admin = User.objects.create_user(username="admin", password="pass")
        self.project = Project.objects.create(
            name="Test Project", created_by=self.admin
        )
        # Create a week (Monday to Sunday)
        self.week_start = date(2025, 1, 6)  # Monday
        self.week_end = date(2025, 1, 12)  # Sunday

    def test_weekly_timesheet_creation(self):
        """Test that WeeklyTimesheet can be created"""
        sheet = WeeklyTimesheet.objects.create(
            user=self.user,
            week_start_date=self.week_start,
            week_end_date=self.week_end,
            status="DRAFT",
        )
        self.assertEqual(sheet.user, self.user)
        self.assertEqual(sheet.status, "DRAFT")

    def test_weekly_timesheet_total_hours(self):
        """Test total_hours property"""
        sheet = WeeklyTimesheet.objects.create(
            user=self.user,
            week_start_date=self.week_start,
            week_end_date=self.week_end,
        )
        # Create entries for this week
        for i in range(3):
            TimeEntry.objects.create(
                user=self.user,
                project=self.project,
                date=self.week_start + timedelta(days=i),
                duration_minutes=120,
                description=f"Work day {i}",
                weekly_timesheet=sheet,
            )
        self.assertEqual(sheet.total_hours, 6.0)

    def test_weekly_timesheet_entry_count(self):
        """Test entry_count property"""
        sheet = WeeklyTimesheet.objects.create(
            user=self.user,
            week_start_date=self.week_start,
            week_end_date=self.week_end,
        )
        TimeEntry.objects.create(
            user=self.user,
            project=self.project,
            date=self.week_start,
            duration_minutes=60,
            description="Work",
            weekly_timesheet=sheet,
        )
        self.assertEqual(sheet.entry_count, 1)

    def test_unique_constraint_on_week_start(self):
        """Test that user cannot have two timesheets for same week"""
        WeeklyTimesheet.objects.create(
            user=self.user,
            week_start_date=self.week_start,
            week_end_date=self.week_end,
        )
        with self.assertRaises(Exception):  # IntegrityError
            WeeklyTimesheet.objects.create(
                user=self.user,
                week_start_date=self.week_start,
                week_end_date=self.week_end,
            )


class TimerSessionModelTests(TestCase):
    """Tests for TimerSession model"""

    def setUp(self):
        self.user = User.objects.create_user(username="worker", password="pass")
        self.admin = User.objects.create_user(username="admin", password="pass")
        self.project = Project.objects.create(
            name="Test Project", created_by=self.admin
        )

    def test_timer_session_creation(self):
        """Test that TimerSession can be created"""
        timer = TimerSession.objects.create(
            user=self.user,
            project=self.project,
            description="Test work",
        )
        self.assertTrue(timer.is_running)
        self.assertIsNotNone(timer.start_time)

    def test_timer_elapsed_time_property(self):
        """Test elapsed_time property"""
        timer = TimerSession.objects.create(
            user=self.user,
            project=self.project,
        )
        elapsed = timer.elapsed_time
        self.assertIsInstance(elapsed, str)
        self.assertRegex(elapsed, r"\d{2}:\d{2}")


class TimeEntryFormTests(TestCase):
    """Tests for TimeEntryForm"""

    def setUp(self):
        self.user = User.objects.create_user(username="worker", password="pass")
        self.admin = User.objects.create_user(username="admin", password="pass")
        self.project = Project.objects.create(
            name="Test Project", created_by=self.admin, is_active=True
        )

    def test_form_valid_with_time_inputs(self):
        """Test form is valid with proper time inputs"""
        form_data = {
            "project": self.project.pk,
            "date": date.today(),
            "description": "Test work",
            "start_time_input": "09:00",
            "end_time_input": "11:00",
        }
        form = TimeEntryForm(data=form_data, user=self.user)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["computed_duration_minutes"], 120)

    def test_form_invalid_end_before_start(self):
        """Test form is invalid when end time is before start time"""
        form_data = {
            "project": self.project.pk,
            "date": date.today(),
            "description": "Test work",
            "start_time_input": "14:00",
            "end_time_input": "10:00",
        }
        form = TimeEntryForm(data=form_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn(
            "End time must be after start time", form.errors.get("__all__", [""])[0]
        )

    def test_form_invalid_same_start_end_time(self):
        """Test form is invalid when start and end times are same"""
        form_data = {
            "project": self.project.pk,
            "date": date.today(),
            "description": "Test work",
            "start_time_input": "10:00",
            "end_time_input": "10:00",
        }
        form = TimeEntryForm(data=form_data, user=self.user)
        self.assertFalse(form.is_valid())


class ProjectFormTests(TestCase):
    """Tests for ProjectForm"""

    def test_form_valid(self):
        """Test form is valid with correct data"""
        form_data = {
            "name": "New Project",
            "description": "Project description",
            "budget_hours": 50,
            "is_active": True,
        }
        form = ProjectForm(data=form_data)
        self.assertTrue(form.is_valid())


class TimerStartFormTests(TestCase):
    """Tests for TimerStartForm"""

    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="pass")
        self.project = Project.objects.create(
            name="Test Project", created_by=self.admin, is_active=True
        )

    def test_form_valid_with_description(self):
        """Test form is valid with project and description"""
        form_data = {
            "project": self.project.pk,
            "description": "Working on task",
        }
        form = TimerStartForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_valid_without_description(self):
        """Test form is valid without description (optional field)"""
        form_data = {
            "project": self.project.pk,
        }
        form = TimerStartForm(data=form_data)
        self.assertTrue(form.is_valid())


class UserRegistrationFormTests(TestCase):
    """Tests for UserRegistrationForm"""

    def test_form_valid_with_matching_passwords(self):
        """Test form is valid when passwords match"""
        form_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "first_name": "New",
            "last_name": "User",
            "password": "testpass123",
            "password_confirm": "testpass123",
            "role": "WORKER",
            "department": "Engineering",
        }
        form = UserRegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_invalid_with_mismatched_passwords(self):
        """Test form is invalid when passwords don't match"""
        form_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "first_name": "New",
            "last_name": "User",
            "password": "testpass123",
            "password_confirm": "differentpass",
            "role": "WORKER",
        }
        form = UserRegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())


class ViewTests(TestCase):
    """Tests for views"""

    def setUp(self):
        """Set up test users and data"""
        # Create users with different roles
        self.worker_user = User.objects.create_user(
            username="worker", password="testpass123"
        )
        self.worker_profile = UserProfile.objects.create(
            user=self.worker_user, role="WORKER", department="Engineering"
        )

        self.manager_user = User.objects.create_user(
            username="manager", password="testpass123"
        )
        self.manager_profile = UserProfile.objects.create(
            user=self.manager_user, role="MANAGER", department="Engineering"
        )

        self.admin_user = User.objects.create_user(
            username="admin", password="testpass123"
        )
        self.admin_profile = UserProfile.objects.create(
            user=self.admin_user, role="ADMIN", department="Management"
        )

        # Create a project
        self.project = Project.objects.create(
            name="Test Project",
            description="A test project",
            created_by=self.admin_user,
            is_active=True,
        )
        self.project.members.add(self.worker_user)

        # Create a time entry
        self.time_entry = TimeEntry.objects.create(
            user=self.worker_user,
            project=self.project,
            date=date.today(),
            duration_minutes=120,
            description="Test work",
            status="PENDING",
        )

    def test_dashboard_redirects_unauthenticated(self):
        """Test dashboard redirects unauthenticated users"""
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_authenticated_worker(self):
        """Test dashboard displays for authenticated worker"""
        self.client.login(username="worker", password="testpass123")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")

    def test_admin_redirected_to_admin_panel(self):
        """Test admin is redirected to custom admin dashboard"""
        self.client.login(username="admin", password="testpass123")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_project_list_worker(self):
        """Test project list for worker"""
        self.client.login(username="worker", password="testpass123")
        response = self.client.get(reverse("project_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Project")

    def test_project_create_worker_denied(self):
        """Test worker cannot create project"""
        self.client.login(username="worker", password="testpass123")
        response = self.client.get(reverse("project_create"))
        self.assertEqual(response.status_code, 302)  # Redirect

    def test_project_create_manager_allowed(self):
        """Test manager can create project"""
        self.client.login(username="manager", password="testpass123")
        response = self.client.get(reverse("project_create"))
        self.assertEqual(response.status_code, 200)

    def test_timesheet_create_authenticated(self):
        """Test timesheet create page for authenticated user"""
        self.client.login(username="worker", password="testpass123")
        response = self.client.get(reverse("timesheet_create"))
        self.assertEqual(response.status_code, 200)

    def test_timesheet_detail_owner(self):
        """Test user can view own timesheet details"""
        self.client.login(username="worker", password="testpass123")
        response = self.client.get(
            reverse("timesheet_detail", kwargs={"pk": self.time_entry.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_timesheet_detail_non_owner_denied(self):
        """Test user cannot view other's timesheet details"""
        # Create another worker with their own entry
        other_worker = User.objects.create_user(username="worker2", password="pass")
        UserProfile.objects.create(user=other_worker, role="WORKER")
        other_entry = TimeEntry.objects.create(
            user=other_worker,
            project=self.project,
            date=date.today(),
            duration_minutes=60,
            description="Other work",
        )

        self.client.login(username="worker", password="testpass123")
        response = self.client.get(
            reverse("timesheet_detail", kwargs={"pk": other_entry.pk})
        )
        self.assertEqual(response.status_code, 302)  # Redirect

    def test_approval_list_manager_allowed(self):
        """Test manager can access approval list"""
        self.client.login(username="manager", password="testpass123")
        response = self.client.get(reverse("approval_list"))
        self.assertEqual(response.status_code, 200)

    def test_approval_list_worker_denied(self):
        """Test worker cannot access approval list"""
        self.client.login(username="worker", password="testpass123")
        response = self.client.get(reverse("approval_list"))
        self.assertEqual(response.status_code, 302)  # Redirect

    def test_approve_entry_manager(self):
        """Test manager can approve entry"""
        self.client.login(username="manager", password="testpass123")
        response = self.client.post(
            reverse("approve_entry", kwargs={"pk": self.time_entry.pk})
        )
        self.assertEqual(response.status_code, 302)  # Redirect after approval

        # Check status was updated
        self.time_entry.refresh_from_db()
        self.assertEqual(self.time_entry.status, "APPROVED")

    def test_approve_entry_worker_denied(self):
        """Test worker cannot approve entry"""
        self.client.login(username="worker", password="testpass123")
        response = self.client.post(
            reverse("approve_entry", kwargs={"pk": self.time_entry.pk})
        )
        self.assertEqual(response.status_code, 302)  # Redirect

        # Status should remain unchanged
        self.time_entry.refresh_from_db()
        self.assertEqual(self.time_entry.status, "PENDING")

    def test_timer_start_authenticated(self):
        """Test authenticated user can start timer"""
        self.client.login(username="worker", password="testpass123")
        response = self.client.post(
            reverse("timer_start"),
            {"project": self.project.pk, "description": "Test work"},
        )
        self.assertEqual(response.status_code, 302)  # Redirect after start

        # Check timer was created
        self.assertTrue(
            TimerSession.objects.filter(user=self.worker_user, is_running=True).exists()
        )

    def test_timer_status_api(self):
        """Test timer status API endpoint"""
        self.client.login(username="worker", password="testpass123")
        response = self.client.get(reverse("timer_status"))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            str(response.content, encoding="utf-8"), '{"is_running": false}'
        )


class WeeklyTimesheetViewTests(TestCase):
    """Tests for weekly timesheet views"""

    def setUp(self):
        self.worker = User.objects.create_user(username="worker", password="pass")
        UserProfile.objects.create(user=self.worker, role="WORKER")

        self.manager = User.objects.create_user(username="manager", password="pass")
        UserProfile.objects.create(user=self.manager, role="MANAGER")

        self.project = Project.objects.create(
            name="Test Project", created_by=self.manager
        )

        # Create a weekly timesheet
        self.week_start = date(2025, 1, 6)
        self.week_end = date(2025, 1, 12)
        self.weekly_sheet = WeeklyTimesheet.objects.create(
            user=self.worker,
            week_start_date=self.week_start,
            week_end_date=self.week_end,
            status="DRAFT",
        )

        # Add time entries
        TimeEntry.objects.create(
            user=self.worker,
            project=self.project,
            date=self.week_start,
            duration_minutes=120,
            description="Monday work",
            weekly_timesheet=self.weekly_sheet,
        )

    def test_weekly_timesheet_detail_owner(self):
        """Test user can view their weekly timesheet"""
        self.client.login(username="worker", password="pass")
        url = reverse("weekly_timesheet_detail", args=["2025-01-06"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_weekly_approval_list_manager(self):
        """Test manager can view weekly approval list"""
        # Submit the timesheet
        self.weekly_sheet.status = "SUBMITTED"
        self.weekly_sheet.save()

        self.client.login(username="manager", password="pass")
        response = self.client.get(reverse("weekly_approval_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "worker")

    def test_weekly_approval_list_worker_denied(self):
        """Test worker cannot access weekly approval list"""
        self.client.login(username="worker", password="pass")
        response = self.client.get(reverse("weekly_approval_list"))
        self.assertEqual(response.status_code, 302)

    def test_approve_weekly_timesheet_manager(self):
        """Test manager can approve weekly timesheet"""
        self.weekly_sheet.status = "SUBMITTED"
        self.weekly_sheet.save()

        self.client.login(username="manager", password="pass")
        response = self.client.post(
            reverse("approve_weekly_timesheet", kwargs={"pk": self.weekly_sheet.pk})
        )
        self.assertEqual(response.status_code, 302)

        # Check status was updated
        self.weekly_sheet.refresh_from_db()
        self.assertEqual(self.weekly_sheet.status, "APPROVED")

        # Check all entries were approved
        for entry in self.weekly_sheet.time_entries.all():
            self.assertEqual(entry.status, "APPROVED")


class ReportViewTests(TestCase):
    """Tests for report views"""

    def setUp(self):
        self.worker = User.objects.create_user(username="worker", password="pass")
        UserProfile.objects.create(user=self.worker, role="WORKER")

        self.manager = User.objects.create_user(username="manager", password="pass")
        UserProfile.objects.create(user=self.manager, role="MANAGER")

        self.project = Project.objects.create(
            name="Test Project", created_by=self.manager, is_active=True
        )

        TimeEntry.objects.create(
            user=self.worker,
            project=self.project,
            date=date.today(),
            duration_minutes=120,
            description="Test work",
            status="APPROVED",
        )

    def test_report_summary_worker(self):
        """Test worker can access report summary"""
        self.client.login(username="worker", password="pass")
        response = self.client.get(reverse("report_summary"))
        self.assertEqual(response.status_code, 200)

    def test_report_summary_manager(self):
        """Test manager can access report summary with all data"""
        self.client.login(username="manager", password="pass")
        response = self.client.get(reverse("report_summary"))
        self.assertEqual(response.status_code, 200)

    def test_report_export_csv(self):
        """Test CSV export functionality"""
        self.client.login(username="worker", password="pass")
        response = self.client.get(reverse("report_export"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")


class EdgeCaseTests(TestCase):
    """Tests for edge cases and special scenarios"""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="pass")
        UserProfile.objects.create(user=self.user, role="WORKER")
        self.admin = User.objects.create_user(username="admin", password="pass")
        UserProfile.objects.create(user=self.admin, role="ADMIN")

        self.project = Project.objects.create(
            name="Test Project", created_by=self.admin
        )

    def test_multiple_timers_prevented(self):
        """Test user cannot have multiple running timers"""
        # Create first timer
        TimerSession.objects.create(
            user=self.user, project=self.project, is_running=True
        )

        self.client.login(username="testuser", password="pass")
        self.client.post(
            reverse("timer_start"),
            {"project": self.project.pk, "description": "Second timer"},
        )

        # Should not create second timer
        self.assertEqual(
            TimerSession.objects.filter(user=self.user, is_running=True).count(), 1
        )

    def test_edit_approved_entry_denied(self):
        """Test approved entries cannot be edited by non-admin"""
        entry = TimeEntry.objects.create(
            user=self.user,
            project=self.project,
            date=date.today(),
            duration_minutes=60,
            description="Test",
            status="APPROVED",
        )

        self.client.login(username="testuser", password="pass")
        response = self.client.get(reverse("timesheet_update", kwargs={"pk": entry.pk}))
        self.assertEqual(response.status_code, 302)  # Redirect

    def test_delete_approved_entry_denied(self):
        """Test approved entries cannot be deleted by non-admin"""
        entry = TimeEntry.objects.create(
            user=self.user,
            project=self.project,
            date=date.today(),
            duration_minutes=60,
            description="Test",
            status="APPROVED",
        )

        self.client.login(username="testuser", password="pass")
        response = self.client.post(
            reverse("timesheet_delete", kwargs={"pk": entry.pk})
        )
        self.assertEqual(response.status_code, 302)  # Redirect

        # Entry should still exist
        self.assertTrue(TimeEntry.objects.filter(pk=entry.pk).exists())

    def test_submit_empty_week_denied(self):
        """Test empty week cannot be submitted"""
        week_start = date(2025, 1, 6)
        week_end = date(2025, 1, 12)
        sheet = WeeklyTimesheet.objects.create(
            user=self.user,
            week_start_date=week_start,
            week_end_date=week_end,
            status="DRAFT",
        )

        self.client.login(username="testuser", password="pass")
        response = self.client.post(reverse("submit_week", args=["2025-01-06"]))
        self.assertEqual(response.status_code, 302)

        # Status should remain DRAFT
        sheet.refresh_from_db()
        self.assertEqual(sheet.status, "DRAFT")

    def test_submit_current_week_denied(self):
        """Test current week cannot be submitted before it ends"""
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        sheet = WeeklyTimesheet.objects.create(
            user=self.user,
            week_start_date=week_start,
            week_end_date=week_end,
            status="DRAFT",
        )

        # Add an entry
        TimeEntry.objects.create(
            user=self.user,
            project=self.project,
            date=week_start,
            duration_minutes=60,
            description="Work",
            weekly_timesheet=sheet,
        )

        self.client.login(username="testuser", password="pass")
        response = self.client.post(
            reverse("submit_week", args=[week_start.strftime("%Y-%m-%d")])
        )
        self.assertEqual(response.status_code, 302)

        # Status should remain DRAFT
        sheet.refresh_from_db()
        self.assertEqual(sheet.status, "DRAFT")

    def test_project_delete_by_admin_only(self):
        """Test only admins can delete projects"""
        self.client.login(username="testuser", password="pass")
        response = self.client.post(
            reverse("project_delete", kwargs={"pk": self.project.pk})
        )
        self.assertEqual(response.status_code, 302)

        # Project should still exist
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())

        # Now try as admin
        self.client.login(username="admin", password="pass")
        response = self.client.post(
            reverse("project_delete", kwargs={"pk": self.project.pk})
        )
        self.assertEqual(response.status_code, 302)

        # Project should be deleted
        self.assertFalse(Project.objects.filter(pk=self.project.pk).exists())


class TimerIntegrationTests(TestCase):
    """Integration tests for timer functionality"""

    def setUp(self):
        self.user = User.objects.create_user(username="worker", password="pass")
        UserProfile.objects.create(user=self.user, role="WORKER")

        self.admin = User.objects.create_user(username="admin", password="pass")
        UserProfile.objects.create(user=self.admin, role="ADMIN")

        self.project = Project.objects.create(
            name="Test Project", created_by=self.admin, is_active=True
        )

    def test_timer_start_stop_workflow(self):
        """Test complete timer start and stop workflow"""
        self.client.login(username="worker", password="pass")

        # Start timer
        response = self.client.post(
            reverse("timer_start"),
            {"project": self.project.pk, "description": "Test work"},
        )
        self.assertEqual(response.status_code, 302)

        timer = TimerSession.objects.filter(user=self.user, is_running=True).first()
        self.assertIsNotNone(timer)

        # Stop timer
        response = self.client.post(reverse("timer_stop", kwargs={"pk": timer.pk}))
        self.assertEqual(response.status_code, 302)

        # Check timer is stopped
        timer.refresh_from_db()
        self.assertFalse(timer.is_running)

        # Check time entry was created
        self.assertTrue(
            TimeEntry.objects.filter(
                user=self.user, project=self.project, entry_type="TIMER"
            ).exists()
        )
