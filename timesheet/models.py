from datetime import datetime

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models


class UserProfile(models.Model):
    """Extend User model with role and department"""

    ROLE_CHOICES = [
        ("WORKER", "Worker"),
        ("MANAGER", "Manager"),
        ("ADMIN", "Admin"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="WORKER")
    department = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"


class Project(models.Model):
    """Project model for organizing time entries"""

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="created_projects"
    )
    members = models.ManyToManyField(
        User,
        blank=True,
        related_name="projects",
        help_text="Users who can log time to this project",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    budget_hours = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )

    def __str__(self):
        return self.name

    @property
    def total_hours(self):
        """Calculate total hours logged for this project"""
        return sum(entry.duration_hours for entry in self.time_entries.all())

    @property
    def total_hours_approved(self):
        """Calculate total approved hours for this project"""
        return sum(
            entry.duration_hours
            for entry in self.time_entries.filter(status="APPROVED")
        )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Project"
        verbose_name_plural = "Projects"


class TimeEntry(models.Model):
    """Time entry model for tracking work hours"""

    ENTRY_TYPES = [
        ("MANUAL", "Manual"),
        ("TIMER", "Timer"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="time_entries"
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="time_entries"
    )
    date = models.DateField()
    duration_minutes = models.IntegerField(validators=[MinValueValidator(1)])
    description = models.TextField()
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPES, default="MANUAL")
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_entries",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    weekly_timesheet = models.ForeignKey(
        "WeeklyTimesheet",
        on_delete=models.CASCADE,
        related_name="time_entries",
        null=True,
        blank=True,
    )

    def __str__(self):
        return (
            f"{self.user.username} - {self.project.name} - {self.duration_minutes}min"
        )

    @property
    def duration_hours(self):
        """Return duration in hours"""
        return round(self.duration_minutes / 60, 2)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name = "Time Entry"
        verbose_name_plural = "Time Entries"
        permissions = [
            ("can_approve_entries", "Can approve time entries"),
        ]


class WeeklyTimesheet(models.Model):
    """Weekly timesheet bundle for submission and approval"""

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SUBMITTED", "Submitted"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="weekly_timesheets"
    )
    week_start_date = models.DateField()  # Monday
    week_end_date = models.DateField()  # Sunday
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")

    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_weekly_timesheets",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True, help_text="Optional notes for this week")
    rejection_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-week_start_date"]
        unique_together = [["user", "week_start_date"]]
        verbose_name = "Weekly Timesheet"
        verbose_name_plural = "Weekly Timesheets"

    def __str__(self):
        return f"{self.user.username} - Week of {self.week_start_date}"

    @property
    def total_hours(self):
        return sum(entry.duration_hours for entry in self.time_entries.all())

    @property
    def entry_count(self):
        return self.time_entries.count()


class TimerSession(models.Model):
    """Active timer session model"""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="timer_sessions"
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="timer_sessions"
    )
    start_time = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)
    is_running = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - {self.project.name} - {self.start_time}"

    @property
    def duration_minutes(self):
        """Calculate current duration in minutes"""
        if self.is_running:
            delta = (
                datetime.now().replace(tzinfo=self.start_time.tzinfo) - self.start_time
            )
            return int(delta.total_seconds() / 60)
        return 0

    @property
    def duration_hours(self):
        """Return current duration in hours"""
        return round(self.duration_minutes / 60, 2)

    @property
    def elapsed_time(self):
        """Return formatted elapsed time string"""
        minutes = self.duration_minutes
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours:02d}:{mins:02d}"

    class Meta:
        ordering = ["-start_time"]
        verbose_name = "Timer Session"
        verbose_name_plural = "Timer Sessions"
