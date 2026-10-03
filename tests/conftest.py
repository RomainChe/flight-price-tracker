import pytest

from tracker.config import _search
from tracker.models import Quote

BASE = {
    "name": "Japon", "origins": ["Barcelone", "Marseille"], "destination": "Japon",
    "depart_from": "2027-05-01", "depart_to": "2027-05-03", "stay_days": [10], "alert_below": 700,
}


@pytest.fixture
def make_search():
    return lambda **over: _search({**BASE, **over}, {})


@pytest.fixture
def search(make_search):
    return make_search()


def quote(price, run_date="2027-01-10", origin="BCN", dest="NRT", rf=None, rt=None, dep="2027-05-01", ret="2027-05-11", **kw):
    return Quote(run_date=run_date, search="Japon", source=kw.pop("source", "Test"), kind="aller-retour",
                 origin=origin, dest=dest, return_from=rf or dest, return_to=rt or origin,
                 depart_date=dep, return_date=ret, price=price, **kw)
