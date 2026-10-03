from datetime import date

from conftest import quote

from tracker.analysis import analyze, arrow, change_vs
from tracker.expert import buying_window, easter, recommend, season_notes

TODAY = "2027-01-10"


def history(prices_by_day):
    return [quote(p, run_date=d) for d, p in prices_by_day.items()]


def test_arrow_and_change_vs():
    series = [("2027-01-01", 1000), ("2027-01-03", 900), ("2027-01-09", 800), ("2027-01-10", 820)]
    assert change_vs(series, TODAY, 1) == (20, 2.5, "↑")
    assert change_vs(series, TODAY, 7) == (-80, -8.9, "↓")
    assert change_vs(series, TODAY, 30) is None
    assert arrow(0.5) == "→"


def test_analyze_best_comparisons_and_alerts(search):
    today = [quote(650, TODAY), quote(800, TODAY, origin="MRS", dest="HND"),
             quote(700, TODAY, dep="2027-05-02", ret="2027-05-12", source="Autre")]
    past = history({"2027-01-08": 900, "2027-01-09": 700})
    a = analyze(search, today, past + today, TODAY)
    assert a["best"].price == 650
    assert [q.price for q in a["top"]] == [650, 700, 800]
    assert a["city_comparison"] == ["Partir de Barcelone coûte 150 € de moins que de Marseille"]
    assert {d: q.price for d, q in a["by_depart_date"].items()} == {"2027-05-01": 650, "2027-05-02": 700}
    assert a["changes"]["veille"] == (-50, -7.1, "↓")
    assert a["percentile"] == 0 and a["historical_min"] == 650
    assert any("seuil" in t for t in a["alerts"]) and any("Plus bas historique" in t for t in a["alerts"])


def test_analyze_without_quotes(search):
    assert analyze(search, [], [], TODAY) == {"best": None}


def test_easter_and_french_holidays():
    assert easter(2027) == date(2027, 3, 28)
    assert easter(2025) == date(2025, 4, 20)
    notes = season_notes(date(2027, 5, 3), ["NRT"])
    assert any("Golden Week" in n for n in notes) and any("1er mai" in n for n in notes)
    assert any("Ascension" in n for n in season_notes(date(2027, 5, 6), ["ICN"]))
    assert season_notes(date(2027, 5, 25), ["NRT"]) == []


def test_buying_window_is_earlier_in_peak_season():
    dep = date(2027, 5, 20)
    assert buying_window(dep, peak=False) == (date(2026, 11, 20), date(2027, 3, 20))
    assert buying_window(dep, peak=True)[0] < date(2026, 10, 1)


def advice(search, price, today, days_tracked=0, level=None, baseline=()):
    best = quote(price, dep="2027-05-26", ret="2027-06-05")  # hors jours fériés
    if level:
        best.price_level, best.typical_low, best.typical_high = level, 700, 1000
    a = {"best": best, "google": best if level else None, "percentile": None, "days_tracked": days_tracked, "changes": {}}
    return recommend(search, a, list(baseline), today)


def test_too_early_means_wait_unless_exceptional(search):
    r = advice(search, 900, date(2026, 10, 3), level="habituel")
    assert r["decision"] == "ATTENDRE" and "novembre" in r["window"]
    assert advice(search, 650, date(2026, 10, 3), level="bas")["decision"] == "ACHETER"


def test_in_window_low_price_buys_otherwise_monitors(search):
    assert advice(search, 650, date(2027, 1, 10), level="bas")["decision"] == "ACHETER"
    assert advice(search, 950, date(2027, 1, 10), level="habituel")["decision"] == "SURVEILLER"


def test_late_means_buy(search):
    assert advice(search, 1200, date(2027, 4, 15))["decision"] == "ACHETER"


def test_confidence_and_transparency_about_missing_data(search):
    poor = advice(search, 900, date(2027, 1, 10))
    assert poor["confidence"] == "faible"
    assert any("aucune donnée fiable" in t for t in poor["limits"])
    rich = advice(search, 900, date(2027, 1, 10), days_tracked=60, level="habituel", baseline=[{"price": 1000}])
    assert rich["confidence"] == "élevée" and rich["limits"] == []
