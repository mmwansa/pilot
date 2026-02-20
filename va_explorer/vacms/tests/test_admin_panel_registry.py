import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from va_explorer.va_admin.command_registry import ALLOWLIST
from va_explorer.va_admin.command_registry import data_dir


class AdminPanelRegistryTests(TestCase):
    def test_registry_has_explicit_allowlist(self):
        self.assertIn("load_household_csv", ALLOWLIST)
        self.assertIn("bulk_load_users", ALLOWLIST)

    def test_execute_endpoint_rejects_unregistered_command(self):
        admin = get_user_model().objects.create_user(
            email="admin-registry@example.com",
            password="StrongPass1!",
            name="Registry Admin",
            is_superuser=True,
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse("va_admin:run"),
            data=json.dumps({"command_id": "definitely_not_allowlisted", "inputs": {}}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("allowlisted", response.content.decode("utf-8"))

    def test_non_admin_cannot_access_admin_panel_page(self):
        user = get_user_model().objects.create_user(
            email="nonadmin@example.com",
            password="StrongPass1!",
            name="Regular User",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("va_admin:index"))
        self.assertEqual(response.status_code, 403)

    def test_non_admin_cannot_run_endpoint(self):
        user = get_user_model().objects.create_user(
            email="nonadmin-run@example.com",
            password="StrongPass1!",
            name="Regular User",
        )
        self.client.force_login(user)
        response = self.client.post(
            reverse("va_admin:run"),
            data=json.dumps({"command_id": "load_death_csv", "inputs": {"csv_file": "E_DEATH.csv"}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_path_traversal_filename_rejected(self):
        admin = get_user_model().objects.create_user(
            email="admin-traversal@example.com",
            password="StrongPass1!",
            name="Registry Admin",
            is_superuser=True,
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse("va_admin:run"),
            data=json.dumps({"command_id": "load_death_csv", "inputs": {"csv_file": "../etc/passwd"}}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid filename", response.content.decode("utf-8"))

    def test_missing_file_rejected_with_clear_message(self):
        admin = get_user_model().objects.create_user(
            email="admin-missing-file@example.com",
            password="StrongPass1!",
            name="Registry Admin",
            is_superuser=True,
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse("va_admin:run"),
            data=json.dumps({"command_id": "load_death_csv", "inputs": {"csv_file": "does_not_exist.csv"}}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("File not found in static/data", response.content.decode("utf-8"))

    def test_csrf_is_enforced_on_run_endpoint(self):
        admin = get_user_model().objects.create_user(
            email="admin-csrf@example.com",
            password="StrongPass1!",
            name="Registry Admin",
            is_superuser=True,
        )
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(admin)

        no_token_response = csrf_client.post(
            reverse("va_admin:run"),
            data=json.dumps({"command_id": "definitely_not_allowlisted", "inputs": {}}),
            content_type="application/json",
        )
        self.assertEqual(no_token_response.status_code, 403)

        panel_response = csrf_client.get(reverse("va_admin:index"))
        self.assertEqual(panel_response.status_code, 200)
        csrf_token = panel_response.cookies.get("csrftoken").value

        with_token_response = csrf_client.post(
            reverse("va_admin:run"),
            data=json.dumps({"command_id": "definitely_not_allowlisted", "inputs": {}}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(with_token_response.status_code, 400)
        self.assertIn("allowlisted", with_token_response.content.decode("utf-8"))

    def test_non_admin_cannot_upload_file(self):
        user = get_user_model().objects.create_user(
            email="nonadmin-upload@example.com",
            password="StrongPass1!",
            name="Regular User",
        )
        self.client.force_login(user)

        upload = SimpleUploadedFile("demo.csv", b"col\n1\n", content_type="text/csv")
        response = self.client.post(
            reverse("va_admin:upload-file"),
            data={"file": upload, "filename": "demo.csv"},
        )
        self.assertEqual(response.status_code, 403)

    def test_upload_rejects_path_traversal_filename(self):
        admin = get_user_model().objects.create_user(
            email="admin-upload@example.com",
            password="StrongPass1!",
            name="Registry Admin",
            is_superuser=True,
        )
        self.client.force_login(admin)

        upload = SimpleUploadedFile("demo.csv", b"col\n1\n", content_type="text/csv")
        response = self.client.post(
            reverse("va_admin:upload-file"),
            data={"file": upload, "filename": "../demo.csv"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid filename", response.content.decode("utf-8"))

    def test_upload_overwrites_existing_file_by_default(self):
        admin = get_user_model().objects.create_user(
            email="admin-upload-default-overwrite@example.com",
            password="StrongPass1!",
            name="Registry Admin",
            is_superuser=True,
        )
        self.client.force_login(admin)

        filename = "test_default_overwrite.csv"
        target = data_dir() / filename
        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            first = SimpleUploadedFile(filename, b"col\n1\n", content_type="text/csv")
            response_one = self.client.post(
                reverse("va_admin:upload-file"),
                data={"file": first, "filename": filename},
            )
            self.assertEqual(response_one.status_code, 200)
            self.assertTrue(target.exists())

            second = SimpleUploadedFile(filename, b"col\n2\n", content_type="text/csv")
            response_two = self.client.post(
                reverse("va_admin:upload-file"),
                data={"file": second, "filename": filename},
            )
            self.assertEqual(response_two.status_code, 200)
            self.assertEqual(target.read_bytes(), b"col\n2\n")
        finally:
            if target.exists():
                target.unlink()
