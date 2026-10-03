"""Meilleurs prix du jour, comparaisons et tendance."""
from datetime import date, timedelta
from statistics import mean

from .models import Quote

STABLE_PCT = 1.0  # en dessous, la variation est affichée comme stable


def arrow(pct: float) -> str:
    return "↑" if pct > STABLE_PCT else "↓" if pct < -STABLE_PCT else "→"


def cheapest_per(quotes: list[Quote], key) -> dict:
    best: dict = {}
    for q in quotes:
        k = key(q)
        if k not in best or q.price < best[k].price:
            best[k] = q
    return dict(sorted(best.items()))


def daily_minima(history: list[Quote]) -> list[tuple[str, float]]:
    return sorted((day, q.price) for day, q in cheapest_per(history, lambda q: q.run_date).items())


def change_vs(series: list[tuple[str, float]], today: str, days: int):
    """(écart €, écart %, flèche) entre aujourd'hui et le dernier relevé datant d'au moins `days` jours."""
    limit = (date.fromisoformat(today) - timedelta(days=days)).isoformat()
    current = dict(series).get(today)
    past = [p for d, p in series if d <= limit]
    if current is None or not past:
        return None
    delta = current - past[-1]
    pct = delta / past[-1] * 100
    return round(delta), round(pct, 1), arrow(pct)


def analyze(search, today_quotes: list[Quote], history: list[Quote], run_date: str) -> dict:
    """`history` contient tous les relevés stockés de la recherche, y compris ceux du jour."""
    if not today_quotes:
        return {"best": None}
    ranked = sorted(cheapest_per(today_quotes, lambda q: q.combo).values(), key=lambda q: q.price)
    best = ranked[0]
    by_city = cheapest_per(today_quotes, lambda q: search.origin_city.get(q.origin, q.origin))
    city_rank = sorted(by_city.items(), key=lambda kv: kv[1].price)
    comparison = [
        f"Partir de {city_rank[0][0]} coûte {round(q.price - city_rank[0][1].price)} € de moins que de {city}"
        for city, q in city_rank[1:]
    ]

    series = daily_minima(history)
    past = [p for d, p in series if d < run_date]
    google = [q for q in ranked if q.price_level]
    alerts = []
    if search.alert_below and best.price < search.alert_below:
        alerts.append(f"Prix sous le seuil d'alerte : {best.price:.0f} € < {search.alert_below:.0f} €")
    if past and best.price < min(past):
        alerts.append(f"Plus bas historique : {best.price:.0f} € (précédent : {min(past):.0f} €)")

    return {
        "best": best,
        "top": ranked[:5],
        "by_city": by_city,
        "city_comparison": comparison,
        "by_depart_date": cheapest_per(today_quotes, lambda q: q.depart_date),
        "by_stay": cheapest_per(today_quotes, lambda q: q.stay_days),
        "series": series,
        "changes": {label: change_vs(series, run_date, n) for label, n in (("veille", 1), ("7 jours", 7), ("30 jours", 30))},
        "moving_avg_7": round(mean(p for _, p in series[-7:])) if series else None,
        "historical_min": min(p for _, p in series) if series else None,
        "percentile": round(sum(p <= best.price for p in past) / len(past) * 100) if past else None,
        "days_tracked": len(series),
        "google": google[0] if google else None,
        "alerts": alerts,
    }
