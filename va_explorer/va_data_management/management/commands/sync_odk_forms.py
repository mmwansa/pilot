from django.core.management.base import BaseCommand

from va_explorer.va_data_management.tasks import sync_odk_forms


class Command(BaseCommand):
    help = "Synchronize ODK form definitions and submissions via pyODK."

    def handle(self, *args, **options):
        _ = args  # unused
        results = sync_odk_forms()
        if not results:
            self.stdout.write("No ODK submissions were imported.")
            return

        for form_name, count in sorted(results.items()):
            self.stdout.write(f"Imported {count} records for '{form_name}'")

        self.stdout.write(self.style.SUCCESS("pyODK synchronization complete."))
