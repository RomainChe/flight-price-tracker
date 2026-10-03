from datetime import date

from tracker.models import Leg, combine_one_ways, date_pairs


def test_date_pairs_with_durations_and_fixed_return(make_search):
    pairs = date_pairs(make_search(stay_days=[10, 14]))
    assert pairs[:2] == [("2027-05-01", "2027-05-11"), ("2027-05-01", "2027-05-15")]
    assert len(pairs) == 6
    assert date_pairs(make_search(return_date="2027-05-02")) == [("2027-05-01", "2027-05-02")]


def test_date_pairs_skip_past_departures(search):
    assert [d for d, _ in date_pairs(search, today=date(2027, 5, 1))] == ["2027-05-02", "2027-05-03"]


def test_open_jaw_combines_cheapest_legs(search):
    outs = [Leg("G", "BCN", "NRT", "2027-05-01", 400), Leg("G", "BCN", "NRT", "2027-05-01", 380),
            Leg("G", "MRS", "HND", "2027-05-01", 500)]
    backs = [Leg("G", "KIX", "MRS", "2027-05-11", 300), Leg("G", "KIX", "MRS", "2027-05-20", 100)]
    quotes = combine_one_ways(search, outs, backs, "2027-01-10")
    best = min(quotes, key=lambda q: q.price)
    assert (best.origin, best.dest, best.return_from, best.return_to, best.price) == ("BCN", "NRT", "KIX", "MRS", 680)
    assert len(quotes) == 2  # le retour du 20 mai ne correspond à aucune durée configurée
