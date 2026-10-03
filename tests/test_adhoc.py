import pytest

from tracker.adhoc import config_from_env
from tracker.config import _search

FORM = {
    "SEARCH_ORIGINS": "Barcelone, Paris", "SEARCH_DESTINATION": "Thaïlande", "SEARCH_DEPART_FROM": "2027-02-10",
    "SEARCH_DEPART_TO": "", "SEARCH_RETURN_DATE": "", "SEARCH_STAY_DAYS": "10, 14", "SEARCH_PASSENGERS": "2",
    "SEARCH_CABIN": "economy", "SEARCH_MAX_STOPS": "1", "SEARCH_LAYOVER_MIN_HOURS": "2,5", "SEARCH_LAYOVER_MAX_HOURS": "",
    "SEARCH_NO_AIRPORT_CHANGE": "true", "SEARCH_CHECKED_BAG": "false", "SEARCH_MAX_DURATION_HOURS": "",
    "SEARCH_EXCLUDED_AIRLINES": "Aeroflot, SU", "SEARCH_ALERT_BELOW": "600",
}


def test_form_becomes_a_valid_search():
    raw = config_from_env(FORM)["searches"][0]
    s = _search(raw, {})
    assert s.origin_airports == ["BCN", "CDG", "ORY"] and "BKK" in s.dest_airports
    assert s.depart_from == s.depart_to and s.stay_days == [10, 14]
    assert s.passengers == 2 and s.max_stops == 1 and s.alert_below == 600
    assert s.layover_hours == (2.5, 24) and s.no_airport_change and not s.checked_bag
    assert s.excluded_airlines == ["Aeroflot", "SU"]


def test_empty_optional_fields_mean_no_constraint():
    raw = config_from_env({**FORM, "SEARCH_MAX_STOPS": "illimité", "SEARCH_LAYOVER_MIN_HOURS": "",
                           "SEARCH_ALERT_BELOW": "", "SEARCH_RETURN_DATE": "2027-02-24", "SEARCH_STAY_DAYS": ""})
    s = _search(raw["searches"][0], {})
    assert s.max_stops is None and s.layover_hours is None and s.alert_below is None
    assert s.return_date.isoformat() == "2027-02-24"


@pytest.mark.parametrize("field, value, message", [
    ("SEARCH_PASSENGERS", "deux", "Passagers"),
    ("SEARCH_STAY_DAYS", "10 jours", "Durées de séjour"),
    ("SEARCH_LAYOVER_MAX_HOURS", "six", "Escale max"),
])
def test_bad_form_values_give_clear_errors(field, value, message):
    with pytest.raises(ValueError, match=message):
        config_from_env({**FORM, field: value})


def test_departure_outside_france_or_bcn_is_still_refused():
    with pytest.raises(ValueError, match="refusée"):
        _search(config_from_env({**FORM, "SEARCH_ORIGINS": "Madrid"})["searches"][0], {})
