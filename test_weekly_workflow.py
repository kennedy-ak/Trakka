"""
Test script for weekly timesheet workflow
Run with: python manage.py shell < test_weekly_workflow.py
"""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "trakka_project.settings")
django.setup()

from timesheet.models import TimeEntry, WeeklyTimesheet  # noqa: E402

print("\n" + "=" * 60)
print("WEEKLY TIMESHEET WORKFLOW TEST")
print("=" * 60)

# 1. Check existing weekly timesheets
print("\n1. Checking existing weekly timesheets...")
weekly_timesheets = WeeklyTimesheet.objects.all()
print(f"   Total weekly timesheets: {weekly_timesheets.count()}")
for wt in weekly_timesheets[:5]:
    print(
        f"   - {wt.user.username}: Week of {wt.week_start_date} "
        f"({wt.status}) - {wt.entry_count} entries, {wt.total_hours}h"
    )

# 2. Check time entries linked to weekly timesheets
print("\n2. Checking time entries linked to weekly timesheets...")
linked_entries = TimeEntry.objects.filter(weekly_timesheet__isnull=False).count()
total_entries = TimeEntry.objects.count()
print(f"   Linked entries: {linked_entries}/{total_entries}")

# 3. Check weekly timesheet statuses
print("\n3. Weekly timesheet status breakdown...")
statuses = WeeklyTimesheet.objects.values_list("status", flat=True).distinct()
for status in statuses:
    count = WeeklyTimesheet.objects.filter(status=status).count()
    print(f"   {status}: {count}")

# 4. Verify business rules
print("\n4. Verifying business rules...")

# Get a draft weekly timesheet
draft_weeks = WeeklyTimesheet.objects.filter(status="DRAFT")
if draft_weeks.exists():
    draft_week = draft_weeks.first()
    print(
        f"   ✓ Draft week found: {draft_week.user.username} - "
        f"Week of {draft_week.week_start_date}"
    )
    print(f"     Entries: {draft_week.entry_count}, Hours: {draft_week.total_hours}")

    # Check if entries can be added to this week
    if draft_week.status in ["DRAFT", "REJECTED"]:
        print(f"     ✓ Can add entries to this week (status: {draft_week.status})")
    else:
        print(
            f"     ✗ Cannot add entries to this week " f"(status: {draft_week.status})"
        )
else:
    print("   ! No draft weeks found")

# 5. Check submitted weeks
print("\n5. Checking submitted weeks (pending approval)...")
submitted_weeks = WeeklyTimesheet.objects.filter(status="SUBMITTED")
print(f"   Submitted weeks: {submitted_weeks.count()}")
for wt in submitted_weeks[:3]:
    print(
        f"   - {wt.user.username}: Week of {wt.week_start_date} - "
        f"{wt.entry_count} entries, {wt.total_hours}h"
    )

# 6. Check approved weeks
print("\n6. Checking approved weeks...")
approved_weeks = WeeklyTimesheet.objects.filter(status="APPROVED")
print(f"   Approved weeks: {approved_weeks.count()}")
for wt in approved_weeks[:3]:
    approved_by = wt.approved_by.username if wt.approved_by else "N/A"
    print(
        f"   - {wt.user.username}: Week of {wt.week_start_date} - "
        f"Approved by {approved_by}"
    )

# 7. Check rejected weeks
print("\n7. Checking rejected weeks...")
rejected_weeks = WeeklyTimesheet.objects.filter(status="REJECTED")
print(f"   Rejected weeks: {rejected_weeks.count()}")
for wt in rejected_weeks[:3]:
    print(f"   - {wt.user.username}: Week of {wt.week_start_date}")
    if wt.rejection_reason:
        print(f"     Reason: {wt.rejection_reason}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60 + "\n")

# Summary
print("SUMMARY:")
print(f"- Total weekly timesheets: {WeeklyTimesheet.objects.count()}")
print(f"- Total time entries: {TimeEntry.objects.count()}")
