import json
from datetime import date

import pytest
from conftest import quote

from tracker.models import Context
from tracker.sources import google_flights as g

TODAY = date(2027, 1, 10)


def page(items_best, items_other=(), insight=True):
    def item(price, airlines, stops, minutes):
        return [["XX", airlines, [None] * (stops + 1), None, None, None, None, None, None, minutes], [[None, price]]]
    payload = [None] * 24
    payload[2] = [[item(*i) for i in items_best]] if items_best else None
    payload[3] = [[item(*i) for i in items_other]]
    if insight:
        payload[5] = [2, [None, 790], [None, 789], [None, -2], [None, 720], [None, 1000], 1, None, None, None,
                      [[[1785708000000, 683], [1791000000000, 790]]]]
    data = json.dumps(payload)
    return f"<html><script class=\"ds:1\">AF_initDataCallback({{key: 'ds:1', data:{data}, sideChannel: {{}}}});</script></html>"


def test_parse_reads_best_and_other_flights_and_price_insight():
    flights, insight = g.parse(page([(790, ["Swiss"], 1, 895)], [(1138, ["Qatar Airways", "JAL"], 2, 1300)]))
    assert flights == [
        {"price": 790, "airlines": "Swiss", "stops": 1, "duration_min": 895},
        {"price": 1138, "airlines": "Qatar Airways; JAL", "stops": 2, "duration_min": 1300},
    ]
    assert insight["low"] == 720 and insight["high"] == 1000
    assert insight["history"][0] == ("2026-08-03", 683)


def test_parse_without_insight_skips_flights_without_price():
    html = page([], [(900, ["AF"], 0, 800)], insight=False).replace("[[null, 900]]", "[]")
    html_ok = page([], [(900, ["AF"], 0, 800), (950, ["KL"], 0, 800)], insight=False).replace("[[null, 900]]", "[]")
    assert g.parse(html) == ([], None)
    assert [f["price"] for f in g.parse(html_ok)[0]] == [950]


def test_parse_consent_page_raises():
    with pytest.raises(ValueError, match="consentement"):
        g.parse("<html><title>Avant de continuer</title></html>")


def test_level():
    assert [g.level(p, 720, 1000) for p in (700, 800, 1100)] == ["bas", "habituel", "élevé"]


def test_plan_prioritises_yesterday_cheapest_then_open_jaw_then_sampling(search):
    ctx = Context("2027-01-10", previous=[quote(900), quote(650, origin="MRS", dest="HND", rf="KIX", rt="BCN")],
                  google_budget=500)
    probes = g.plan(search, ctx, TODAY)
    assert probes[:3] == [("ow", "MRS", "HND", "2027-05-01"), ("ow", "KIX", "BCN", "2027-05-11"),
                          ("rt", "BCN", "NRT", "2027-05-01", "2027-05-11")]
    assert len(probes) == len(set(probes))
    assert len([p for p in probes if p[0] == "rt"]) == 2 * 7 * 3  # 2 départs x 7 aéroports x 3 paires de dates


def test_plan_respects_budget(search):
    assert len(g.plan(search, Context("2027-01-10", google_budget=10), TODAY)) == 10


def test_collect_builds_round_trips_open_jaws_and_reports_failures(make_search):
    s = make_search(passengers=2, depart_to="2027-05-01", destination_airports=["NRT", "KIX"], max_stops=1)

    def fake_fetch(client, search, probe):
        if probe == ("rt", "MRS", "KIX", "2027-05-01", "2027-05-11"):
            raise RuntimeError("timeout")
        if probe[0] == "rt":
            flights = [{"price": 1600, "airlines": "Swiss", "stops": 1, "duration_min": 900},
                       {"price": 1000, "airlines": "Cheap", "stops": 3, "duration_min": 2000}]
            return flights, {"low": 1400, "high": 2000, "history": [("2026-12-01", 1500)]}, "https://g/rt"
        price = 500 if probe[1] in ("BCN", "MRS") else 300
        return [{"price": price, "airlines": "AF", "stops": 0, "duration_min": 800}], None, f"https://g/{probe[1]}"

    ctx = Context("2027-01-10", google_budget=50, google_pause=(0, 0))
    quotes, note = g.collect(s, ctx, fetch=fake_fetch, sleep=lambda _: None)
    rt = [q for q in quotes if q.kind == "aller-retour"]
    assert len(rt) == 3
    # prix par personne, vol à 3 escales filtré
    assert all(q.price == 800 and q.price_level == "habituel" and q.typical_low == 700 for q in rt)
    assert rt[0].history == [("2026-12-01", 750)]
    ow = [q for q in quotes if q.kind == "2 allers simples"]
    assert ("BCN", "KIX", "MRS") in {(q.origin, q.return_from, q.return_to) for q in ow}
    assert all(q.price == 400 for q in ow)
    assert "timeout" in note and note.startswith(f"{len(g.plan(s, ctx, TODAY)) - 1}/")


def test_collect_stops_when_blocked_and_raises_if_nothing(search):
    def blocked(*_):
        raise ValueError("page sans résultats (consentement ou blocage)")
    ctx = Context("2027-01-10", google_budget=50, google_pause=(0, 0))
    with pytest.raises(RuntimeError, match="arrêt après 5 échecs"):
        g.collect(search, ctx, fetch=blocked, sleep=lambda _: None)
