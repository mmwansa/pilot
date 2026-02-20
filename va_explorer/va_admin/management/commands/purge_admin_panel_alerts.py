from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from va_explorer.va_admin.models import AdminPanelAlert


class Command(BaseCommand):
    help = "Delete admin panel alerts older than retention window (default 30 days)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            dest="days",
            type=int,
            default=30,
            help="Retention window in days. Alerts older than this are deleted.",
        )
        parser.add_argument(
            "--dry-run",
            dest="dry_run",
            action="store_true",
            help="Show how many alerts would be deleted without deleting.",
        )

    def handle(self, *args, **options):
        days = max(int(options.get("days") or 30), 1)
        dry_run = bool(options.get("dry_run"))

        cutoff = timezone.now() - timedelta(days=days)
        queryset = AdminPanelAlert.objects.filter(created_at__lt=cutoff)
        count = queryset.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[dry-run] {count} alerts older than {days} days would be deleted."
                )
            )
            return

        deleted_count, _ = queryset.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted_count} admin panel alerts older than {days} days."
            )
        )
