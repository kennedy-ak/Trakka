from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ProjectForm, ReportFilterForm, TimeEntryForm, TimerStartForm
from .models import Project, TimeEntry, TimerSession, WeeklyTimesheet

# ============== Helper Functions ==============


def get_user_role(user):
    """Get the user's role from UserProfile"""
    if hasattr(user, "profile"):
        return user.profile.role
    return "WORKER"


def is_manager_or_admin(user):
    """Check if user is manager or admin"""
    role = get_user_role(user)
    return role in ["MANAGER", "ADMIN"] or user.is_superuser


def is_admin(user):
    """Check if user is admin"""
    return get_user_role(user) == "ADMIN" or user.is_superuser


def get_week_start_end():
    """Get the start and end of the current week (Monday to Sunday)"""
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    return start_of_week, end_of_week


# ============== Dashboard View ==============


@login_required
def dashboard(request):
    """Main dashboard view"""
    user = request.user
    role = get_user_role(user)

    # Redirect admins to the custom admin dashboard
    if role == "ADMIN":
        return redirect("adminpanel:admin_dashboard")
    week_start, week_end = get_week_start_end()

    # Get running timer for the current user
    running_timer = TimerSession.objects.filter(user=user, is_running=True).first()

    # Get this week's entries for current user
    if role == "WORKER":
        week_entries = TimeEntry.objects.filter(
            user=user, date__range=[week_start, week_end]
        )
    else:
        # Managers and admins see all entries
        week_entries = TimeEntry.objects.filter(date__range=[week_start, week_end])

    total_hours_week = sum(entry.duration_hours for entry in week_entries)
    recent_entries = TimeEntry.objects.filter(user=user).order_by("-created_at")[:5]

    # Get pending approvals count for managers/admins
    pending_approvals_count = 0
    pending_weekly_approvals_count = 0
    if role in ["MANAGER", "ADMIN"]:
        pending_approvals_count = TimeEntry.objects.filter(status="PENDING").count()
        pending_weekly_approvals_count = WeeklyTimesheet.objects.filter(
            status="SUBMITTED"
        ).count()

    # Get active projects count
    active_projects_count = Project.objects.filter(is_active=True).count()

    # Get or create current week's WeeklyTimesheet for workers
    current_week = None
    if role == "WORKER":
        current_week, created = WeeklyTimesheet.objects.get_or_create(
            user=user,
            week_start_date=week_start,
            defaults={"week_end_date": week_end, "status": "DRAFT"},
        )

    context = {
        "running_timer": running_timer,
        "total_hours_week": total_hours_week,
        "recent_entries": recent_entries,
        "pending_approvals_count": pending_approvals_count,
        "pending_weekly_approvals_count": pending_weekly_approvals_count,
        "active_projects_count": active_projects_count,
        "week_start": week_start,
        "week_end": week_end,
        "current_week": current_week,
    }
    return render(request, "dashboard.html", context)


# ============== Project Views ==============


@login_required
def project_list(request):
    """List all projects"""
    role = get_user_role(request.user)

    if role == "WORKER":
        projects = Project.objects.filter(is_active=True)
    else:
        projects = Project.objects.all()

    paginator = Paginator(projects, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "can_create": role in ["MANAGER", "ADMIN"],
    }
    return render(request, "projects/project_list.html", context)


@login_required
def project_create(request):
    """Create a new project (managers and admins only)"""
    role = get_user_role(request.user)
    if role not in ["MANAGER", "ADMIN"]:
        messages.error(request, "You do not have permission to create projects.")
        return redirect("project_list")

    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.save()
            messages.success(request, "Project created successfully.")
            return redirect("project_detail", pk=project.pk)
    else:
        form = ProjectForm()

    return render(request, "projects/project_create.html", {"form": form})


@login_required
def project_detail(request, pk):
    """View project details"""
    project = get_object_or_404(Project, pk=pk)
    entries = project.time_entries.all().order_by("-date", "-created_at")

    # Calculate statistics
    total_hours = project.total_hours
    approved_hours = project.total_hours_approved

    context = {
        "project": project,
        "entries": entries,
        "total_hours": total_hours,
        "approved_hours": approved_hours,
        "can_edit": is_manager_or_admin(request.user),
    }
    return render(request, "projects/project_detail.html", context)


@login_required
def project_update(request, pk):
    """Update a project (managers and admins only)"""
    role = get_user_role(request.user)
    if role not in ["MANAGER", "ADMIN"]:
        messages.error(request, "You do not have permission to edit projects.")
        return redirect("project_list")

    project = get_object_or_404(Project, pk=pk)

    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, "Project updated successfully.")
            return redirect("project_detail", pk=project.pk)
    else:
        form = ProjectForm(instance=project)

    return render(
        request, "projects/project_create.html", {"form": form, "project": project}
    )


@login_required
def project_delete(request, pk):
    """Delete a project (admins only)"""
    if not is_admin(request.user):
        messages.error(request, "Only admins can delete projects.")
        return redirect("project_list")

    project = get_object_or_404(Project, pk=pk)

    if request.method == "POST":
        project.delete()
        messages.success(request, "Project deleted successfully.")
        return redirect("project_list")

    return render(request, "projects/project_delete.html", {"project": project})


# ============== Time Entry Views ==============


@login_required
def timesheet_list(request):
    """List time entries"""
    role = get_user_role(request.user)

    # Base queryset
    if role == "WORKER":
        entries = TimeEntry.objects.filter(user=request.user)
    else:
        entries = TimeEntry.objects.all()

    # Apply filters
    status_filter = request.GET.get("status")
    project_filter = request.GET.get("project")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    if status_filter:
        entries = entries.filter(status=status_filter)
    if project_filter:
        entries = entries.filter(project_id=project_filter)
    if date_from:
        entries = entries.filter(date__gte=date_from)
    if date_to:
        entries = entries.filter(date__lte=date_to)

    entries = entries.order_by("-date", "-created_at")

    # Get filter options
    projects = Project.objects.filter(is_active=True)

    paginator = Paginator(entries, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "projects": projects,
        "status_filter": status_filter,
        "project_filter": project_filter,
        "date_from": date_from,
        "date_to": date_to,
    }
    return render(request, "timesheets/timesheet_list.html", context)


@login_required
def timesheet_create(request):
    """Create a new time entry"""
    if request.method == "POST":
        form = TimeEntryForm(request.POST, user=request.user)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.entry_type = "MANUAL"
            entry.duration_minutes = form.cleaned_data["computed_duration_minutes"]
            # Combine date + time for start_time and end_time
            entry_date = form.cleaned_data["date"]
            entry.start_time = datetime.combine(
                entry_date, form.cleaned_data["parsed_start_time"]
            )
            entry.end_time = datetime.combine(
                entry_date, form.cleaned_data["parsed_end_time"]
            )

            # Get week boundaries
            week_start = entry_date - timedelta(days=entry_date.weekday())
            week_end = week_start + timedelta(days=6)

            # Get or create weekly timesheet
            weekly_timesheet, created = WeeklyTimesheet.objects.get_or_create(
                user=request.user,
                week_start_date=week_start,
                defaults={"week_end_date": week_end, "status": "DRAFT"},
            )

            # Only allow adding to DRAFT or REJECTED weeks
            if weekly_timesheet.status not in ["DRAFT", "REJECTED"]:
                messages.error(
                    request, f"Cannot add entries to a {weekly_timesheet.status} week."
                )
                return redirect("timesheet_list")

            entry.weekly_timesheet = weekly_timesheet
            entry.save()
            messages.success(request, "Time entry created successfully.")
            return redirect("timesheet_list")
    else:
        form = TimeEntryForm(user=request.user)

    return render(request, "timesheets/timesheet_create.html", {"form": form})


@login_required
def timesheet_detail(request, pk):
    """View time entry details"""
    entry = get_object_or_404(TimeEntry, pk=pk)

    # Check permissions
    role = get_user_role(request.user)
    if role == "WORKER" and entry.user != request.user:
        messages.error(request, "You can only view your own time entries.")
        return redirect("timesheet_list")

    context = {
        "entry": entry,
        "can_edit": role == "ADMIN" or entry.user == request.user,
        "can_approve": role in ["MANAGER", "ADMIN"],
    }
    return render(request, "timesheets/timesheet_detail.html", context)


@login_required
def timesheet_update(request, pk):
    """Update a time entry"""
    entry = get_object_or_404(TimeEntry, pk=pk)
    role = get_user_role(request.user)

    # Check permissions
    if role == "WORKER" and entry.user != request.user:
        messages.error(request, "You can only edit your own time entries.")
        return redirect("timesheet_list")

    if entry.status == "APPROVED" and not is_admin(request.user):
        messages.error(request, "Cannot edit approved entries.")
        return redirect("timesheet_detail", pk=pk)

    # Check if weekly timesheet allows editing
    if entry.weekly_timesheet and entry.weekly_timesheet.status not in [
        "DRAFT",
        "REJECTED",
    ]:
        if not is_admin(request.user):
            messages.error(
                request,
                f"Cannot edit entries in a {entry.weekly_timesheet.status} week.",
            )
            return redirect("timesheet_detail", pk=pk)

    if request.method == "POST":
        form = TimeEntryForm(request.POST, instance=entry, user=request.user)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.duration_minutes = form.cleaned_data["computed_duration_minutes"]
            entry_date = form.cleaned_data["date"]
            entry.start_time = datetime.combine(
                entry_date, form.cleaned_data["parsed_start_time"]
            )
            entry.end_time = datetime.combine(
                entry_date, form.cleaned_data["parsed_end_time"]
            )
            entry.save()
            messages.success(request, "Time entry updated successfully.")
            return redirect("timesheet_detail", pk=pk)
    else:
        form = TimeEntryForm(instance=entry, user=request.user)

    return render(
        request, "timesheets/timesheet_create.html", {"form": form, "entry": entry}
    )


@login_required
def timesheet_delete(request, pk):
    """Delete a time entry"""
    entry = get_object_or_404(TimeEntry, pk=pk)
    role = get_user_role(request.user)

    # Check permissions
    if role == "WORKER" and entry.user != request.user:
        messages.error(request, "You can only delete your own time entries.")
        return redirect("timesheet_list")

    if entry.status == "APPROVED" and not is_admin(request.user):
        messages.error(request, "Cannot delete approved entries.")
        return redirect("timesheet_detail", pk=pk)

    # Check if weekly timesheet allows deleting
    if entry.weekly_timesheet and entry.weekly_timesheet.status not in [
        "DRAFT",
        "REJECTED",
    ]:
        if not is_admin(request.user):
            messages.error(
                request,
                f"Cannot delete entries in a {entry.weekly_timesheet.status} week.",
            )
            return redirect("timesheet_detail", pk=pk)

    if request.method == "POST":
        entry.delete()
        messages.success(request, "Time entry deleted successfully.")
        return redirect("timesheet_list")

    return render(request, "timesheets/timesheet_delete.html", {"entry": entry})


# ============== Timer Views ==============


@login_required
def timer_start(request):
    """Start a new timer session"""
    if request.method == "POST":
        form = TimerStartForm(request.POST)
        if form.is_valid():
            # Check if user already has a running timer
            existing_timer = TimerSession.objects.filter(
                user=request.user, is_running=True
            ).first()

            if existing_timer:
                messages.error(
                    request, "You already have a running timer. Please stop it first."
                )
                return redirect("dashboard")

            # Create timer session from form data
            TimerSession.objects.create(
                user=request.user,
                project=form.cleaned_data["project"],
                description=form.cleaned_data.get("description", ""),
            )
            messages.success(request, "Timer started successfully.")
            return redirect("dashboard")
    else:
        form = TimerStartForm()

    return render(request, "timesheets/timer_start.html", {"form": form})


@login_required
def timer_stop(request, pk):
    """Stop a running timer and create a time entry"""
    timer = get_object_or_404(TimerSession, pk=pk, user=request.user)

    if not timer.is_running:
        messages.error(request, "This timer is already stopped.")
        return redirect("dashboard")

    if request.method == "POST":
        # Calculate duration
        end_time = timezone.now()
        duration_minutes = timer.duration_minutes
        entry_date = timer.start_time.date()

        # Get week boundaries
        week_start = entry_date - timedelta(days=entry_date.weekday())
        week_end = week_start + timedelta(days=6)

        # Get or create weekly timesheet
        weekly_timesheet, created = WeeklyTimesheet.objects.get_or_create(
            user=request.user,
            week_start_date=week_start,
            defaults={"week_end_date": week_end, "status": "DRAFT"},
        )

        # Only allow adding to DRAFT or REJECTED weeks
        if weekly_timesheet.status not in ["DRAFT", "REJECTED"]:
            messages.error(
                request, f"Cannot add entries to a {weekly_timesheet.status} week."
            )
            timer.is_running = False
            timer.save()
            return redirect("dashboard")

        # Create time entry
        entry = TimeEntry.objects.create(
            user=request.user,
            project=timer.project,
            date=entry_date,
            duration_minutes=duration_minutes,
            description=timer.description
            or f"Timer session: {timer.start_time.strftime('%Y-%m-%d %H:%M')}",
            entry_type="TIMER",
            start_time=timer.start_time,
            end_time=end_time,
            status="PENDING",
            weekly_timesheet=weekly_timesheet,
        )

        # Stop the timer
        timer.is_running = False
        timer.save()

        messages.success(
            request,
            f"Timer stopped. Time entry created for {duration_minutes} minutes.",
        )
        return redirect("timesheet_detail", pk=entry.pk)

    return render(request, "timesheets/timer_stop.html", {"timer": timer})


@login_required
def timer_status(request):
    """API endpoint to check timer status"""
    timer = TimerSession.objects.filter(user=request.user, is_running=True).first()

    if timer:
        data = {
            "is_running": True,
            "timer_id": timer.pk,
            "project": timer.project.name,
            "description": timer.description,
            "start_time": timer.start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_minutes": timer.duration_minutes,
            "elapsed_time": timer.elapsed_time,
        }
    else:
        data = {
            "is_running": False,
        }

    return JsonResponse(data)


# ============== Approval Views ==============


@login_required
def approval_list(request):
    """List pending approvals for managers/admins"""
    role = get_user_role(request.user)

    if role not in ["MANAGER", "ADMIN"]:
        messages.error(request, "You do not have permission to view approvals.")
        return redirect("dashboard")

    entries = TimeEntry.objects.filter(status="PENDING").order_by(
        "-date", "-created_at"
    )

    paginator = Paginator(entries, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
    }
    return render(request, "approvals/approval_list.html", context)


@login_required
def approve_entry(request, pk):
    """Approve a time entry"""
    role = get_user_role(request.user)

    if role not in ["MANAGER", "ADMIN"]:
        messages.error(request, "You do not have permission to approve entries.")
        return redirect("dashboard")

    entry = get_object_or_404(TimeEntry, pk=pk)

    if entry.status != "PENDING":
        messages.warning(request, "This entry has already been processed.")
        return redirect("approval_list")

    if request.method == "POST":
        entry.status = "APPROVED"
        entry.approved_by = request.user
        entry.approved_at = timezone.now()
        entry.save()
        messages.success(request, "Time entry approved successfully.")
        return redirect("approval_list")

    return render(request, "approvals/approve_entry.html", {"entry": entry})


@login_required
def reject_entry(request, pk):
    """Reject a time entry"""
    role = get_user_role(request.user)

    if role not in ["MANAGER", "ADMIN"]:
        messages.error(request, "You do not have permission to reject entries.")
        return redirect("dashboard")

    entry = get_object_or_404(TimeEntry, pk=pk)

    if entry.status != "PENDING":
        messages.warning(request, "This entry has already been processed.")
        return redirect("approval_list")

    if request.method == "POST":
        entry.status = "REJECTED"
        entry.approved_by = request.user
        entry.approved_at = timezone.now()
        entry.rejection_reason = request.POST.get("reason", "")
        entry.save()
        messages.success(request, "Time entry rejected successfully.")
        return redirect("approval_list")

    return render(request, "approvals/reject_entry.html", {"entry": entry})


# ============== Report Views ==============


@login_required
def report_summary(request):
    """Summary report view"""
    role = get_user_role(request.user)

    # Get filters
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    project_filter = request.GET.get("project")
    user_filter = request.GET.get("user")

    # Base queryset
    if role == "WORKER":
        entries = TimeEntry.objects.filter(user=request.user)
    else:
        entries = TimeEntry.objects.all()

    # Apply filters
    if date_from:
        entries = entries.filter(date__gte=date_from)
    if date_to:
        entries = entries.filter(date__lte=date_to)
    if project_filter:
        entries = entries.filter(project_id=project_filter)
    if user_filter and role != "WORKER":
        entries = entries.filter(user_id=user_filter)

    # Calculate statistics
    total_entries = entries.count()
    total_hours = sum(entry.duration_hours for entry in entries)

    # Group by project
    project_stats = (
        entries.values("project__name")
        .annotate(total_hours=Sum("duration_minutes") / 60, entry_count=Count("id"))
        .order_by("-total_hours")
    )

    # Group by user (for managers/admins)
    if role != "WORKER":
        user_stats = (
            entries.values("user__username", "user__profile__role")
            .annotate(total_hours=Sum("duration_minutes") / 60, entry_count=Count("id"))
            .order_by("-total_hours")
        )
    else:
        user_stats = []

    # Group by status
    status_stats = (
        entries.values("status")
        .annotate(total_hours=Sum("duration_minutes") / 60, entry_count=Count("id"))
        .order_by("-total_hours")
    )

    # Get filter options
    projects = Project.objects.filter(is_active=True)
    users = User.objects.all() if role != "WORKER" else []

    context = {
        "total_entries": total_entries,
        "total_hours": round(total_hours, 2),
        "project_stats": project_stats,
        "user_stats": user_stats,
        "status_stats": status_stats,
        "projects": projects,
        "users": users,
        "date_from": date_from,
        "date_to": date_to,
        "project_filter": project_filter,
        "user_filter": user_filter,
    }
    return render(request, "reports/report_summary.html", context)


@login_required
def report_detail(request):
    """Detailed report with all time entries"""
    role = get_user_role(request.user)

    # Get filters
    form = ReportFilterForm(request.GET or None)

    # Base queryset
    if role == "WORKER":
        entries = TimeEntry.objects.filter(user=request.user)
    else:
        entries = TimeEntry.objects.all()

    # Apply filters
    if form.is_valid():
        if form.cleaned_data.get("date_from"):
            entries = entries.filter(date__gte=form.cleaned_data["date_from"])
        if form.cleaned_data.get("date_to"):
            entries = entries.filter(date__lte=form.cleaned_data["date_to"])
        if form.cleaned_data.get("project"):
            entries = entries.filter(project=form.cleaned_data["project"])
        if form.cleaned_data.get("user") and role != "WORKER":
            entries = entries.filter(user=form.cleaned_data["user"])
        if form.cleaned_data.get("status"):
            entries = entries.filter(status=form.cleaned_data["status"])

    entries = entries.order_by("-date", "-created_at")

    paginator = Paginator(entries, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "form": form,
    }
    return render(request, "reports/report_detail.html", context)


@login_required
def report_export(request):
    """Export report to CSV"""
    import csv

    from django.http import HttpResponse

    role = get_user_role(request.user)

    # Get filters
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    project_filter = request.GET.get("project")
    user_filter = request.GET.get("user")

    # Base queryset
    if role == "WORKER":
        entries = TimeEntry.objects.filter(user=request.user)
    else:
        entries = TimeEntry.objects.all()

    # Apply filters
    if date_from:
        entries = entries.filter(date__gte=date_from)
    if date_to:
        entries = entries.filter(date__lte=date_to)
    if project_filter:
        entries = entries.filter(project_id=project_filter)
    if user_filter and role != "WORKER":
        entries = entries.filter(user_id=user_filter)

    entries = entries.order_by("-date")

    # Create CSV response
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="timesheet_report.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "Date",
            "User",
            "Project",
            "Description",
            "Duration (hours)",
            "Status",
            "Entry Type",
        ]
    )

    for entry in entries:
        writer.writerow(
            [
                entry.date,
                entry.user.username,
                entry.project.name,
                entry.description,
                entry.duration_hours,
                entry.status,
                entry.entry_type,
            ]
        )

    return response


# ============== Weekly Timesheet Views ==============


@login_required
def weekly_timesheet_detail(request, week_start):
    """View weekly timesheet details"""
    from datetime import datetime

    week_start_date = datetime.strptime(week_start, "%Y-%m-%d").date()

    # Get weekly timesheet
    weekly_timesheet = get_object_or_404(
        WeeklyTimesheet, user=request.user, week_start_date=week_start_date
    )

    # Get all entries for this week grouped by day
    entries = weekly_timesheet.time_entries.all().order_by("date", "-created_at")

    # Group entries by date
    from itertools import groupby

    entries_by_date = {}
    for date_key, items in groupby(entries, key=lambda e: e.date):
        entries_by_date[date_key] = list(items)

    context = {
        "weekly_timesheet": weekly_timesheet,
        "entries": entries,
        "entries_by_date": entries_by_date,
        "can_submit": weekly_timesheet.status in ["DRAFT", "REJECTED"]
        and weekly_timesheet.entry_count > 0,
    }
    return render(request, "timesheets/weekly_timesheet_detail.html", context)


@login_required
def submit_week(request, week_start):
    """Submit weekly timesheet for approval"""
    from datetime import datetime

    week_start_date = datetime.strptime(week_start, "%Y-%m-%d").date()

    # Get weekly timesheet
    weekly_timesheet = get_object_or_404(
        WeeklyTimesheet, user=request.user, week_start_date=week_start_date
    )

    # Validate status
    if weekly_timesheet.status not in ["DRAFT", "REJECTED"]:
        messages.error(request, f"Cannot submit a {weekly_timesheet.status} week.")
        return redirect("dashboard")

    # Validate has entries
    if weekly_timesheet.entry_count == 0:
        messages.error(
            request, "Cannot submit an empty week. Please add at least one time entry."
        )
        return redirect("dashboard")

    # Validate week has ended (can only submit after Sunday)
    today = timezone.now().date()
    if today <= weekly_timesheet.week_end_date:
        messages.error(
            request, "You can only submit a week after it has ended (after Sunday)."
        )
        return redirect("dashboard")

    if request.method == "POST":
        notes = request.POST.get("notes", "")

        # Update weekly timesheet
        weekly_timesheet.status = "SUBMITTED"
        weekly_timesheet.submitted_at = timezone.now()
        weekly_timesheet.notes = notes
        weekly_timesheet.save()

        # Update all entries to PENDING status
        weekly_timesheet.time_entries.all().update(status="PENDING")

        messages.success(
            request,
            f'Week of {week_start_date.strftime("%b %d")} submitted for approval.',
        )
        return redirect("dashboard")

    # Get entries grouped by date for display
    entries = weekly_timesheet.time_entries.all().order_by("date", "-created_at")
    from itertools import groupby

    entries_by_date = {}
    for date_key, items in groupby(entries, key=lambda e: e.date):
        entries_by_date[date_key] = list(items)

    context = {
        "weekly_timesheet": weekly_timesheet,
        "entries": entries,
        "entries_by_date": entries_by_date,
    }
    return render(request, "timesheets/submit_week.html", context)


@login_required
def weekly_approval_list(request):
    """List weekly timesheets pending approval (managers/admins only)"""
    role = get_user_role(request.user)

    if role not in ["MANAGER", "ADMIN"]:
        messages.error(request, "You do not have permission to view weekly approvals.")
        return redirect("dashboard")

    # Get all submitted weekly timesheets
    weekly_timesheets = WeeklyTimesheet.objects.filter(status="SUBMITTED").order_by(
        "-submitted_at"
    )

    paginator = Paginator(weekly_timesheets, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
    }
    return render(request, "approvals/weekly_approval_list.html", context)


@login_required
def approve_weekly_timesheet(request, pk):
    """Approve a weekly timesheet"""
    role = get_user_role(request.user)

    if role not in ["MANAGER", "ADMIN"]:
        messages.error(
            request, "You do not have permission to approve weekly timesheets."
        )
        return redirect("dashboard")

    weekly_timesheet = get_object_or_404(WeeklyTimesheet, pk=pk)

    if weekly_timesheet.status != "SUBMITTED":
        messages.warning(request, "This weekly timesheet has already been processed.")
        return redirect("weekly_approval_list")

    if request.method == "POST":
        # Update weekly timesheet
        weekly_timesheet.status = "APPROVED"
        weekly_timesheet.approved_by = request.user
        weekly_timesheet.approved_at = timezone.now()
        weekly_timesheet.save()

        # Update all time entries to APPROVED
        weekly_timesheet.time_entries.all().update(
            status="APPROVED",
            approved_by=request.user,
            approved_at=timezone.now(),
        )

        messages.success(
            request,
            f"Weekly timesheet for "
            f"{weekly_timesheet.user.username} approved successfully.",
        )
        return redirect("weekly_approval_list")

    # Get entries for display
    entries = weekly_timesheet.time_entries.all().order_by("date", "-created_at")

    context = {
        "weekly_timesheet": weekly_timesheet,
        "entries": entries,
    }
    return render(request, "approvals/approve_weekly_timesheet.html", context)


@login_required
def reject_weekly_timesheet(request, pk):
    """Reject a weekly timesheet"""
    role = get_user_role(request.user)

    if role not in ["MANAGER", "ADMIN"]:
        messages.error(
            request, "You do not have permission to reject weekly timesheets."
        )
        return redirect("dashboard")

    weekly_timesheet = get_object_or_404(WeeklyTimesheet, pk=pk)

    if weekly_timesheet.status != "SUBMITTED":
        messages.warning(request, "This weekly timesheet has already been processed.")
        return redirect("weekly_approval_list")

    if request.method == "POST":
        rejection_reason = request.POST.get("reason", "")

        if not rejection_reason:
            messages.error(request, "Please provide a rejection reason.")
            return redirect("reject_weekly_timesheet", pk=pk)

        # Update weekly timesheet
        weekly_timesheet.status = "REJECTED"
        weekly_timesheet.approved_by = request.user
        weekly_timesheet.approved_at = timezone.now()
        weekly_timesheet.rejection_reason = rejection_reason
        weekly_timesheet.save()

        # Update all time entries to REJECTED
        weekly_timesheet.time_entries.all().update(
            status="REJECTED",
            approved_by=request.user,
            approved_at=timezone.now(),
            rejection_reason=rejection_reason,
        )

        messages.success(
            request, f"Weekly timesheet for {weekly_timesheet.user.username} rejected."
        )
        return redirect("weekly_approval_list")

    # Get entries for display
    entries = weekly_timesheet.time_entries.all().order_by("date", "-created_at")

    context = {
        "weekly_timesheet": weekly_timesheet,
        "entries": entries,
    }
    return render(request, "approvals/reject_weekly_timesheet.html", context)
