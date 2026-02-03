from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.core.paginator import Paginator
from django.utils import timezone
from timesheet.models import UserProfile, Project, TimeEntry
from timesheet.forms import UserRegistrationForm, UserProfileForm


# Helper Functions
def get_user_role(user):
    """Get the user's role from UserProfile"""
    if hasattr(user, 'profile'):
        return user.profile.role
    return 'WORKER'


def is_admin(user):
    """Check if user is admin"""
    return get_user_role(user) == 'ADMIN'


# ============== Dashboard Views ==============

@login_required
def admin_dashboard(request):
    """Main admin dashboard - only accessible by ADMIN role"""
    if not is_admin(request.user):
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard')

    # Get statistics
    total_users = User.objects.filter(is_active=True).count()
    total_projects = Project.objects.count()
    total_entries = TimeEntry.objects.count()
    pending_approvals = TimeEntry.objects.filter(status='PENDING').count()

    # User counts by role
    workers_count = UserProfile.objects.filter(role='WORKER').count()
    managers_count = UserProfile.objects.filter(role='MANAGER').count()
    admins_count = UserProfile.objects.filter(role='ADMIN').count()

    # Recent activity
    recent_users = User.objects.select_related('profile').order_by('-date_joined')[:5]
    recent_projects = Project.objects.prefetch_related('members').order_by('-created_at')[:5]

    # Project statistics
    active_projects = Project.objects.filter(is_active=True).count()
    total_budget_hours = Project.objects.aggregate(Sum('budget_hours'))['budget_hours__sum'] or 0

    # Get recent pending approvals
    pending_entries = TimeEntry.objects.filter(
        status='PENDING'
    ).select_related('user', 'project').order_by('-date', '-created_at')[:5]

    context = {
        'total_users': total_users,
        'total_projects': total_projects,
        'total_entries': total_entries,
        'pending_approvals': pending_approvals,
        'workers_count': workers_count,
        'managers_count': managers_count,
        'admins_count': admins_count,
        'recent_users': recent_users,
        'recent_projects': recent_projects,
        'active_projects': active_projects,
        'total_budget_hours': total_budget_hours,
        'pending_entries': pending_entries,
    }
    return render(request, 'adminpanel/dashboard.html', context)


# ============== User Management Views ==============

@login_required
def user_list(request):
    """List all users - admin only"""
    if not is_admin(request.user):
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard')

    users = User.objects.select_related('profile').all()
    query = request.GET.get('q')
    role_filter = request.GET.get('role')

    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )

    if role_filter:
        users = users.filter(profile__role=role_filter)

    # Order by username
    users = users.order_by('username')

    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
        'role_filter': role_filter,
    }
    return render(request, 'adminpanel/user_list.html', context)


@login_required
def user_create(request):
    """Create a new user - admin only"""
    if not is_admin(request.user):
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()

            # Create profile with role
            UserProfile.objects.create(
                user=user,
                role=form.cleaned_data['role'],
                department=form.cleaned_data['department']
            )

            messages.success(request, f'User {user.username} created successfully.')
            return redirect('adminpanel:user_list')
    else:
        form = UserRegistrationForm()

    return render(request, 'adminpanel/user_create.html', {'form': form})


@login_required
def user_detail(request, user_id):
    """View user details - admin only"""
    if not is_admin(request.user):
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard')

    user = get_object_or_404(User.objects.select_related('profile'), id=user_id)

    # Get user statistics
    total_entries = user.time_entries.count()
    total_hours = sum(entry.duration_hours for entry in user.time_entries.all())
    approved_entries = user.time_entries.filter(status='APPROVED').count()
    pending_entries = user.time_entries.filter(status='PENDING').count()
    projects = user.projects.all()

    # Get recent time entries
    recent_entries = user.time_entries.select_related('project').order_by('-date', '-created_at')[:10]

    context = {
        'target_user': user,
        'total_entries': total_entries,
        'total_hours': round(total_hours, 2),
        'approved_entries': approved_entries,
        'pending_entries': pending_entries,
        'projects': projects,
        'recent_entries': recent_entries,
    }
    return render(request, 'adminpanel/user_detail.html', context)


@login_required
def user_edit(request, user_id):
    """Edit user profile - admin only"""
    if not is_admin(request.user):
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard')

    user = get_object_or_404(User, id=user_id)
    profile = get_object_or_404(UserProfile, user=user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, f'User {user.username} updated successfully.')
            return redirect('adminpanel:user_detail', user_id=user.id)
    else:
        form = UserProfileForm(instance=profile)

    context = {
        'form': form,
        'target_user': user,
    }
    return render(request, 'adminpanel/user_edit.html', context)


@login_required
def user_delete(request, user_id):
    """Delete/deactivate user - admin only"""
    if not is_admin(request.user):
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard')

    user = get_object_or_404(User, id=user_id)

    # Prevent deleting yourself
    if user == request.user:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('adminpanel:user_list')

    if request.method == 'POST':
        # Deactivate instead of deleting
        user.is_active = False
        user.save()
        messages.success(request, f'User {user.username} has been deactivated.')
        return redirect('adminpanel:user_list')

    context = {
        'target_user': user,
    }
    return render(request, 'adminpanel/user_delete.html', context)


@login_required
def user_activate(request, user_id):
    """Activate a deactivated user - admin only"""
    if not is_admin(request.user):
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard')

    user = get_object_or_404(User, id=user_id)
    user.is_active = True
    user.save()

    messages.success(request, f'User {user.username} has been activated.')
    return redirect('adminpanel:user_list')


# ============== Project Management Views ==============

@login_required
def project_list_admin(request):
    """List all projects with admin controls - admin only"""
    if not is_admin(request.user):
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard')

    projects = Project.objects.prefetch_related('members').all()
    query = request.GET.get('q')

    if query:
        projects = projects.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )

    paginator = Paginator(projects, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
    }
    return render(request, 'adminpanel/project_list.html', context)


@login_required
def project_members_manage(request, project_id):
    """Manage project members - admin only"""
    if not is_admin(request.user):
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard')

    project = get_object_or_404(Project.objects.prefetch_related('members'), id=project_id)

    if request.method == 'POST':
        member_ids = request.POST.getlist('members')
        project.members.set(member_ids)
        messages.success(request, f'Project members updated for {project.name}.')
        return redirect('adminpanel:project_members', project_id=project.id)

    # Get all active users
    all_users = User.objects.filter(is_active=True).select_related('profile').order_by('username')

    context = {
        'project': project,
        'all_users': all_users,
    }
    return render(request, 'adminpanel/project_members.html', context)


# ============== Reports & Analytics Views ==============

@login_required
def reports_overview(request):
    """Admin reports overview - admin only"""
    if not is_admin(request.user):
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard')

    from datetime import timedelta

    # Get time period
    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)

    # Entry statistics
    total_entries = TimeEntry.objects.count()
    recent_entries = TimeEntry.objects.filter(date__gte=thirty_days_ago).count()

    # Status breakdown
    status_breakdown = TimeEntry.objects.values('status').annotate(
        count=Count('id'),
        hours=Sum('duration_minutes') / 60
    ).order_by('-count')

    # Top projects by hours
    top_projects = Project.objects.annotate(
        total_hours=Sum('time_entries__duration_minutes') / 60,
        entry_count=Count('time_entries')
    ).order_by('-total_hours')[:10]

    # Top users by hours
    top_users = User.objects.annotate(
        total_hours=Sum('time_entries__duration_minutes') / 60,
        entry_count=Count('time_entries')
    ).filter(total_hours__isnull=False).order_by('-total_hours')[:10]

    # Entry type breakdown
    entry_type_breakdown = TimeEntry.objects.values('entry_type').annotate(
        count=Count('id'),
        hours=Sum('duration_minutes') / 60
    )

    context = {
        'total_entries': total_entries,
        'recent_entries': recent_entries,
        'status_breakdown': status_breakdown,
        'top_projects': top_projects,
        'top_users': top_users,
        'entry_type_breakdown': entry_type_breakdown,
    }
    return render(request, 'adminpanel/reports.html', context)


# ============== System Settings Views ==============

@login_required
def system_settings(request):
    """System settings - admin only"""
    if not is_admin(request.user):
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard')

    # System information
    from django.conf import settings

    context = {
        'debug_mode': settings.DEBUG,
        'db_engine': settings.DATABASES['default']['ENGINE'],
        'secret_key_preview': settings.SECRET_KEY[:10] + '...',
    }
    return render(request, 'adminpanel/settings.html', context)
