import pytest

from tracker.airports import resolve_destination, resolve_origin
from tracker.config import load_config, passes_filters


def test_origins_by_name_or_code():
    assert resolve_origin("Paris") == ["CDG", "ORY"]
    assert resolve_origin("Barcelone") == ["BCN"]
    assert resolve_origin("mrs") == ["MRS"]
    assert resolve_origin(" Montpellier ") == ["MPL"]


@pytest.mark.parametrize("city", ["Madrid", "Genève", "LHR", "Tokyo"])
def test_origin_outside_france_or_bcn_is_refused(city):
    with pytest.raises(ValueError, match="refusée"):
        resolve_origin(city)


def test_destination_country_lists_international_airports():
    airports, country = resolve_destination("Japon")
    assert country == "JP" and {"NRT", "HND", "KIX", "NGO", "FUK", "CTS"} <= set(airports)
    assert resolve_destination("Séoul") == (["ICN"], None)


def test_unknown_destination_explains_how_to_fix():
    with pytest.raises(ValueError, match="destination_airports"):
        resolve_destination("Groenland")


def test_example_config_is_valid():
    s = load_config("config.yaml").searches[0]
    assert s.origin_airports == ["BCN", "MRS"]
    assert s.origin_city == {"BCN": "Barcelone", "MRS": "Marseille"}
    assert s.stay_days == [10, 14, 21] and s.alert_below == 700


@pytest.mark.parametrize("override, message", [
    ({"origins": ["Madrid"]}, "refusée"),
    ({"stay_days": []}, "stay_days"),
    ({"depart_to": "2027-04-01"}, "avant"),
    ({"depart_from": "1er mai"}, "date invalide"),
    ({"cabin": "luxe"}, "classe"),
])
def test_invalid_search_is_rejected(make_search, override, message):
    with pytest.raises(ValueError, match=message):
        make_search(**override)


def test_filters(make_search):
    s = make_search(max_stops=1, max_duration_hours=20, excluded_airlines=["Aeroflot", "SU"])
    assert passes_filters(s, 1, 900, "Air France; KLM")
    assert not passes_filters(s, 2, 900, "Air France")
    assert not passes_filters(s, 0, 21 * 60, "Air France")
    assert not passes_filters(s, 0, 900, "SU")
    assert not passes_filters(s, 0, 900, "Air France + Aeroflot")
    assert passes_filters(s, 0, 900, "Lufthansa")  # « SU » ne doit pas matcher par sous-chaîne
