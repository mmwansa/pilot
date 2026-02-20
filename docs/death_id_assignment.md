# Death ID Assignment

The `assign_death_ids` management command generates and assigns unique sequential death identifiers to `Death` records that don't have them. Each death ID is composed of the ward's cluster code plus a sequential number, ensuring deaths are uniquely identifiable within a cluster and globally unique across the entire system.

## Format

Death ID format: `{cluster_code}{sequence:04d}`

**Example:**
- Cluster code: `1213SM`
- First death in ward: `1213SM0001`
- Second death in ward: `1213SM0002`
- Third death in ward: `1213SM0003`

Each ward maintains its own independent sequence counter.

## Prerequisites

- `ClusterLocationCodes` table must be populated with ward cluster codes (see [Generate Cluster IDs](generate_cluster_id.md))
- `Death` records must have the `ward` field populated

## Auto-Migration

The command automatically checks if the `death_id` column exists on the `Death` table. If the column is missing:
1. Runs `makemigrations va_data_management`
2. Runs `migrate` to create the column
3. Proceeds with death ID assignment

If migrations fail, the command displays instructions to run them manually.

## Usage

### Preview Assignments (Dry Run)

Before assigning death IDs, preview what would be assigned:

```bash
python manage.py assign_death_ids --dry-run
```

**Output:**
- Count of deaths without death_ids
- Number of wards affected
- Table preview showing first 20 assignments (ward, death_id, deceased name)
- Total count of deaths to be updated

### Assign Death IDs

Execute the actual assignment:

```bash
python manage.py assign_death_ids
```

**Behavior:**
- Queries all `Death` records with missing or empty `death_id`
- Groups deaths by ward
- Looks up each ward's cluster code from `ClusterLocationCodes` (case-insensitive match on `ward_code`)
- Finds the next available sequence number for each ward (respects existing assignments)
- Generates sequential IDs and updates the database
- Displays summary of assignments

## Output Example

```
Found 45 deaths without death_ids.
Deaths grouped into 3 ward(s).
================================================================================
Ward                 Death ID        Deceased Name
================================================================================
CHAMUKA              1213SM0001      John Doe
CHAMUKA              1213SM0002      Jane Smith
CHISAMBA             4567KL0001      Robert Brown
...
================================================================================
✓ Successfully assigned death_ids to 45 death(s).
```

## Warnings & Edge Cases

- **Missing cluster codes:** If a ward in the `Death` table doesn't exist in `ClusterLocationCodes`, deaths in that ward are skipped with a warning
- **Case-insensitive matching:** Ward matching is case-insensitive to handle variations like "CHAMUKA" vs "chamuka"
- **Sequence continuation:** If a ward already has some deaths with IDs, new deaths continue from the highest sequence number

## Troubleshooting

**No deaths without death_ids found:**
All deaths already have IDs assigned; nothing to do.

**No cluster code found for wards:**
Ensure `ClusterLocationCodes` table is populated and matches ward names from the `Death` table. Run:
```bash
python manage.py generate_ward_codes --initial
```

**Migration fails:**
If auto-migration fails, run manually:
```bash
python manage.py makemigrations va_data_management
python manage.py migrate
```
Then retry the command.
