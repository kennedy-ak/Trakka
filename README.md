# Trakka

A Django-based timesheet management application designed to help teams track work hours, manage projects, and streamline time approval workflows.

## Features

### Core Functionality
- **Time Tracking**: Log work hours manually or use the built-in timer
- **Project Management**: Create and manage projects with team members
- **Approval Workflow**: Managers and admins can approve or reject time entries
- **User Roles**: Three-tier role system (Worker, Manager, Admin)
- **Reporting**: Generate detailed reports and summaries
- **Real-time Timer**: Start/stop timer for accurate time tracking

### Key Features by Role

| Role | Capabilities |
|------|--------------|
| **Worker** | Log time entries, start/stop timer, view own entries |
| **Manager** | Approve/reject entries, view team reports, manage projects |
| **Admin** | Full system access, user management, system settings |

## Tech Stack

- **Backend**: Django 6.0.1
- **Python**: 3.12+
- **Database**: SQLite (default)
- **Package Manager**: uv
- **Additional Libraries**:
  - django-extensions (4.1+)
  - django-widget-tweaks (1.5.1+)
  - python-decouple (3.8+)

## Installation

### Prerequisites
- Python 3.12 or higher
- uv package manager

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Trakka
   ```

2. **Install dependencies using uv**
   ```bash
   uv sync
   ```

3. **Run database migrations**
   ```bash
   python manage.py migrate
   ```

4. **Create a superuser (admin account)**
   ```bash
   python manage.py createsuperuser
   ```

5. **Start the development server**
   ```bash
   python manage.py runserver
   ```

6. **Access the application**
   - Main application: http://127.0.0.1:8000/
   - Django Admin: http://127.0.0.1:8000/admin/
   - Management Panel: http://127.0.0.1:8000/management/

## Usage

### Initial Setup

1. **Create test users** (optional):
   ```bash
   python manage.py create_test_users
   ```

2. **Log in** with your credentials at the login page

3. **Create a project** to start tracking time

### Time Tracking

**Manual Entry:**
1. Navigate to the dashboard
2. Click "Create Entry" under Timesheets
3. Fill in the project, date, duration, and description
4. Submit for approval

**Timer Mode:**
1. Select a project from the dashboard
2. Click "Start Timer"
3. Work on your task
4. Click "Stop Timer" when done
5. Add a description and submit

### Approval Process

1. Navigate to the Approvals section
2. Review pending time entries
3. Approve or reject entries with optional comments

### Reports

1. Access the Reports section
2. View summaries and detailed reports
3. Export reports for analysis

## Project Structure

```
Trakka/
├── adminpanel/              # Admin panel app
│   ├── migrations/          # Database migrations
│   ├── templates/           # Admin templates
│   ├── admin.py             # Admin configuration
│   ├── models.py            # Admin models
│   ├── urls.py              # URL routing
│   └── views.py             # View functions
├── timesheet/               # Timesheet app
│   ├── management/          # Management commands
│   ├── migrations/          # Database migrations
│   ├── static/              # Static files
│   ├── templates/           # Timesheet templates
│   ├── forms.py             # Form definitions
│   ├── models.py            # Data models
│   ├── urls.py              # URL routing
│   └── views.py             # View functions
├── templates/               # Global templates
│   ├── auth/                # Authentication templates
│   ├── approvals/           # Approval templates
│   ├── projects/            # Project templates
│   ├── reports/             # Report templates
│   └── timesheets/          # Timesheet templates
├── trakka_project/          # Project configuration
│   ├── settings.py          # Django settings
│   ├── urls.py              # Root URL configuration
│   └── wsgi.py              # WSGI configuration
├── manage.py                # Django management script
├── pyproject.toml           # Project dependencies
└── README.md                # This file
```

## Data Models

### UserProfile
Extends Django's User model with role and department information.

### Project
Represents a work project with members and budget tracking.

### TimeEntry
Tracks individual time entries with approval status and entry type (manual/timer).

### TimerSession
Manages active timer sessions for real-time tracking.

## Development

### Running Tests
```bash
python manage.py test
```

### Creating Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Django Shell
```bash
python manage.py shell
```

## Configuration

### Environment Variables
The application uses `python-decouple` for configuration. Key settings can be configured in [`trakka_project/settings.py`](trakka_project/settings.py):

- `SECRET_KEY`: Django secret key (change in production)
- `DEBUG`: Enable/disable debug mode
- `ALLOWED_HOSTS`: Allowed hosts for the application
- `DATABASES`: Database configuration
- `TIME_ZONE`: Application timezone (default: UTC)

### Static Files
Collect static files for production:
```bash
python manage.py collectstatic
```

## URL Structure

| Path | Description |
|------|-------------|
| `/` | Main dashboard |
| `/login/` | User login |
| `/logout/` | User logout |
| `/projects/` | Project list |
| `/entries/` | Time entries list |
| `/timer/` | Timer controls |
| `/approvals/` | Approval queue |
| `/reports/` | Reports and analytics |
| `/management/` | Admin panel |
| `/admin/` | Django admin |

## License

This project is provided as-is for educational and development purposes.

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write tests for new functionality
5. Submit a pull request

## Support

For issues, questions, or suggestions, please open an issue on the project repository.
