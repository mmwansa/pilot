import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from va_explorer.tests.factories import AdminFactory, UserFactory
from va_explorer.users.models import Feedback

pytestmark = pytest.mark.django_db


def test_user_can_submit_feedback(client):
    user = UserFactory()
    client.force_login(user)
    response = client.post(
        reverse("users:feedback_submit"),
        data={
            "subject": "Broken page",
            "report_type": Feedback.ReportType.BUG,
            "module": Feedback.Module.DATA_MANAGEMENT,
            "feature": Feedback.feature_choices_for(Feedback.Module.DATA_MANAGEMENT)[0][0],
            "severity": Feedback.Severity.HIGH,
            "description": "Steps to reproduce...",
        },
    )
    assert response.status_code == 302
    feedback = Feedback.objects.get()
    assert feedback.submitted_by == user
    assert feedback.status == Feedback.Status.NEW
    assert feedback.report_type == Feedback.ReportType.BUG
    assert feedback.metadata.get("operating_system") is not None
    assert feedback.metadata.get("timestamp") is not None


def test_non_admin_cannot_access_feedback_mailbox(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get(reverse("users:feedback_mailbox"))
    assert response.status_code == 403


def test_admin_can_view_feedback_mailbox_and_detail(client):
    admin = AdminFactory()
    feedback = Feedback.objects.create(
        subject="Issue",
        module=Feedback.Module.SCHEDULE_MANAGEMENT,
        feature="scheduled_vas",
        severity=Feedback.Severity.MEDIUM,
        description="Details",
    )
    client.force_login(admin)
    list_response = client.get(reverse("users:feedback_mailbox"))
    assert list_response.status_code == 200
    assert feedback.subject in list_response.content.decode()

    detail_response = client.get(
        reverse("users:feedback_detail", args=[feedback.pk])
    )
    assert detail_response.status_code == 200
    assert "Issue" in detail_response.content.decode()


def test_admin_can_update_feedback_status(client):
    admin = AdminFactory()
    feedback = Feedback.objects.create(
        subject="Bug",
        module=Feedback.Module.ANALYTICS,
        feature="dashboards",
        severity=Feedback.Severity.CRITICAL,
        description="Dashboard crash",
    )
    client.force_login(admin)
    response = client.post(
        reverse("users:feedback_detail", args=[feedback.pk]),
        data={"status": Feedback.Status.RESOLVED},
    )
    assert response.status_code == 302
    feedback.refresh_from_db()
    assert feedback.status == Feedback.Status.RESOLVED


def test_feedback_attachment_and_filename(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    user = UserFactory(username="reporter")
    client.force_login(user)
    uploaded = SimpleUploadedFile(
        "screenshot.png", b"fake image bytes", content_type="image/png"
    )
    response = client.post(
        reverse("users:feedback_submit"),
        data={
            "subject": "Attachment test",
            "report_type": Feedback.ReportType.FEATURE,
            "module": Feedback.Module.DATA_MANAGEMENT,
            "feature": Feedback.feature_choices_for(Feedback.Module.DATA_MANAGEMENT)[0][0],
            "severity": Feedback.Severity.MEDIUM,
            "description": "With attachment",
            "attachment": uploaded,
        },
    )
    assert response.status_code == 302
    feedback = Feedback.objects.get()
    assert feedback.attachment.name.startswith("feedback/")
    filename = feedback.attachment.name.split("/")[-1]
    assert "data_management" in filename
    assert "medium" in filename
    assert "reporter" in filename
