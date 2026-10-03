"""Lecture et validation de config.yaml."""
import re
from dataclasses import dataclass, field
from datetime import date

import yaml

from .airports import resolve_destination, resolve_origin

CABINS = {"economy", "premium-economy", "business", "first"}


@dataclass
class Search:
    name: str
    origins: list[str]  # libellés saisis (ex. Barcelone)
    origin_airports: list[str]
    origin_city: dict  # aéroport -> libellé de ville
    destination: str
    dest_airports: list[str]
    dest_country: str | None
    depart_from: date
    depart_to: date
    stay_days: list[int] = field(default_factory=list)
    return_date: date | None = None
    passengers: int = 1
    cabin: str = "economy"
    currency: str = "EUR"
    max_stops: int | None = None
    max_duration_hours: float | None = None
    checked_bag: bool = False
    excluded_airlines: list[str] = field(default_factory=list)
    alert_below: float | None = None


@dataclass
class Config:
    searches: list[Search]
    google_max_requests: int = 150
    google_pause_seconds: tuple[float, float] = (2.0, 5.0)
    email_subject: str = "Suivi des prix des vols"


def _date(value, label) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ValueError(f"{label} : date invalide « {value} » (format attendu AAAA-MM-JJ).") from None


def _search(raw: dict, defaults: dict) -> Search:
    raw = {**defaults, **raw}
    name = raw.get("name") or "Recherche"
    origins = raw.get("origins") or []
    if isinstance(origins, str):
        origins = [origins]
    if not origins or not raw.get("destination"):
        raise ValueError(f"{name} : `origins` et `destination` sont obligatoires.")
    origin_city = {}
    for label in origins:
        for code in resolve_origin(label):
            origin_city[code] = str(label)
    if raw.get("destination_airports"):
        dest_airports, country = [c.upper() for c in raw["destination_airports"]], None
    else:
        dest_airports, country = resolve_destination(raw["destination"])

    start, end = _date(raw.get("depart_from"), f"{name}.depart_from"), _date(raw.get("depart_to"), f"{name}.depart_to")
    if end < start:
        raise ValueError(f"{name} : depart_to est avant depart_from.")
    return_date = _date(raw["return_date"], f"{name}.return_date") if raw.get("return_date") else None
    stay_days = [int(d) for d in raw.get("stay_days") or []]
    if not return_date and not stay_days:
        raise ValueError(f"{name} : indique `stay_days` (ex. [10, 14]) ou `return_date`.")
    if any(d <= 0 for d in stay_days):
        raise ValueError(f"{name} : les durées de séjour doivent être positives.")
    cabin = raw.get("cabin", "economy")
    if cabin not in CABINS:
        raise ValueError(f"{name} : classe inconnue « {cabin} » ({', '.join(sorted(CABINS))}).")
    passengers = int(raw.get("passengers", 1))
    if not 1 <= passengers <= 9:
        raise ValueError(f"{name} : de 1 à 9 passagers.")

    return Search(
        name=name, origins=[str(o) for o in origins], origin_airports=list(origin_city), origin_city=origin_city,
        destination=str(raw["destination"]), dest_airports=dest_airports, dest_country=country,
        depart_from=start, depart_to=end, stay_days=stay_days, return_date=return_date,
        passengers=passengers, cabin=cabin, currency=str(raw.get("currency", "EUR")).upper(),
        max_stops=raw.get("max_stops"), max_duration_hours=raw.get("max_duration_hours"),
        checked_bag=bool(raw.get("checked_bag", False)),
        excluded_airlines=[str(a) for a in raw.get("excluded_airlines") or []],
        alert_below=raw.get("alert_below"),
    )


def load_config(path) -> Config:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    defaults = raw.get("defaults") or {}
    searches = [_search(s, defaults) for s in raw.get("searches") or []]
    if not searches:
        raise ValueError("config.yaml : aucune recherche dans `searches`.")
    if len({s.name for s in searches}) != len(searches):
        raise ValueError("config.yaml : chaque recherche doit avoir un `name` unique.")
    google = raw.get("google") or {}
    pause = google.get("pause_seconds", [2, 5])
    return Config(
        searches=searches,
        google_max_requests=int(google.get("max_requests", 150)),
        google_pause_seconds=(float(pause[0]), float(pause[1])),
        email_subject=(raw.get("email") or {}).get("subject", "Suivi des prix des vols"),
    )


def airline_excluded(search: Search, airlines: str) -> bool:
    """Compare nom ou code IATA, à l'identique (Google donne des noms, Travelpayouts des codes)."""
    tokens = {t.strip().lower() for t in re.split(r"[;,+]", airlines)}
    return any(a.strip().lower() in tokens for a in search.excluded_airlines)


def passes_filters(search: Search, stops, duration_min, airlines) -> bool:
    if search.max_stops is not None and stops is not None and stops > search.max_stops:
        return False
    if search.max_duration_hours and duration_min and duration_min > search.max_duration_hours * 60:
        return False
    return not airline_excluded(search, airlines)
