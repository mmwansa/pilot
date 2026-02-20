"""Backward-compatible re-exports for VACMS admin panel command registry."""

from va_explorer.va_admin.command_registry import (  # noqa: F401
    ADMINS_GROUP_NAME,
    ALLOWLIST,
    STANDARD_FILENAME_PLACEHOLDERS,
    grouped_command_specs,
    resolve_data_file,
)
