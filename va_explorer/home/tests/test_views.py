import datetime as dt
import json
from datetime import date, datetime

import pytest
import time_machine
from dateutil.relativedelta import relativedelta
from dateutil.tz import gettz
from django.test import Client

from va_explorer.tests.factories import (
    CauseCodingIssueFactory,
    CauseOfDeathFactory,
    VerbalAutopsyFactory,
)
from va_explorer.users.models import User

pytestmark = pytest.mark.django_db
eastern_tz = gettz("US/Eastern")


# Hit the trends json endpoint and make sure the counts are correct
# Use time machine to eliminate variation in retrieving today's date
@time_machine.travel(dt.datetime(2021, 10, 26, 1, 24, tzinfo=eastern_tz))
def test_trends(user: User):
    client = Client()
    client.force_login(user=user)

    today = date.today()

    # Other interview dates
    today_minus_one_month = datetime.now() - relativedelta(months=1)
    today_minus_six_months = datetime.now() - relativedelta(months=6)
    today_minus_one_year = datetime.now() - relativedelta(months=12)

    # VAs collected today = 2
    coded_va = VerbalAutopsyFactory.create(Id10012=today, Id10023=today)
    uncoded_va = VerbalAutopsyFactory.create(Id10012=today, Id10023=today)
    # VAs collected at other points in time = 3
    VerbalAutopsyFactory.create(
        Id10012=today_minus_one_month, Id10023=today_minus_one_month
    )
    VerbalAutopsyFactory.create(
        Id10012=today_minus_six_months, Id10023=today_minus_six_months
    )
    VerbalAutopsyFactory.create(
        Id10012=today_minus_one_year, Id10023=today_minus_one_year
    )

    CauseOfDeathFactory.create(cause="Indeterminate", verbalautopsy=coded_va)
    CauseCodingIssueFactory.create(verbalautopsy=coded_va, severity="error")

    response = client.get("/trends", follow=True)
    assert response.status_code == 200

    json_data = json.loads(response.content)
    va_table_data = json_data["vaTable"]

    # Check that trends counts are correct
    assert va_table_data["collected"]["24"] == 2
    assert va_table_data["collected"]["1 week"] == 2
    assert va_table_data["collected"]["1 month"] == 3
    assert va_table_data["collected"]["Overall"] == 5

    assert va_table_data["coded"]["24"] == 1
    assert va_table_data["coded"]["1 week"] == 1
    assert va_table_data["coded"]["1 month"] == 1
    assert va_table_data["coded"]["Overall"] == 1

    assert va_table_data["uncoded"]["24"] == 1
    assert va_table_data["uncoded"]["1 week"] == 1
    assert va_table_data["uncoded"]["1 month"] == 2
    assert va_table_data["uncoded"]["Overall"] == 4

    # Check that the underlying graph data are correct
    # Graphs do not show VAs collected in the current month
    # Thus, the collected VAs were in: October, April, and September
    assert json_data["graphs"]["collected"]["y"] == [
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
    ]
    # Graphs do not show VAs coded in the current month
    # Thus, there are no coded VAs in the time period in question
    assert json_data["graphs"]["coded"]["y"] == [
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    ]
    # Graphs do not show VAs uncoded in the current month
    # Thus, the uncoded VAs were in: October, April, and September
    assert json_data["graphs"]["uncoded"]["y"] == [
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
    ]

    # VAs in issue list includes VAs with no cause in Cause of Death
    assert len(json_data["issueList"]) == 4
    assert uncoded_va.Id10017 in json_data["issueList"][0]["deceased"]
    assert json_data["additionalIssues"] == 0
    # VAs in indeterminate COD list includes VAs with indeterminate COD
    assert len(json_data["indeterminateCodList"]) == 1
    assert json_data["indeterminateCodList"][0]["id"] == coded_va.id
    assert json_data["additionalIndeterminateCods"] == 0

    assert json_data["isFieldWorker"] is False


# Hit the trends json endpoint and make sure the counts are correct
def test_trends_no_data(user: User):
    client = Client()
    client.force_login(user=user)

    response = client.get("/trends", follow=True)
    assert response.status_code == 200

    json_data = json.loads(response.content)
    va_table_data = json_data["vaTable"]

    # Check that trends counts are correct
    assert va_table_data["collected"]["24"] == 0
    assert va_table_data["collected"]["1 week"] == 0
    assert va_table_data["collected"]["1 month"] == 0
    assert va_table_data["collected"]["Overall"] == 0

    assert va_table_data["coded"]["24"] == 0
    assert va_table_data["coded"]["1 week"] == 0
    assert va_table_data["coded"]["1 month"] == 0
    assert va_table_data["coded"]["Overall"] == 0

    assert va_table_data["uncoded"]["24"] == 0
    assert va_table_data["uncoded"]["1 week"] == 0
    assert va_table_data["uncoded"]["1 month"] == 0
    assert va_table_data["uncoded"]["Overall"] == 0

    # Check that the underlying graph data are correct
    # Graphs do not show VAs collected in the current month
    # Thus, the collected VAs were in: October, April, and September
    assert json_data["graphs"]["collected"]["y"] == [
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    ]
    # Graphs do not show VAs coded in the current month
    # Thus, there are no coded VAs in the time period in question
    assert json_data["graphs"]["coded"]["y"] == [
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    ]
    # Graphs do not show VAs uncoded in the current month
    # Thus, the uncoded VAs were in: October, April, and September
    assert json_data["graphs"]["uncoded"]["y"] == [
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    ]

    assert len(json_data["issueList"]) == 0
    assert json_data["additionalIssues"] == 0
    assert len(json_data["indeterminateCodList"]) == 0
    assert json_data["additionalIndeterminateCods"] == 0

    assert json_data["isFieldWorker"] is False


def test_regional_operations_page_loads(user: User):
    client = Client()
    client.force_login(user=user)

    response = client.get("/regional-operations/", follow=True)
    assert response.status_code == 200
    assert b"id=\"regionalFiltersComponent\"" in response.content
    assert b"id=\"regionalCsaComponent\"" in response.content
    assert b"id=\"regionalMsoComponent\"" in response.content


def test_regional_operations_components_refresh_independently(user: User):
    client = Client()
    client.force_login(user=user)

    filters_response = client.get(
        "/regional-operations/components/filters/",
        {"geography": "lusaka", "time_preset": "time7"},
        follow=True,
    )
    assert filters_response.status_code == 200
    assert b"id=\"geographyFilterSelect\"" in filters_response.content
    assert b"value=\"lusaka\" selected" in filters_response.content

    csa_response = client.get(
        "/regional-operations/components/csa/",
        {"geography": "lusaka", "csa_sort": "deaths", "csa_dir": "asc"},
        follow=True,
    )
    assert csa_response.status_code == 200
    assert b"CSA Name (Search)" in csa_response.content
    assert b"regional-sort-link" in csa_response.content

    mso_response = client.get(
        "/regional-operations/components/mso/",
        {"source": "facility", "mso_sort": "error", "mso_dir": "asc"},
        follow=True,
    )
    assert mso_response.status_code == 200
    assert b"id=\"msoSourceSelect\"" in mso_response.content
    assert b"value=\"facility\" selected" in mso_response.content
    assert b"regional-sort-link" in mso_response.content


# Get the about page and make sure it returns successfully
def test_about(user: User):
    client = Client()
    client.force_login(user=user)
    response = client.get("/about/")
    assert response.status_code == 200
