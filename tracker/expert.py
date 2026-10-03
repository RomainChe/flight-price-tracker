"""Module « expert » : acheter maintenant ou attendre ? Règles calculées en code, sans IA.

# ponytail: barème de points fait main ; à recalibrer quand l'historique couvrira une saison entière.
"""
from datetime import date, timedelta
from statistics import median

from .airports import COUNTRIES

MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
          "septembre", "octobre", "novembre", "décembre"]
# Fenêtre d'achat long-courrier Europe -> Asie, en mois avant le départ (règle générale du secteur).
WINDOW_NORMAL = (6, 2)
WINDOW_PEAK = (8, 4)
JAPAN = set(COUNTRIES["japon"][1])


def easter(year: int) -> date:
    """Dimanche de Pâques (algorithme grégorien anonyme)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    wd = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * wd) // 451
    month, day = divmod(h + wd - 7 * m + 114, 31)
    return date(year, month, day + 1)


def french_holidays(year: int) -> dict[date, str]:
    e = easter(year)
    return {
        date(year, 1, 1): "Jour de l'an", e + timedelta(days=1): "lundi de Pâques",
        date(year, 5, 1): "1er mai", date(year, 5, 8): "8 mai", e + timedelta(days=39): "Ascension",
        e + timedelta(days=50): "lundi de Pentecôte", date(year, 7, 14): "14 juillet",
        date(year, 8, 15): "15 août", date(year, 11, 1): "Toussaint", date(year, 11, 11): "11 novembre",
        date(year, 12, 25): "Noël",
    }


def season_notes(dep: date, dest_airports) -> list[str]:
    notes = []
    if JAPAN & set(dest_airports) and (date(dep.year, 4, 29) <= dep <= date(dep.year, 5, 5)):
        notes.append("départ pendant la Golden Week au Japon (29 avril – 5 mai) : forte demande et hôtels chers")
    near = [name for day, name in french_holidays(dep.year).items() if abs((day - dep).days) <= 3]
    if near:
        notes.append(f"départ proche d'un jour férié en France ({', '.join(near)}) : ponts, demande plus forte")
    return notes


def month_part(d: date, with_year: bool) -> str:
    part = "début" if d.day <= 10 else "mi" if d.day <= 20 else "fin"
    text = f"{part}-{MONTHS[d.month - 1]}" if part == "mi" else f"{part} {MONTHS[d.month - 1]}"
    return f"{text} {d.year}" if with_year else text


def months_before(d: date, n: int) -> date:
    y, m = divmod(d.year * 12 + d.month - 1 - n, 12)
    return date(y, m + 1, min(d.day, 28))


def buying_window(dep: date, peak: bool) -> tuple[date, date]:
    early, late = WINDOW_PEAK if peak else WINDOW_NORMAL
    return months_before(dep, early), months_before(dep, late)


def recommend(search, analysis: dict, baseline: list[dict], today: date) -> dict:
    best = analysis.get("best")
    if not best:
        return {"decision": "SURVEILLER", "confidence": "faible", "window": "", "reasons": ["Aucun prix trouvé aujourd'hui."], "limits": []}
    dep = date.fromisoformat(best.depart_date)
    notes = season_notes(dep, search.dest_airports)
    start, end = buying_window(dep, peak=bool(notes))
    window = f"entre {month_part(start, start.year != end.year)} et {month_part(end, True)}"
    score, reasons, limits = 0, [], []

    if search.alert_below and best.price < search.alert_below:
        score += 2
        reasons.append(f"le prix ({best.price:.0f} €) est sous ton seuil de {search.alert_below:.0f} €")
    g = analysis.get("google")
    if g:
        if g.price_level == "bas":
            score += 2
        elif g.price_level == "élevé":
            score -= 1
        reasons.append(f"Google juge ce prix {g.price_level} (fourchette habituelle {g.typical_low:.0f}–{g.typical_high:.0f} €)")
        if len(g.history) >= 14:
            old = median(p for _, p in g.history[:14])
            pct = (g.history[-1][1] - old) / old * 100
            if abs(pct) >= 3:
                reasons.append(f"selon Google, ce trajet a {'augmenté' if pct > 0 else 'baissé'} de {abs(pct):.0f} % en {len(g.history)} jours")
                score += 1 if pct > 0 else -1
    else:
        limits.append("indicateur de prix Google indisponible aujourd'hui")

    if analysis.get("percentile") is not None and analysis["days_tracked"] >= 7:
        p = analysis["percentile"]
        score += 1 if p <= 20 else -1 if p >= 80 else 0
        reasons.append(f"le prix du jour est au {p}e percentile de nos {analysis['days_tracked']} jours de relevés")
    week = (analysis.get("changes") or {}).get("7 jours")
    if week and abs(week[1]) >= 3:
        score += 1 if week[1] > 0 else -1
        reasons.append(f"tendance sur 7 jours : {week[0]:+} € ({week[1]:+} %)")

    last_year = [r["price"] for r in baseline]
    if last_year:
        ref = median(last_year)
        if best.price < ref * 0.9:
            score += 1
        elif best.price > ref * 1.1:
            score -= 1
        reasons.append(f"l'an dernier, les prix relevés pour ces dates tournaient autour de {ref:.0f} € ({len(last_year)} relevés)")
    else:
        limits.append("aucune donnée fiable de l'an dernier pour ce trajet : on applique les règles générales du secteur")

    reasons += notes
    if today < start:
        decision = "ACHETER" if score >= 3 else "ATTENDRE"
        reasons.append(f"il est tôt : pour un long-courrier, la fenêtre habituelle est {window}")
    elif today <= end:
        decision = "ACHETER" if score >= 2 else "SURVEILLER"
        reasons.append(f"on est dans la fenêtre d'achat habituelle ({window})")
    else:
        decision = "ACHETER"
        reasons.append("le départ approche : les prix montent en général fortement dans les deux derniers mois")

    data_points = (analysis["days_tracked"] >= 14) + (analysis["days_tracked"] >= 45) + bool(g) + bool(last_year)
    confidence = "élevée" if data_points >= 3 else "moyenne" if data_points == 2 else "faible"
    if analysis["days_tracked"] < 14:
        limits.append(f"seulement {analysis['days_tracked']} jour(s) d'historique : la précision augmentera avec les relevés")
    return {"decision": decision, "confidence": confidence, "window": window, "reasons": reasons, "limits": limits, "score": score}
