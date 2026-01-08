import pandas as pd
import pytest
from datetime import timedelta
from django.core.management import call_command
from django.utils import timezone

from va_explorer.va_data_management.models import ODKPullLock, ODKPullState
from va_explorer.va_data_management.odk.service import ODKPullLocked, ODKPullService


pytestmark = pytest.mark.django_db


def test_pull_form_updates_state_and_counts(monkeypatch):
    service = ODKPullService(default_project_id=1)
    last_seen = timezone.now() - timedelta(days=2)
    state = ODKPullState.objects.create(
        form_id="abc", project_id=1, last_submission_at=last_seen
    )

    calls = {}

    def fake_list_submissions(form_id, project_id, since=None, include_attachments=False):
        calls["since"] = since
        df = pd.DataFrame([{"createdAt": "2024-01-01T00:00:00Z"}])
        return df, timezone.now()

    def fake_upsert(df, form_name=None):
        return {"created": len(df)}

    monkeypatch.setattr(service, "list_submissions", fake_list_submissions)
    monkeypatch.setattr(service, "upsert_into_models", fake_upsert)

    summary = service.pull_form("abc", project_id=1, form_name="test")

    state.refresh_from_db()
    assert calls["since"] == last_seen
    assert state.last_run_status == ODKPullState.STATUS_SUCCESS
    assert summary["created"] == 1
    assert state.last_submission_at is not None


def test_lock_prevents_overlap():
    service = ODKPullService(default_project_id=1)
    ODKPullLock.objects.create(
        form_id="locked",
        project_id=1,
        expires_at=timezone.now() + timedelta(hours=1),
    )

    with pytest.raises(ODKPullLocked):
        service.pull_form("locked", project_id=1)


def test_management_command_delegates_to_service(monkeypatch):
    called = {}

    class FakeService(ODKPullService):
        def pull_forms(self, form_configs, **kwargs):
            called["configs"] = list(form_configs)
            called["kwargs"] = kwargs
            return {"abc": {"status": "SUCCESS", "created": 1}}

    monkeypatch.setattr(
        "va_explorer.va_data_management.management.commands.import_from_odk.ODKPullService",
        FakeService,
    )

    call_command("import_from_odk", "--form-id", "abc", "--full-refresh", "--dry-run")

    assert called["configs"][0]["form_id"] == "abc"
    assert called["kwargs"]["full_refresh"] is True
    assert called["kwargs"]["dry_run"] is True
