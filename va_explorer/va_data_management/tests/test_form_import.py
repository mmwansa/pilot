from pathlib import Path

import pandas as pd
import pytest
from django.core.management import CommandError, call_command

from va_explorer.va_data_management.models import (
    Death,
    ODKFormChoice,
    Pregnancy,
    PregnancyOutcome,
    PregnancyOutcomeBaby,
)

pytestmark = pytest.mark.django_db


def make_definition(tmpdir):
    survey = pd.DataFrame(
        {
            "type": ["select_one yesno"],
            "name": ["consent"],
            "label": ["Consent"],
        }
    )
    choices = pd.DataFrame(
        {
            "list_name": ["yesno", "yesno"],
            "name": ["1", "0"],
            "label": ["Yes", "No"],
        }
    )
    xls_path = Path(tmpdir) / "def.xlsx"
    with pd.ExcelWriter(xls_path) as writer:
        survey.to_excel(writer, sheet_name="survey", index=False)
        choices.to_excel(writer, sheet_name="choices", index=False)
    return xls_path


def test_import_definition_and_csv(tmp_path):
    definition = make_definition(tmp_path)
    call_command("load_pregnancy_definition", str(definition))
    assert ODKFormChoice.objects.count() == 2

    csv_path = Path(tmp_path) / "data.csv"
    csv_path.write_text("consent\n1\n")
    call_command("load_pregnancy_csv", str(csv_path))
    preg = Pregnancy.objects.get()
    assert preg.consent == "Yes"


def test_death_import_definition_and_csv(tmp_path):
    definition = make_definition(tmp_path)
    call_command("load_death_definition", str(definition))
    assert ODKFormChoice.objects.filter(form_name="death").count() == 2

    csv_path = Path(tmp_path) / "data.csv"
    csv_path.write_text("consent\n1\n")
    call_command("load_death_csv", str(csv_path))
    death = Death.objects.get()
    assert death.consent == "Yes"


def test_pregnancy_outcome_import_definition_and_csv(tmp_path):
    definition = make_definition(tmp_path)
    call_command("load_pregnancy_outcome_definition", str(definition))
    assert ODKFormChoice.objects.filter(form_name="pregnancy_outcome").count() == 2

    csv_path = Path(tmp_path) / "data.csv"
    csv_path.write_text("consent\n1\n")
    call_command("load_pregnancy_outcome_csv", str(csv_path))
    outcome = PregnancyOutcome.objects.get()
    assert outcome.consent == "Yes"


def test_import_without_definition(tmp_path):
    csv_path = Path(tmp_path) / "data.csv"
    csv_path.write_text("consent\n1\n")
    with pytest.raises(CommandError):
        call_command("load_pregnancy_csv", str(csv_path))


def test_death_import_without_definition(tmp_path):
    csv_path = Path(tmp_path) / "data.csv"
    csv_path.write_text("consent\n1\n")
    with pytest.raises(CommandError):
        call_command("load_death_csv", str(csv_path))


def test_pregnancy_outcome_import_without_definition(tmp_path):
    csv_path = Path(tmp_path) / "data.csv"
    csv_path.write_text("consent\n1\n")
    with pytest.raises(CommandError):
        call_command("load_pregnancy_outcome_csv", str(csv_path))


def test_pregnancy_outcome_baby_details_linking_and_missing_parent_skip(tmp_path):
    definition = make_definition(tmp_path)
    call_command("load_pregnancy_outcome_definition", str(definition))

    parent_csv = Path(tmp_path) / "pregnancy_outcome.csv"
    parent_csv.write_text("key,consent\nparent-1,1\n")
    call_command("load_pregnancy_outcome_csv", str(parent_csv))
    assert PregnancyOutcome.objects.filter(key="parent-1").exists()

    baby_csv = Path(tmp_path) / "pregnancy_outcome_baby_details.csv"
    baby_csv.write_text(
        "PARENT_KEY,KEY,PO-49A,PO-49B,PO-49C\n"
        "parent-1,parent-1/baby[1],Baby 1,First Child,01\n"
        "missing-parent,missing-parent/baby[1],Baby X,Orphan Child,02\n"
    )

    call_command(
        "load_po_baby_details",
        str(baby_csv),
        "--log_dir",
        str(tmp_path),
    )

    assert PregnancyOutcomeBaby.objects.count() == 1
    baby = PregnancyOutcomeBaby.objects.get()
    assert baby.pregnancy_outcome.key == "parent-1"
    assert baby.PO_49B == "First Child"
