import logging
from contextlib import contextmanager
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from va_explorer.va_data_management.management.commands.load_form_csv import (
    FORM_MODEL_MAP,
)
from va_explorer.va_data_management.models import (
    ODKFormChoice,
    ODKPullLock,
    ODKPullState,
)
from va_explorer.va_data_management.utils.loading import (
    load_records_from_dataframe,
    normalize_dataframe_columns,
)
from va_explorer.va_data_management.utils.odk import make_pyodk_client


logger = logging.getLogger(__name__)

GLOBAL_LOCK = "__GLOBAL__"


class ODKPullLocked(Exception):
    """Raised when an ODK pull is already running."""


def load_definition_from_bytes(form_name: str, content: bytes) -> int:
    """Parse an XLSForm definition and populate ODKFormChoice."""
    survey = pd.read_excel(BytesIO(content), sheet_name="survey")
    choices = pd.read_excel(BytesIO(content), sheet_name="choices")
    label_col = None
    for col in choices.columns:
        if str(col).lower().startswith("label"):
            label_col = col
            break
    if label_col is None:
        return 0
    created = 0
    for _, srow in survey.iterrows():
        qtype = str(srow.get("type", ""))
        if not qtype.startswith("select_"):
            continue
        parts = qtype.split()
        if len(parts) < 2:
            continue
        list_name = parts[1]
        field = srow.get("name")
        if not field:
            continue
        sub = choices[choices["list_name"] == list_name]
        for _, crow in sub.iterrows():
            ODKFormChoice.objects.update_or_create(
                form_name=form_name,
                field_name=field,
                value=str(crow["name"]),
                defaults={"label": str(crow[label_col])},
            )
            created += 1
    return created


def import_dataframe_records(form_name: str, df: pd.DataFrame) -> int:
    """Map values using ODKFormChoice and save model records."""
    lookup: Dict[str, Dict[str, str]] = {}
    for choice in ODKFormChoice.objects.filter(form_name=form_name):
        lookup.setdefault(choice.field_name, {})[choice.value] = choice.label
    for field, mapping in lookup.items():
        if field in df.columns:
            df[field] = df[field].map(lambda v, _m=mapping: _m.get(str(v), v))
    model = FORM_MODEL_MAP[form_name]
    df = normalize_dataframe_columns(df, model)
    objects = [model(**row) for row in df.to_dict(orient="records")]
    model.objects.bulk_create(objects)
    return len(objects)


class ODKPullService:
    """Encapsulate pyODK usage, locking, and incremental state."""

    def __init__(
        self,
        default_project_id: Optional[int] = None,
        lock_ttl_seconds: int = 1800,
        allow_attachments: bool = True,
    ):
        self.default_project_id = default_project_id or getattr(
            settings, "ODK_DEFAULT_PROJECT_ID", None
        )
        self.lock_ttl_seconds = lock_ttl_seconds
        self.allow_attachments = allow_attachments
        self._logger = logger

    def get_client(self, project_id: Optional[int] = None):
        pid = project_id or self.default_project_id
        return make_pyodk_client(pid)

    def _acquire_lock(self, form_id: str, project_id: int):
        return self._acquire(form_id=form_id, project_id=project_id)

    def _acquire_global(self, project_id: int):
        return self._acquire(form_id=GLOBAL_LOCK, project_id=project_id)

    @contextmanager
    def _acquire(self, form_id: str, project_id: int):
        now = timezone.now()
        expires = now + timedelta(seconds=self.lock_ttl_seconds)
        with transaction.atomic():
            lock, created = (
                ODKPullLock.objects.select_for_update()
                .filter(form_id=form_id, project_id=project_id)
                .get_or_create(defaults={"expires_at": expires})
            )
            if not created and lock.expires_at and lock.expires_at > now:
                raise ODKPullLocked(f"Pull already running for {form_id}")
            lock.expires_at = expires
            lock.save(update_fields=["expires_at", "locked_at"])
        try:
            yield
        finally:
            ODKPullLock.objects.filter(form_id=form_id, project_id=project_id).delete()

    def pull_forms(
        self,
        form_configs: Iterable[Dict[str, Any]],
        since: Optional[datetime] = None,
        full_refresh: bool = False,
        dry_run: bool = False,
        no_attachments: bool = False,
        ignore_frequency: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """Pull multiple forms; returns summary per form_id."""
        summary: Dict[str, Dict[str, Any]] = {}
        for cfg in form_configs:
            form_id = cfg.get("form_id")
            if not form_id:
                continue
            if cfg.get("enabled") is False:
                summary[form_id] = {"skipped": True, "reason": "disabled"}
                continue
            project_id = cfg.get("project_id") or self.default_project_id
            form_name = cfg.get("form_name")
            frequency = cfg.get("frequency_minutes")
            state, _ = ODKPullState.objects.get_or_create(
                form_id=form_id, project_id=project_id
            )
            if frequency and state.last_run_finished_at and not ignore_frequency:
                delta = timezone.now() - state.last_run_finished_at
                if delta < timedelta(minutes=int(frequency)):
                    summary[form_id] = {
                        "skipped": True,
                        "reason": "not_due",
                        "last_run": state.last_run_finished_at,
                    }
                    continue
            summary[form_id] = self.pull_form(
                form_id=form_id,
                project_id=project_id,
                form_name=form_name,
                since=since,
                full_refresh=full_refresh,
                dry_run=dry_run,
                no_attachments=no_attachments,
            )
        return summary

    def pull_form(
        self,
        form_id: str,
        project_id: Optional[int] = None,
        form_name: Optional[str] = None,
        since: Optional[datetime] = None,
        full_refresh: bool = False,
        dry_run: bool = False,
        no_attachments: bool = False,
    ) -> Dict[str, Any]:
        """Pull a single form and load it into models."""
        project_id = project_id or self.default_project_id
        if not project_id:
            raise ValueError("project_id is required to pull ODK data")
        state, _ = ODKPullState.objects.get_or_create(
            form_id=form_id, project_id=project_id
        )
        with self._acquire_global(project_id), self._acquire_lock(form_id, project_id):
            state.mark_started()
            self._logger.info(
                "Starting ODK pull",
                extra={
                    "form_id": form_id,
                    "project_id": project_id,
                    "full_refresh": full_refresh,
                    "since": since,
                    "dry_run": dry_run,
                },
            )
            try:
                since_dt = None if full_refresh else (since or state.last_submission_at)
                df, latest_ts = self.list_submissions(
                    form_id=form_id,
                    project_id=project_id,
                    since=since_dt,
                    include_attachments=not no_attachments and self.allow_attachments,
                )
                counts: Dict[str, Any] = {"fetched": len(df)}
                if dry_run or df.empty:
                    state.mark_finished(
                        ODKPullState.STATUS_SUCCESS, counts=counts, last_submission_at=latest_ts
                    )
                    return {**counts, "status": ODKPullState.STATUS_SUCCESS, "dry_run": dry_run}

                loaded_counts = self.upsert_into_models(df, form_name=form_name)
                counts.update(loaded_counts)
                state.mark_finished(
                    ODKPullState.STATUS_SUCCESS,
                    counts=counts,
                    last_submission_at=latest_ts,
                )
                self._logger.info(
                    "Finished ODK pull",
                    extra={
                        "form_id": form_id,
                        "project_id": project_id,
                        "counts": counts,
                        "last_submission_at": latest_ts,
                    },
                )
                return {**counts, "status": ODKPullState.STATUS_SUCCESS}
            except Exception as exc:
                state.mark_finished(
                    ODKPullState.STATUS_FAILED, counts=state.last_counts, error=str(exc)
                )
                self._logger.exception("ODK pull failed for form %s", form_id)
                raise

    def list_submissions(
        self,
        form_id: str,
        project_id: int,
        since: Optional[datetime] = None,
        include_attachments: bool = False,
    ) -> Tuple[pd.DataFrame, Optional[datetime]]:
        """Return submissions DataFrame and latest submission timestamp."""
        with self.get_client(project_id).open() as client:
            filter_expr = None
            if since:
                since_utc = self._as_utc(since)
                filter_expr = f"updatedAt ge {since_utc}"
            data = client.submissions.get_table(
                form_id=form_id, project_id=project_id, expand="*", filter=filter_expr
            )
            records = data.get("value", [])
            if not records:
                return pd.DataFrame(), since

            df = pd.DataFrame.from_records(records)
            df.columns = [c.rsplit("-", 1)[-1] for c in df.columns]

            if include_attachments:
                self.download_attachments_if_needed(
                    client=client, project_id=project_id, form_id=form_id, records=records
                )

            latest_ts = self._max_timestamp(df)
            return df, latest_ts

    def download_attachments_if_needed(
        self,
        client,
        project_id: int,
        form_id: str,
        records: List[Dict[str, Any]],
    ) -> None:
        """Fetch attachments for submissions that report missing attachments."""
        # Placeholder: VACMS currently stores tabular data; attachments can be added later.
        missing = [r for r in records if r.get("attachmentsPresent") and not r.get("attachments")]
        if missing:
            self._logger.info(
                "Skipping attachment download for %s submissions (not implemented)", len(missing)
            )

    def upsert_into_models(self, df: pd.DataFrame, form_name: Optional[str]) -> Dict[str, Any]:
        """Route data to appropriate loader."""
        if form_name and form_name in FORM_MODEL_MAP:
            created = import_dataframe_records(form_name, df)
            return {"created": created}
        results = load_records_from_dataframe(df)
        return {
            "created": len(results["created"]),
            "ignored": len(results["ignored"]),
            "outdated": len(results["outdated"]),
            "corrected": len(results.get("corrected", [])),
        }

    def _max_timestamp(self, df: pd.DataFrame) -> Optional[datetime]:
        for col in ("updatedAt", "createdAt"):
            if col in df.columns:
                ts = pd.to_datetime(df[col], errors="coerce")
                if ts.notnull().any():
                    return ts.max().to_pydatetime()
        return None

    def _as_utc(self, dt: datetime) -> str:
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone=timezone.utc)
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )
