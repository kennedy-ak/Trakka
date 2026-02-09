from django.urls import path

from . import views

app_name = "adminpanel"

urlpatterns = [
    # Dashboard
    path("", views.admin_dashboard, name="admin_dashboard"),
    # User Management
    path("users/", views.user_list, name="user_list"),
    path("users/create/", views.user_create, name="user_create"),
    path("users/<int:user_id>/", views.user_detail, name="user_detail"),
    path("users/<int:user_id>/edit/", views.user_edit, name="user_edit"),
    path("users/<int:user_id>/delete/", views.user_delete, name="user_delete"),
    path("users/<int:user_id>/activate/", views.user_activate, name="user_activate"),
    # Project Management
    path("projects/", views.project_list_admin, name="project_list"),
    path(
        "projects/<int:project_id>/members/",
        views.project_members_manage,
        name="project_members",
    ),
    # Reports & Analytics
    path("reports/", views.reports_overview, name="reports"),
    # System Settings
    path("settings/", views.system_settings, name="settings"),
]
