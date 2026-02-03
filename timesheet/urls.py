from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Authentication
    path('login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Projects
    path('projects/', views.project_list, name='project_list'),
    path('projects/create/', views.project_create, name='project_create'),
    path('projects/<int:pk>/', views.project_detail, name='project_detail'),
    path('projects/<int:pk>/update/', views.project_update, name='project_update'),
    path('projects/<int:pk>/delete/', views.project_delete, name='project_delete'),

    # Time Entries
    path('entries/', views.timesheet_list, name='timesheet_list'),
    path('entries/create/', views.timesheet_create, name='timesheet_create'),
    path('entries/<int:pk>/', views.timesheet_detail, name='timesheet_detail'),
    path('entries/<int:pk>/update/', views.timesheet_update, name='timesheet_update'),
    path('entries/<int:pk>/delete/', views.timesheet_delete, name='timesheet_delete'),

    # Timer
    path('timer/start/', views.timer_start, name='timer_start'),
    path('timer/stop/<int:pk>/', views.timer_stop, name='timer_stop'),
    path('timer/status/', views.timer_status, name='timer_status'),

    # Approvals
    path('approvals/', views.approval_list, name='approval_list'),
    path('approvals/<int:pk>/approve/', views.approve_entry, name='approve_entry'),
    path('approvals/<int:pk>/reject/', views.reject_entry, name='reject_entry'),

    # Reports
    path('reports/', views.report_summary, name='report_summary'),
    path('reports/detail/', views.report_detail, name='report_detail'),
    path('reports/export/', views.report_export, name='report_export'),
]
