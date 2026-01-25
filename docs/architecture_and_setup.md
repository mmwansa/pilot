# VA Explorer Architecture, Setup, and Command Guide

## 1. Platform overview
VA Explorer is a Django/PostgreSQL reference implementation for managing and analyzing Verbal Autopsy (VA) data. It bundles user and role management, data supervision workflows, automated cause-of-death (COD) coding, dashboards, and integrations with tools such as ODK Central, Kobo Toolbox, and DHIS2 so civil registration programs can run their VA pipelines from a single interface.【F:README.md†L6-L19】

## 2. System architecture
### 2.1 Django project layout and services
The project uses a conventional Django layout rooted at `config/` and `va_explorer/`. Core settings define the root directories, load environment variables from `.env`, and configure PostgreSQL with request-level transactions, Django-allauth authentication, and modular app registration for the home, users, analytics, data management, DHIS, export, cleanup, and CMS modules.【F:config/settings/base.py†L10-L143】 Middleware mixes Django defaults with CORS, WhiteNoise, request history tracking, and the debug toolbar.【F:config/settings/base.py†L145-L167】 Static and media assets live under `va_explorer/static` and `va_explorer/media`, and custom template libraries/context processors expose VA-specific metadata in every view.【F:config/settings/base.py†L169-L218】

Celery is preconfigured with Redis brokers, long task timeouts, and database-backed beat scheduling so background jobs such as imports and COD coding can be offloaded when needed.【F:config/settings/base.py†L283-L304】 Email, caching, and security settings are centralized so deployments can switch between console delivery, SMTP, or production-grade credentials via environment variables.【F:config/settings/base.py†L221-L282】

### 2.2 Domain model
The `va_data_management` app models VA locations as a tree using `treebeard` so every facility sits under a hierarchical province/district path, enabling efficient access control by geography.【F:va_explorer/va_data_management/models/verbal_autopsy.py†L27-L53】 Each `VerbalAutopsy` record stores the full WHO instrument fields, links to a location, and includes indexes/permissions for high-volume querying and bulk operations.【F:va_explorer/va_data_management/models/verbal_autopsy.py†L55-L199】 Soft deletion and historical tracking are enabled via `SoftDeletionModel` and `django-simple-history`, letting teams audit changes to sensitive health data.【F:va_explorer/va_data_management/models/verbal_autopsy.py†L12-L24】

### 2.3 Access control and user management
A custom `User` model uses email-as-username, tracks supplemental contact data, and enforces password history/complexity validators. Users can be restricted to multiple locations; the helper `verbal_autopsies()` method automatically expands a user’s location tree and filters VA querysets to those leaves, which powers all dashboards and exports.【F:va_explorer/users/models.py†L52-L101】 Fine-grained permissions (`view_pii`, `download_data`, `supervise_users`, etc.) are surfaced as convenience properties on the model so business rules can grant or revoke capabilities while keeping a clean API for the UI layer.【F:va_explorer/users/models.py†L101-L145】

### 2.4 Data ingestion utilities
Most ingestion commands rely on shared helpers in `va_data_management.utils.loading`. These helpers normalize field names, reconcile CSV columns with Django models, map ODK-coded values to human-readable labels, assign facilities automatically, and bulk-create model instances (with history) before validating them for dashboard use.【F:va_explorer/va_data_management/utils/loading.py†L1-L120】【F:va_explorer/va_data_management/utils/loading.py†L178-L229】 The same module implements `load_records_from_dataframe`, which powers ODK/Kobo imports by harmonizing critical identifiers such as `instanceid` and ensuring essential interview metadata exists before saving.【F:va_explorer/va_data_management/utils/loading.py†L230-L320】

### 2.5 Analytics and dashboards
The home dashboard view aggregates summary counts, location names, and high-level metrics for the current user by combining `get_va_summary_stats` with `get_homepage_metrics`, then exposes a trends API that streams table data, graphs, and issue lists to the frontend.【F:va_explorer/home/views.py†L10-L51】 The analytics app adds REST endpoints plus template-driven dashboards for supervisors; `DashboardAPIView` accepts filters (date range, COD, region, age, sex) and feeds them through `load_va_data`, while `UserSupervisionView` wraps `django-filter` and pandas to compute interviewer performance, timeliness, and error rates grouped by fieldworker, facility, or other dimensions.【F:va_explorer/va_analytics/views.py†L23-L152】

### 2.6 Background integrations
Data integrations live in dedicated management commands:
- ODK Central imports run through `ODKPullService`, which handles locking, incremental state, and retries; both the scheduled Celery task and the `import_from_odk` command call the same pipeline.【F:va_explorer/va_data_management/odk/service.py†L1-L247】【F:va_explorer/va_data_management/management/commands/import_from_odk.py†L1-L125】
- Kobo Toolbox imports support pagination via batch tokens and track created, ignored, overwritten, corrected, and invalid records while iterating through every page of submissions.【F:va_explorer/va_data_management/management/commands/import_from_kobo.py†L11-L71】
- DHIS2 exports fetch coded VAs, look up COD mappings, hit the pyCrossVA transform service, and assemble entity attribute CSVs before sending them to DHIS using environment-provided credentials.【F:va_explorer/va_data_management/management/commands/run_dhis.py†L1-L120】
- COD automation runs through `run_coding_algorithms`, which validates algorithm settings, optionally backs up and wipes prior CODs, runs the configured algorithms, and reports throughput/issues for auditing.【F:va_explorer/va_data_management/management/commands/run_coding_algorithms.py†L14-L60】

## 3. Environment setup and local execution
1. **Clone & enter the repo.** The README walks contributors through cloning and changing directories.【F:README.md†L63-L71】
2. **Create and activate a Python 3.10–3.12 virtual environment.** Platform-specific activation commands are documented so Windows (CMD, PowerShell), Git Bash, and Linux/macOS users can all follow the same process.【F:README.md†L73-L112】
3. **Install dependencies.** Run `pip install -r requirements/local.txt` to pull in Django, Celery, DRF, etc.【F:README.md†L113-L117】
4. **Configure PostgreSQL and `.env`.** Create a local database (default `vae_cms_db`), copy `.env.template`, and fill in connection variables (`POSTGRES_HOST/PORT/DB/USER/PASSWORD`).【F:README.md†L119-L142】
5. **Apply migrations.** Ensure `psycopg2-binary` is installed, then run `python manage.py makemigrations` and `python manage.py migrate` (CLI variants for each OS shell are provided).【F:README.md†L143-L199】
6. **Bootstrap permissions and an admin.** Run `python manage.py initialize_groups` followed by `python manage.py seed_admin_user <EMAIL> --password <PASSWORD>` to seed the core roles and a login credential.【F:README.md†L210-L280】
7. **Start the server.** Use `python manage.py runserver` (or `./manage.py runserver`) and browse to `http://localhost:8000`. Linting (`pre-commit`) and tests (`pytest`, optional coverage) are documented for contributors.【F:README.md†L289-L320】
8. **Optional COD pipeline.** If you need automated COD assignments, build the supporting Docker services and run `./manage.py run_coding_algorithms` once the containers are up.【F:README.md†L322-L327】

## 4. Management commands reference
All commands are executed with `python manage.py <command> [options]` (or `./manage.py`). Commands fall into several categories:

### 4.1 User and permission provisioning
| Command | Description & options |
| --- | --- |
| `initialize_groups [--debug]` | Recreates the predefined Admin, Data Manager, Data Viewer, Field Worker, Mortality Surveillance Officer, and Community Surveillance Officer groups and reattaches the correct dashboard, VA, user, and data cleanup permissions. `--debug` prints missing permission diagnostics without failing the run.【F:va_explorer/users/management/commands/initialize_groups.py†L1-L114】 |
| `seed_admin_user <email> [--password <value>]` | Creates a superuser with the supplied email. In production, the command refuses custom passwords and instead generates a temporary 32-character password, marking the account as requiring reset. In other environments you can pass `--password` to set a known credential.【F:va_explorer/users/management/commands/seed_admin_user.py†L11-L60】 |
| `seed_demo_users` | Only in the local settings profile, seeds demo Data Manager, Data Viewer, and Field Worker accounts with predictable addresses (`data_manager@example.com`, etc.) and the default `Password1`, assigning them to the correct groups.【F:va_explorer/users/management/commands/seed_demo_users.py†L10-L55】 |
| `get_user_form_template [--output_file user_form_fields.csv]` | Exports the current user-creation form schema (field names, requirements, default choices) to CSV so you can prepare bulk user files confidently.【F:va_explorer/users/management/commands/get_user_form_template.py†L1-L21】 |
| `bulk_load_users <csv> [--email_confirmation <bool>]` | Creates accounts from a CSV that mirrors the user creation form. Each user is assigned a temporary password, and you can toggle `--email_confirmation` if you want to trigger notifications after import.【F:va_explorer/users/management/commands/bulk_load_users.py†L1-L23】 |
| `export_user_info [--output_file user_list.csv] [--user_file source.csv]` | Produces an anonymized export of all users (roles, permissions) without PII. You can optionally feed an existing CSV via `--user_file` to use as a filter/template.【F:va_explorer/users/management/commands/export_user_info.py†L6-L27】 |

### 4.2 Location and reference data
| Command | Description & options |
| --- | --- |
| `load_locations <csv> [--delete_previous <bool>]` | Builds the facility tree (country → province → district → facility) from a CSV that must include `province`, `district`, `key`, `name`, and `status`. Setting `--delete_previous True` wipes existing locations before rebuilding the tree.【F:va_explorer/va_data_management/management/commands/load_locations.py†L11-L48】 |
| `refresh_locations` | Iterates through every VA (in 5,000-record batches), maps legacy hospital keys to the latest facility list, reassigns `location` when needed, and revalidates dashboard caches.【F:va_explorer/va_data_management/management/commands/refresh_locations.py†L11-L57】 |
| `export_locations [--output_file locations_<timestamp>.csv]` | Dumps the current facility roster (province, district, name, key, status) to CSV for auditing or editing.【F:va_explorer/va_data_management/management/commands/export_locations.py†L9-L61】 |
| `load_srs_cluster_locations <csv> [--delete_previous]` | Imports the SRS cluster hierarchy (province → district → constituency → ward → EA) with optional boolean cleanup of existing `SRSClusterLocation` rows; unmatched EA names can be deduped automatically, and `--delete_previous` wipes prior data after a confirmation prompt.【F:va_explorer/va_data_management/management/commands/load_srs_cluster_locations.py†L10-L200】 |
| `load_dhis_cod_codes <csv>` | Loads COD code mappings needed for DHIS2 export. Pass a CSV with the DHIS codes and descriptions; the command lowercases columns, bulk creates `CODCodesDHIS`, and reports the number of records inserted.【F:va_explorer/va_data_management/management/commands/load_dhis_cod_codes.py†L1-L23】 |

### 4.3 Household and census collection
| Command | Description & options |
| --- | --- |
| `load_form_csv <form_name> <csv>` | Generic loader for ODK form outputs (`household`, `household_member`, `pregnancy`, `pregnancy_outcome`, `death`). It requires the ODK definition to be preloaded, maps coded values to labels, normalizes columns to the model, and bulk creates rows.【F:va_explorer/va_data_management/management/commands/load_form_csv.py†L17-L56】 |
| `load_household_csv <csv>` | Specialized loader for baseline household surveys that normalizes dozens of HH_* columns using ODK definitions, bulk creates `Household` rows, and automatically runs `dq_households` afterward to flag duplicates, timeliness, and consent issues.【F:va_explorer/va_data_management/management/commands/load_household_csv.py†L16-L125】 |
| `load_household_members <csv> [--log_dir logs/]` | Imports roster entries using the parent household key. It translates select-one codes using ODK choices, ensures `parent_key` is present, bulk creates `HouseholdMember` rows, and logs any skipped records (with timestamps) to the specified directory.【F:va_explorer/va_data_management/management/commands/load_household_members.py†L18-L110】 |
| `dq_households` | Runs the household data-quality suite: duplicate detection (exact field matches or EA/HUN/HHN collisions within a one-day window), short interview duration, submission timeliness, completeness, and consent validation. Results are persisted and exported to CSV/JSON, and stale issues can be auto-resolved.【F:va_explorer/va_data_management/management/commands/dq_households.py†L1-L80】【F:va_explorer/va_data_management/management/commands/dq_households.py†L120-L169】 |

### 4.4 Pregnancy, death, and VA imports
| Command | Description & options |
| --- | --- |
| `load_pregnancy_csv <csv>` | Loads pregnancy forms using the previously imported ODK definition, enforces unique `key` values, drops blanks/duplicates, filters out already-known keys, maps coded columns, and bulk inserts while reporting skipped counts.【F:va_explorer/va_data_management/management/commands/load_pregnancy_csv.py†L11-L87】 |
| `load_pregnancy_outcome_csv <csv> [--log_missing_ea missing_ea_name_mappings.csv]` | Similar to the pregnancy loader but additionally maps EA names to `SRSClusterLocation` codes, logs unmatched EAs to the specified file, and maintains uniqueness on `key`.【F:va_explorer/va_data_management/management/commands/load_pregnancy_outcome_csv.py†L16-L117】 |
| `load_death_csv <csv>` | Imports death notifications using the ODK definitions, requiring a `key`, removing duplicates/blanks, mapping select fields, and bulk inserting new rows only.【F:va_explorer/va_data_management/management/commands/load_death_csv.py†L1-L52】 |
| `load_va_csv <csv> [--random_locations True|False]` | Loads WHO VA CSV exports directly into the `VerbalAutopsy` table via `load_records_from_dataframe`, with an optional flag to assign random locations (useful for demonstrations). It reports created/ignored/outdated rows after ingest.【F:va_explorer/va_data_management/management/commands/load_va_csv.py†L9-L29】 |
| `load_odk_definitions [--dry-run] [--only FIELD] [--force] [--no-verbose]` | Parses the bundled XLSForms (household, pregnancy, pregnancy outcome, death) and stores every choice in `ODKFormChoice`. `--dry-run` inspects without writing, `--only` restricts to a single survey field, `--force` deletes previous choices, and `--no-verbose` silences log chatter.【F:va_explorer/va_data_management/management/commands/load_odk_definitions.py†L10-L143】 |
| `import_from_odk [--form-id <xmlFormId>] [--project-id <id>] [--since <ISO|7d>] [--full-refresh] [--dry-run] [--no-attachments]` | Uses the shared `ODKPullService` to import submissions with locking/state; defaults to configured forms when `--form-id` is omitted and can run incremental windows via `--since` or full refreshes via `--full-refresh`.【F:va_explorer/va_data_management/management/commands/import_from_odk.py†L1-L125】 |
| `import_from_kobo [--token <value>] [--asset_id <value>]` | Streams Kobo Toolbox submissions in batches of 5,000 using either CLI tokens or `KOBO_API_TOKEN/KOBO_ASSET_ID`, tallying created, ignored, overwritten, corrected, and invalid rows as it iterates over every results page.【F:va_explorer/va_data_management/management/commands/import_from_kobo.py†L11-L71】 |

### 4.5 Data cleanup and demo utilities
| Command | Description & options |
| --- | --- |
| `mark_vas_as_duplicate` | Requires `QUESTIONS_TO_AUTODETECT_DUPLICATES` in the settings/.env. Generates unique hashes for every VA, bulk updates the identifier field, then calls `VerbalAutopsy.mark_duplicates()` to flag duplicates for review.【F:va_explorer/va_data_management/management/commands/mark_vas_as_duplicate.py†L7-L47】 |
| `fake_current_va_dates` | Local-only utility that shifts every VA’s death and audit timestamps so that legacy datasets appear current by computing the most recent recorded death date and offsetting all rows accordingly.【F:va_explorer/va_data_management/management/commands/fake_current_va_dates.py†L1-L40】 |
| `randomize_va_dates` | Another local-only helper that redistributes VA interview/death dates across the past six months with an increasing trend so dashboards look realistic. Uses `tqdm` for progress and preserves historical auditing state by toggling `skip_history_when_saving`.【F:va_explorer/va_data_management/management/commands/randomize_va_dates.py†L1-L46】 |

### 4.6 COD automation and DHIS2 integration
| Command | Description & options |
| --- | --- |
| `run_coding_algorithms [--overwrite <bool>] [--cod_fname old_cod_mapping.csv]` | Validates algorithm settings, optionally backs up and deletes existing COD assignments, runs the configured algorithms, and reports counts/issue totals so you know how many VAs were coded successfully.【F:va_explorer/va_data_management/management/commands/run_coding_algorithms.py†L14-L60】 |
| `load_dhis_cod_codes <csv>` | Imports the COD code mapping table required by DHIS exports (see §4.2).【F:va_explorer/va_data_management/management/commands/load_dhis_cod_codes.py†L1-L23】 |
| `run_dhis` | Collects all coded-but-unexported VAs, joins them with CODs, transforms the data through the pyCrossVA service, generates entity attribute and record storage CSVs, coerces date/age fields to DHIS-friendly types, and posts them using credentials supplied via `DHIS_USER`, `DHIS_PASS`, `DHIS_HOST`, `DHIS_ORGUNIT`, and `DHIS2_URL`/`DHIS2_SSL_VERIFY`. Only VAs absent from `DhisStatus` are processed, and CSV artifacts land in `OpenVAFiles/` for inspection.【F:va_explorer/va_data_management/management/commands/run_dhis.py†L1-L120】 |

## 5. Executing commands
All commands follow the same pattern:
```bash
# Example: load household data
python manage.py load_household_csv data/households.csv

# Example with options
python manage.py import_from_odk --form-id abc --project-id 123 --since 7d --dry-run
```
When an option is marked as mutually exclusive (e.g., `--project-id` vs. `--project-name`), supply only one. Many commands support environment-variable fallbacks so secrets can be managed outside the CLI. Demo utilities guard themselves with `DJANGO_SETTINGS_MODULE=config.settings.local` to avoid accidental production use.

Use this document as a quick reference whenever you need to explain the platform’s architecture, rebuild a development environment, or run a specific management command.
