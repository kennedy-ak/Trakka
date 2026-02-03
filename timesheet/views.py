from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, Q, Count
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import datetime, timedelta, date
from .models import Project, TimeEntry, TimerSession, UserProfile
from .forms import (
    TimeEntryForm, ProjectForm, TimerStartForm,
    ReportFilterForm, UserProfileForm, UserRegistrationForm
)


# ============== Helper Functions ==============

def get_user_role(user):
    """Get the user's role from UserProfile"""
    if hasattr(user, 'profile'):
        return user.profile.role
    return 'WORKER'


def is_manager_or_admin(user):
    """Check if user is manager or admin"""
    role = get_user_role(user)
    return role in ['MANAGER', 'ADMIN']


def is_admin(user):
    """Check if user is admin"""
    return get_user_role(user) == 'ADMIN'


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
    week_start, week_end = get_week_start_end()

    # Get running timer for the current user
    running_timer = TimerSession.objects.filter(
        user=user,
        is_running=True
    ).first()

    # Get this week's entries for current user
    if role == 'WORKER':
        week_entries = TimeEntry.objects.filter(
            user=user,
            date__range=[week_start, week_end]
        )
    else:
        # Managers and admins see all entries
        week_entries = TimeEntry.objects.filter(
            date__range=[week_start, week_end]
        )

    total_hours_week = sum(entry.duration_hours for entry in week_entries)
    recent_entries = TimeEntry.objects.filter(
        user=user
    ).order_by('-created_at')[:5]

    # Get pending approvals count for managers/admins
    pending_approvals_count = 0
    if role in ['MANAGER', 'ADMIN']:
        pending_approvals_count = TimeEntry.objects.filter(
            status='PENDING'
        ).count()

    # Get active projects count
    active_projects_count = Project.objects.filter(is_active=True).count()

    context = {
        'running_timer': running_timer,
        'total_hours_week': total_hours_week,
        'recent_entries': recent_entries,
        'pending_approvals_count': pending_approvals_count,
        'active_projects_count': active_projects_count,
        'week_start': week_start,
        'week_end': week_end,
    }
    return render(request, 'dashboard.html', context)


# ============== Project Views ==============

@login_required
def project_list(request):
    """List all projects"""
    role = get_user_role(request.user)

    if role == 'WORKER':
        projects = Project.objects.filter(is_active=True)
    else:
        projects = Project.objects.all()

    paginator = Paginator(projects, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'can_create': role in ['MANAGER', 'ADMIN'],
    }
    return render(request, 'projects/project_list.html', context)


@login_required
def project_create(request):
    """Create a new project (managers and admins only)"""
    role = get_user_role(request.user)
    if role not in ['MANAGER', 'ADMIN']:
        messages.error(request, 'You do not have permission to create projects.')
        return redirect('project_list')

    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.save()
            messages.success(request, 'Project created successfully.')
            return redirect('project_detail', pk=project.pk)
    else:
        form = ProjectForm()

    return render(request, 'projects/project_create.html', {'form': form})


@login_required
def project_detail(request, pk):
    """View project details"""
    project = get_object_or_404(Project, pk=pk)
    entries = project.time_entries.all().order_by('-date', '-created_at')

    # Calculate statistics
    total_hours = project.total_hours
    approved_hours = project.total_hours_approved

    context = {
        'project': project,
        'entries': entries,
        'total_hours': total_hours,
        'approved_hours': approved_hours,
        'can_edit': is_manager_or_admin(request.user),
    }
    return render(request, 'projects/project_detail.html', context)


@login_required
def project_update(request, pk):
    """Update a project (managers and admins only)"""
    role = get_user_role(request.user)
    if role not in ['MANAGER', 'ADMIN']:
        messages.error(request, 'You do not have permission to edit projects.')
        return redirect('project_list')

    project = get_object_or_404(Project, pk=pk)

    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, 'Project updated successfully.')
            return redirect('project_detail', pk=project.pk)
    else:
        form = ProjectForm(instance=project)

    return render(request, 'projects/project_create.html', {'form': form, 'project': project})


@login_required
def project_delete(request, pk):
    """Delete a project (admins only)"""
    if not is_admin(request.user):
        messages.error(request, 'Only admins can delete projects.')
        return redirect('project_list')

    project = get_object_or_404(Project, pk=pk)

    if request.method == 'POST':
        project.delete()
        messages.success(request, 'Project deleted successfully.')
        return redirect('project_list')

    return render(request, 'projects/project_delete.html', {'project': project})


# ============== Time Entry Views ==============

@login_required
def timesheet_list(request):
    """List time entries"""
    role = get_user_role(request.user)

    # Base queryset
    if role == 'WORKER':
        entries = TimeEntry.objects.filter(user=request.user)
    else:
        entries = TimeEntry.objects.all()

    # Apply filters
    status_filter = request.GET.get('status')
    project_filter = request.GET.get('project')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if status_filter:
        entries = entries.filter(status=status_filter)
    if project_filter:
        entries = entries.filter(project_id=project_filter)
    if date_from:
        entries = entries.filter(date__gte=date_from)
    if date_to:
        entries = entries.filter(date__lte=date_to)

    entries = entries.order_by('-date', '-created_at')

    # Get filter options
    projects = Project.objects.filter(is_active=True)

    paginator = Paginator(entries, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'projects': projects,
        'status_filter': status_filter,
        'project_filter': project_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'timesheets/timesheet_list.html', context)


@login_required
def timesheet_create(request):
    """Create a new time entry"""
    if request.method == 'POST':
        form = TimeEntryForm(request.POST, user=request.user)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.entry_type = 'MANUAL'
            entry.save()
            messages.success(request, 'Time entry created successfully.')
            return redirect('timesheet_list')
    else:
        form = TimeEntryForm(user=request.user)

    return render(request, 'timesheets/timesheet_create.html', {'form': form})


@login_required
def timesheet_detail(request, pk):
    """View time entry details"""
    entry = get_object_or_404(TimeEntry, pk=pk)

    # Check permissions
    role = get_user_role(request.user)
    if role == 'WORKER' and entry.user != request.user:
        messages.error(request, 'You can only view your own time entries.')
        return redirect('timesheet_list')

    context = {
        'entry': entry,
        'can_edit': role == 'ADMIN' or entry.user == request.user,
        'can_approve': role in ['MANAGER', 'ADMIN'],
    }
    return render(request, 'timesheets/timesheet_detail.html', context)


@login_required
def timesheet_update(request, pk):
    """Update a time entry"""
    entry = get_object_or_404(TimeEntry, pk=pk)
    role = get_user_role(request.user)

    # Check permissions
    if role == 'WORKER' and entry.user != request.user:
        messages.error(request, 'You can only edit your own time entries.')
        return redirect('timesheet_list')

    if entry.status == 'APPROVED' and not is_admin(request.user):
        messages.error(request, 'Cannot edit approved entries.')
        return redirect('timesheet_detail', pk=pk)

    if request.method == 'POST':
        form = TimeEntryForm(request.POST, instance=entry, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Time entry updated successfully.')
            return redirect('timesheet_detail', pk=pk)
    else:
        form = TimeEntryForm(instance=entry, user=request.user)

    return render(request, 'timesheets/timesheet_create.html', {'form': form, 'entry': entry})


@login_required
def timesheet_delete(request, pk):
    """Delete a time entry"""
    entry = get_object_or_404(TimeEntry, pk=pk)
    role = get_user_role(request.user)

    # Check permissions
    if role == 'WORKER' and entry.user != request.user:
        messages.error(request, 'You can only delete your own time entries.')
        return redirect('timesheet_list')

    if entry.status == 'APPROVED' and not is_admin(request.user):
        messages.error(request, 'Cannot delete approved entries.')
        return redirect('timesheet_detail', pk=pk)

    if request.method == 'POST':
        entry.delete()
        messages.success(request, 'Time entry deleted successfully.')
        return redirect('timesheet_list')

    return render(request, 'timesheets/timesheet_delete.html', {'entry': entry})


# ============== Timer Views ==============

@login_required
def timer_start(request):
    """Start a new timer session"""
    if request.method == 'POST':
        form = TimerStartForm(request.POST)
        if form.is_valid():
            # Check if user already has a running timer
            existing_timer = TimerSession.objects.filter(
                user=request.user,
                is_running=True
            ).first()

            if existing_timer:
                messages.error(request, 'You already have a running timer. Please stop it first.')
                return redirect('dashboard')

            timer = form.save(commit=False)
            timer.user = request.user
            timer.save()
            messages.success(request, 'Timer started successfully.')
            return redirect('dashboard')
    else:
        form = TimerStartForm()

    return render(request, 'timesheets/timer_start.html', {'form': form})


@login_required
def timer_stop(request, pk):
    """Stop a running timer and create a time entry"""
    timer = get_object_or_404(TimerSession, pk=pk, user=request.user)

    if not timer.is_running:
        messages.error(request, 'This timer is already stopped.')
        return redirect('dashboard')

    if request.method == 'POST':
        # Calculate duration
        end_time = timezone.now()
        duration_minutes = timer.duration_minutes

        # Create time entry
        entry = TimeEntry.objects.create(
            user=request.user,
            project=timer.project,
            date=timer.start_time.date(),
            duration_minutes=duration_minutes,
            description=timer.description or f"Timer session: {timer.start_time.strftime('%Y-%m-%d %H:%M')}",
            entry_type='TIMER',
            start_time=timer.start_time,
            end_time=end_time,
            status='PENDING'
        )

        # Stop the timer
        timer.is_running = False
        timer.save()

        messages.success(request, f'Timer stopped. Time entry created for {duration_minutes} minutes.')
        return redirect('timesheet_detail', pk=entry.pk)

    return render(request, 'timesheets/timer_stop.html', {'timer': timer})


@login_required
def timer_status(request):
    """API endpoint to check timer status"""
    timer = TimerSession.objects.filter(
        user=request.user,
        is_running=True
    ).first()

    if timer:
        data = {
            'is_running': True,
            'timer_id': timer.pk,
            'project': timer.project.name,
            'description': timer.description,
            'start_time': timer.start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'elapsed_minutes': timer.duration_minutes,
            'elapsed_time': timer.elapsed_time,
        }
    else:
        data = {
            'is_running': False,
        }

    return JsonResponse(data)


# ============== Approval Views ==============

@login_required
def approval_list(request):
    """List pending approvals for managers/admins"""
    role = get_user_role(request.user)

    if role not in ['MANAGER', 'ADMIN']:
        messages.error(request, 'You do not have permission to view approvals.')
        return redirect('dashboard')

    entries = TimeEntry.objects.filter(status='PENDING').order_by('-date', '-created_at')

    paginator = Paginator(entries, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
    }
    return render(request, 'approvals/approval_list.html', context)


@login_required
def approve_entry(request, pk):
    """Approve a time entry"""
    role = get_user_role(request.user)

    if role not in ['MANAGER', 'ADMIN']:
        messages.error(request, 'You do not have permission to approve entries.')
        return redirect('dashboard')

    entry = get_object_or_404(TimeEntry, pk=pk)

    if entry.status != 'PENDING':
        messages.warning(request, 'This entry has already been processed.')
        return redirect('approval_list')

    if request.method == 'POST':
        entry.status = 'APPROVED'
        entry.approved_by = request.user
        entry.approved_at = timezone.now()
        entry.save()
        messages.success(request, 'Time entry approved successfully.')
        return redirect('approval_list')

    return render(request, 'approvals/approve_entry.html', {'entry': entry})


@login_required
def reject_entry(request, pk):
    """Reject a time entry"""
    role = get_user_role(request.user)

    if role not in ['MANAGER', 'ADMIN']:
        messages.error(request, 'You do not have permission to reject entries.')
        return redirect('dashboard')

    entry = get_object_or_404(TimeEntry, pk=pk)

    if entry.status != 'PENDING':
        messages.warning(request, 'This entry has already been processed.')
        return redirect('approval_list')

    if request.method == 'POST':
        entry.status = 'REJECTED'
        entry.approved_by = request.user
        entry.approved_at = timezone.now()
        entry.rejection_reason = request.POST.get('reason', '')
        entry.save()
        messages.success(request, 'Time entry rejected successfully.')
        return redirect('approval_list')

    return render(request, 'approvals/reject_entry.html', {'entry': entry})


# ============== Report Views ==============

@login_required
def report_summary(request):
    """Summary report view"""
    role = get_user_role(request.user)

    # Get filters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    project_filter = request.GET.get('project')
    user_filter = request.GET.get('user')

    # Base queryset
    if role == 'WORKER':
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
    if user_filter and role != 'WORKER':
        entries = entries.filter(user_id=user_filter)

    # Calculate statistics
    total_entries = entries.count()
    total_hours = sum(entry.duration_hours for entry in entries)

    # Group by project
    project_stats = entries.values('project__name').annotate(
        total_hours=Sum('duration_minutes') / 60,
        entry_count=Count('id')
    ).order_by('-total_hours')

    # Group by user (for managers/admins)
    if role != 'WORKER':
        user_stats = entries.values('user__username', 'user__profile__role').annotate(
            total_hours=Sum('duration_minutes') / 60,
            entry_count=Count('id')
        ).order_by('-total_hours')
    else:
        user_stats = []

    # Group by status
    status_stats = entries.values('status').annotate(
        total_hours=Sum('duration_minutes') / 60,
        entry_count=Count('id')
    ).order_by('-total_hours')

    # Get filter options
    projects = Project.objects.filter(is_active=True)
    users = User.objects.all() if role != 'WORKER' else []

    context = {
        'total_entries': total_entries,
        'total_hours': round(total_hours, 2),
        'project_stats': project_stats,
        'user_stats': user_stats,
        'status_stats': status_stats,
        'projects': projects,
        'users': users,
        'date_from': date_from,
        'date_to': date_to,
        'project_filter': project_filter,
        'user_filter': user_filter,
    }
    return render(request, 'reports/report_summary.html', context)


@login_required
def report_detail(request):
    """Detailed report with all time entries"""
    role = get_user_role(request.user)

    # Get filters
    form = ReportFilterForm(request.GET or None)

    # Base queryset
    if role == 'WORKER':
        entries = TimeEntry.objects.filter(user=request.user)
    else:
        entries = TimeEntry.objects.all()

    # Apply filters
    if form.is_valid():
        if form.cleaned_data.get('date_from'):
            entries = entries.filter(date__gte=form.cleaned_data['date_from'])
        if form.cleaned_data.get('date_to'):
            entries = entries.filter(date__lte=form.cleaned_data['date_to'])
        if form.cleaned_data.get('project'):
            entries = entries.filter(project=form.cleaned_data['project'])
        if form.cleaned_data.get('user') and role != 'WORKER':
            entries = entries.filter(user=form.cleaned_data['user'])
        if form.cleaned_data.get('status'):
            entries = entries.filter(status=form.cleaned_data['status'])

    entries = entries.order_by('-date', '-created_at')

    paginator = Paginator(entries, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'form': form,
    }
    return render(request, 'reports/report_detail.html', context)


@login_required
def report_export(request):
    """Export report to CSV"""
    import csv
    from django.http import HttpResponse

    role = get_user_role(request.user)

    # Get filters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    project_filter = request.GET.get('project')
    user_filter = request.GET.get('user')

    # Base queryset
    if role == 'WORKER':
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
    if user_filter and role != 'WORKER':
        entries = entries.filter(user_id=user_filter)

    entries = entries.order_by('-date')

    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="timesheet_report.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date', 'User', 'Project', 'Description', 'Duration (hours)', 'Status', 'Entry Type'])

    for entry in entries:
        writer.writerow([
            entry.date,
            entry.user.username,
            entry.project.name,
            entry.description,
            entry.duration_hours,
            entry.status,
            entry.entry_type,
        ])

    return response
