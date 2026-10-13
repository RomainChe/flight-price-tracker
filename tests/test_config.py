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
    assert s.origin_airports == ["BCN", "CDG", "ORY", "MRS", "LYS", "NCE", "TLS"]
    assert s.origin_city["ORY"] == "Paris"
    assert (s.depart_from.isoformat(), s.depart_to.isoformat(), s.return_date.isoformat()) == ("2027-05-05", "2027-05-05", "2027-05-22")
    assert s.max_stops == 2 and s.layover_hours == (3, 6) and s.no_airport_change


def test_example_config_has_a_flexible_search_around_the_wanted_date():
    wanted, flex = load_config("config.yaml").searches
    assert flex.return_date is None and flex.stay_days == [14, 15, 16, 17]
    assert flex.depart_from < wanted.depart_from < flex.depart_to  # fourchette d'environ 2 mois autour de la date voulue
    assert (flex.depart_to - flex.depart_from).days <= 62
    assert (flex.max_stops, flex.layover_hours, flex.no_airport_change) == (wanted.max_stops, wanted.layover_hours, wanted.no_airport_change)
    assert flex.origin_airports == wanted.origin_airports and flex.name != wanted.name


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


@pytest.mark.parametrize("value", [[6, 3], [3], "3-6", [-1, 2]])
def test_invalid_layover_hours_are_rejected(make_search, value):
    with pytest.raises(ValueError, match="layover_hours"):
        make_search(layover_hours=value)


def test_layover_filters(make_search):
    s = make_search(layover_hours=[3, 6], no_airport_change=True)
    assert s.layover_hours == (3.0, 6.0)
    assert passes_filters(s, 0, 800, "AF", [])
    assert passes_filters(s, 1, 900, "AF", [(180, "HKG", "HKG")])
    assert not passes_filters(s, 1, 900, "AF", [(179, "HKG", "HKG")])
    assert not passes_filters(s, 2, 900, "AF", [(200, "HKG", "HKG"), (361, "DOH", "DOH")])
    assert not passes_filters(s, 1, 900, "AF", [(240, "CDG", "ORY")])
    assert not passes_filters(s, 1, 900, "AF", None)  # escales non détaillées
    assert passes_filters(make_search(), 1, 900, "AF", None)  # sans critère d'escale, rien à vérifier
