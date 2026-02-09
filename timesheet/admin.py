from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import (Project, TimeEntry, TimerSession, UserProfile,
                     WeeklyTimesheet)


class UserProfileInline(admin.StackedInline):
    """Inline admin for user profile"""

    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile"


class UserAdmin(BaseUserAdmin):
    """Custom user admin with profile inline"""

    inlines = (UserProfileInline,)
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "get_role",
        "is_active",
    )
    list_filter = ("is_active", "is_staff", "is_superuser")

    def get_role(self, obj):
        """Get user role from profile"""
        if hasattr(obj, "profile"):
            return obj.profile.role
        return "N/A"

    get_role.short_description = "Role"


class TimeEntryInline(admin.TabularInline):
    """Inline time entries for project admin"""

    model = TimeEntry
    extra = 0
    fields = ("user", "date", "duration_minutes", "status", "entry_type")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """Admin interface for Project model"""

    list_display = (
        "name",
        "created_by",
        "is_active",
        "budget_hours",
        "total_hours",
        "approved_hours",
        "created_at",
    )
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "total_hours", "approved_hours")
    inlines = [TimeEntryInline]

    def total_hours(self, obj):
        """Display total hours"""
        return round(obj.total_hours, 2)

    total_hours.short_description = "Total Hours"

    def approved_hours(self, obj):
        """Display approved hours"""
        return round(obj.total_hours_approved, 2)

    approved_hours.short_description = "Approved Hours"


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    """Admin interface for TimeEntry model"""

    list_display = (
        "user",
        "project",
        "date",
        "duration_minutes",
        "duration_hours",
        "status",
        "entry_type",
        "weekly_timesheet",
        "created_at",
    )
    list_filter = (
        "status",
        "entry_type",
        "date",
        "project",
        "weekly_timesheet__status",
    )
    search_fields = ("user__username", "project__name", "description")
    readonly_fields = ("created_at", "updated_at", "approved_at", "duration_hours")
    date_hierarchy = "date"

    actions = ["approve_entries", "reject_entries"]

    def approve_entries(self, request, queryset):
        """Admin action to approve selected entries"""
        updated = queryset.filter(status="PENDING").update(status="APPROVED")
        self.message_user(request, f"{updated} entries approved.")

    approve_entries.short_description = "Approve selected entries"

    def reject_entries(self, request, queryset):
        """Admin action to reject selected entries"""
        updated = queryset.filter(status="PENDING").update(status="REJECTED")
        self.message_user(request, f"{updated} entries rejected.")

    reject_entries.short_description = "Reject selected entries"


@admin.register(TimerSession)
class TimerSessionAdmin(admin.ModelAdmin):
    """Admin interface for TimerSession model"""

    list_display = ("user", "project", "start_time", "is_running", "duration_minutes")
    list_filter = ("is_running", "start_time")
    search_fields = ("user__username", "project__name")
    readonly_fields = (
        "start_time",
        "duration_minutes",
        "duration_hours",
        "elapsed_time",
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin interface for UserProfile model"""

    list_display = ("user", "role", "department")
    list_filter = ("role", "department")
    search_fields = ("user__username", "user__email", "department")


@admin.register(WeeklyTimesheet)
class WeeklyTimesheetAdmin(admin.ModelAdmin):
    """Admin interface for WeeklyTimesheet model"""

    list_display = (
        "user",
        "week_start_date",
        "week_end_date",
        "status",
        "total_hours",
        "entry_count",
        "submitted_at",
    )
    list_filter = ("status", "week_start_date", "submitted_at")
    search_fields = ("user__username", "notes", "rejection_reason")
    readonly_fields = (
        "created_at",
        "updated_at",
        "submitted_at",
        "approved_at",
        "total_hours",
        "entry_count",
    )
    date_hierarchy = "week_start_date"

    fieldsets = (
        (
            "Week Information",
            {"fields": ("user", "week_start_date", "week_end_date", "status")},
        ),
        (
            "Approval Details",
            {
                "fields": (
                    "submitted_at",
                    "approved_by",
                    "approved_at",
                    "rejection_reason",
                )
            },
        ),
        ("Notes", {"fields": ("notes",)}),
        ("Statistics", {"fields": ("total_hours", "entry_count")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
