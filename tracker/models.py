"""Modèle commun à toutes les sources : un prix aller-retour relevé un jour donné."""
from dataclasses import dataclass, field
from datetime import date, timedelta


@dataclass
class Quote:
    run_date: str
    search: str
    source: str
    kind: str  # "aller-retour" ou "2 allers simples"
    origin: str
    dest: str
    return_from: str
    return_to: str
    depart_date: str
    return_date: str
    price: float  # par personne
    airlines: str = ""
    stops: int | None = None  # escales à l'aller
    duration_min: int | None = None  # durée de l'aller
    link: str = ""
    price_level: str = ""  # indicateur Google : bas / habituel / élevé
    typical_low: float | None = None
    typical_high: float | None = None
    history: list = field(default_factory=list, repr=False, compare=False)  # non stocké
    layovers: str = field(default="", compare=False)  # détail affiché dans l'e-mail, non stocké

    @property
    def combo(self) -> tuple:
        return (self.origin, self.dest, self.return_from, self.return_to, self.depart_date, self.return_date)

    @property
    def stay_days(self) -> int:
        return (date.fromisoformat(self.return_date) - date.fromisoformat(self.depart_date)).days


@dataclass
class Context:
    """Ce qu'une source reçoit en plus de la recherche."""
    run_date: str
    previous: list[Quote] = field(default_factory=list)  # relevés de la veille pour cette recherche
    quotes_so_far: list[Quote] = field(default_factory=list)  # relevés du jour des sources déjà passées
    google_budget: int = 150
    google_pause: tuple[float, float] = (2.0, 5.0)
    token: str = ""


@dataclass
class Leg:
    """Aller simple, utilisé pour composer les open-jaw."""
    source: str
    origin: str
    dest: str
    date: str
    price: float
    airlines: str = ""
    stops: int | None = None
    duration_min: int | None = None
    link: str = ""
    layovers: str = ""


def date_pairs(search, today: date | None = None) -> list[tuple[str, str]]:
    """Toutes les paires (aller, retour) de la recherche, sans les départs déjà passés."""
    pairs = []
    day = max(search.depart_from, today + timedelta(days=1)) if today else search.depart_from
    while day <= search.depart_to:
        if search.return_date:
            if search.return_date > day:
                pairs.append((day.isoformat(), search.return_date.isoformat()))
        else:
            pairs += [(day.isoformat(), (day + timedelta(days=n)).isoformat()) for n in search.stay_days]
        day += timedelta(days=1)
    return pairs


def matches_stay(search, dep: str, ret: str, tolerance: int = 0) -> bool:
    """Le séjour dep -> ret correspond-il à la recherche, à `tolerance` jours près ?"""
    if not dep or not ret:
        return False
    d, r = date.fromisoformat(dep), date.fromisoformat(ret)
    if not search.depart_from <= d <= search.depart_to or r <= d:
        return False
    if search.return_date:
        return abs((r - search.return_date).days) <= tolerance
    return any(abs((r - d).days - n) <= tolerance for n in search.stay_days)


def combine_one_ways(search, outs: list[Leg], backs: list[Leg], run_date: str, tolerance: int = 0,
                     kind="2 allers simples") -> list[Quote]:
    """Assemble allers et retours simples en aller-retour (open-jaw compris), le moins cher par combinaison."""
    best_out: dict = {}
    for leg in outs:
        key = (leg.origin, leg.dest, leg.date)
        if key not in best_out or leg.price < best_out[key].price:
            best_out[key] = leg
    best_back: dict = {}
    for leg in backs:
        key = (leg.origin, leg.dest, leg.date)
        if key not in best_back or leg.price < best_back[key].price:
            best_back[key] = leg
    quotes = []
    for (o, d, dep), out in best_out.items():
        for (rf, rt, ret), back in best_back.items():
            if not matches_stay(search, dep, ret, tolerance) or rf not in search.dest_airports or rt not in search.origin_airports:
                continue
            quotes.append(Quote(
                run_date=run_date, search=search.name, source=out.source, kind=kind,
                origin=o, dest=d, return_from=rf, return_to=rt, depart_date=dep, return_date=ret,
                price=round(out.price + back.price, 2),
                airlines=" + ".join(dict.fromkeys(a for a in (out.airlines, back.airlines) if a)),
                stops=out.stops, duration_min=out.duration_min,
                link=" | ".join(x for x in (out.link, back.link) if x),
                layovers=" · ".join(f"{label} : {leg.layovers}" for label, leg in (("aller", out), ("retour", back)) if leg.layovers),
            ))
    return quotes


def keep_cheapest(quotes: list[Quote]) -> list[Quote]:
    """Une seule offre par (source, combinaison) : la moins chère."""
    best: dict = {}
    for q in quotes:
        key = (q.source, q.combo)
        if key not in best or q.price < best[key].price:
            best[key] = q
    return list(best.values())
