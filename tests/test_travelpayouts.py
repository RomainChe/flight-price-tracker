import pytest

from tracker.models import Context
from tracker.sources import travelpayouts as tp

ROUND_TRIPS = [
    {"origin_airport": "BCN", "destination_airport": "NRT", "price": 690, "airline": "LX", "transfers": 1,
     "departure_at": "2027-05-01T10:00:00+02:00", "return_at": "2027-05-11T12:00:00+09:00",
     "duration_to": 900, "link": "/search/BCN0105TYO11051"},
    {"origin_airport": "BCN", "destination_airport": "NRT", "price": 500, "airline": "SU", "transfers": 1,
     "departure_at": "2027-05-01T10:00:00+02:00", "return_at": "2027-05-11T12:00:00+09:00", "duration_to": 900},
    {"origin_airport": "BCN", "destination_airport": "NRT", "price": 400, "airline": "LX", "transfers": 1,
     "departure_at": "2027-05-01T10:00:00+02:00", "return_at": "2027-05-25T12:00:00+09:00", "duration_to": 900},
]


def fake_get(calls):
    def get(path, params, token):
        calls.append(params)
        route = (params["origin"], params["destination"], params["one_way"])
        if route == ("BCN", "TYO", "false"):
            return ROUND_TRIPS
        if route == ("MRS", "TYO", "true"):
            return [{"origin_airport": "MRS", "destination_airport": "HND", "price": 350, "airline": "AF",
                     "transfers": 1, "departure_at": "2027-05-02T09:00:00+02:00", "duration_to": 800}]
        if route == ("OSA", "BCN", "true"):
            return [{"origin_airport": "KIX", "destination_airport": "BCN", "price": 300, "airline": "QR",
                     "transfers": 1, "departure_at": "2027-05-12T09:00:00+09:00", "duration_to": 800}]
        return []
    return get


def test_collect_keeps_matching_round_trips_and_builds_open_jaws(make_search):
    calls = []
    s = make_search(excluded_airlines=["SU"])
    quotes, note = tp.collect(s, Context("2027-01-10", token="t"), get=fake_get(calls), sleep=lambda _: None)
    rt = [q for q in quotes if q.kind == "aller-retour"]
    # SU exclue, retour au 25 mai hors durées configurées
    assert [(q.price, q.link) for q in rt] == [(690, "https://www.aviasales.com/search/BCN0105TYO11051")]
    ow = [q for q in quotes if q.kind == "2 allers simples"]
    assert [(q.origin, q.dest, q.return_from, q.return_to, q.price) for q in ow] == [("MRS", "HND", "KIX", "BCN", 650)]
    assert {p["origin"] for p in calls} >= {"BCN", "MRS", "TYO", "OSA"}
    assert "requêtes réussies" in note


def test_cached_stays_close_to_wanted_duration_are_kept(make_search):
    # Réponse réelle du cache : 13 j et 22 j pour des durées voulues de 14 et 21 j.
    rows = [
        {"origin_airport": "BCN", "destination_airport": "NRT", "price": 831, "airline": "ZH", "transfers": 1,
         "departure_at": "2027-05-03T12:20:00+02:00", "return_at": "2027-05-16T19:00:00+09:00", "duration_to": 1040},
        {"origin_airport": "BCN", "destination_airport": "HND", "price": 769, "airline": "CA", "transfers": 1,
         "departure_at": "2027-05-02T12:30:00+02:00", "return_at": "2027-05-24T14:00:00+09:00", "duration_to": 895},
        {"origin_airport": "BCN", "destination_airport": "NRT", "price": 500, "airline": "XX", "transfers": 1,
         "departure_at": "2027-05-02T12:30:00+02:00", "return_at": "2027-05-30T14:00:00+09:00", "duration_to": 895},
    ]

    def get(path, params, token):
        return rows if params["one_way"] == "false" and params["origin"] == "BCN" and params["destination"] == "TYO" else []
    s = make_search(stay_days=[14, 21])
    quotes, _ = tp.collect(s, Context("2027-01-10", token="t"), get=get, sleep=lambda _: None)
    assert sorted((q.price, q.stay_days) for q in quotes) == [(769, 22), (831, 13)]  # 28 j : trop loin


def test_collect_without_token_fails_clearly(search):
    with pytest.raises(RuntimeError, match="TRAVELPAYOUTS_TOKEN"):
        tp.collect(search, Context("2027-01-10"))


def test_collect_all_requests_failing_raises(search):
    def down(*_):
        raise OSError("HTTP 503")
    with pytest.raises(RuntimeError, match="503"):
        tp.collect(search, Context("2027-01-10", token="t"), get=down, sleep=lambda _: None)


def test_baseline_queries_last_year_by_country_including_paris(search):
    calls = []

    def get(path, params, token):
        calls.append(params)
        return [{"origin": params["origin"], "destination": "TYO", "value": 820, "depart_date": "2026-05-04",
                 "return_date": "2026-05-18", "found_at": "2026-01-20T10:00:00Z"}]
    rows = tp.baseline(search, "t", get=get, sleep=lambda _: None)
    assert {c["origin"] for c in calls} == {"BCN", "MRS", "PAR"}
    assert all(c["destination"] == "JP" and c["beginning_of_period"] == "2026-05-01" for c in calls)
    assert rows[0]["price"] == 820 and rows[0]["found_at"] == "2026-01-20"
