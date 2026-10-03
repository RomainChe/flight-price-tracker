"""Google Flights via fast-flights : aucune clé, aucun quota payant.

fast-flights construit l'URL de recherche ; la lecture de la page est faite ici car
fast-flights ignore les « meilleurs vols » (payload[2]) et l'indicateur de prix (payload[5]).
Les open-jaw multi-destinations ne sont pas dans la page initiale : on les compose
avec deux allers simples.
"""
import json
import random
import time
from datetime import UTC, date, datetime

from fast_flights import FlightQuery, Passengers, create_query
from primp import Client
from selectolax.lexbor import LexborHTMLParser

from ..config import passes_filters
from ..models import Leg, Quote, combine_one_ways, date_pairs

NAME = "Google Flights"
URL = "https://www.google.com/travel/flights"
# Refus des cookies : sans lui, une IP européenne reçoit la page de consentement.
COOKIES = {"SOCS": "CAESHAgBEhJnd3NfMjAyMzA4MTAtMF9SQzIaAmZyIAEaBgiAo_CmBg"}
MAX_CONSECUTIVE_ERRORS = 5
SEEDS = 20  # combinaisons les moins chères de la veille re-vérifiées en priorité
OPEN_JAW_DATE_PAIRS = 1  # 2 x départs x aéroports requêtes par paire de dates


def _day(ms: int) -> str:
    """Horodatage Google (minuit dans un fuseau local) -> jour, quel que soit le fuseau de la machine."""
    return datetime.fromtimestamp(ms / 1000 + 12 * 3600, UTC).date().isoformat()


def parse(html: str) -> tuple[list[dict], dict | None]:
    """Page Google Flights -> (vols, indicateur de prix). Lève ValueError si la page n'a pas de résultats."""
    script = LexborHTMLParser(html).css_first(r"script.ds\:1")
    if script is None:
        raise ValueError("page sans résultats (consentement ou blocage)")
    data = script.text().split("data:", 1)[1].rsplit(",", 1)[0]
    if data.endswith("errorHasStatus: true"):
        return [], None
    payload = json.loads(data)
    flights = []
    for block in (payload[2], payload[3]):
        for item in (block[0] if block else None) or []:
            try:
                f, price = item[0], item[1][0][1]
            except (IndexError, TypeError):  # vol affiché sans prix
                continue
            if price:
                stops = len(f[2]) - 1
                layovers = [(l[0], l[1], l[2]) for l in (f[13] if len(f) > 13 else None) or []]
                flights.append({
                    "price": price, "airlines": "; ".join(f[1] or []), "stops": stops, "duration_min": f[9],
                    "layovers": layovers if layovers or not stops else None,  # None : escales non détaillées
                })
    insight = None
    s = payload[5] if len(payload) > 5 else None
    if s and s[4] and s[5]:
        history = s[10][0] if len(s) > 10 and s[10] else []
        insight = {
            "low": s[4][1], "high": s[5][1],
            "history": [(_day(ts), p) for ts, p in history],
        }
    return flights, insight


def layover_text(layovers) -> str:
    return ", ".join(f"{arr} {m // 60} h {m % 60:02d}" + (f" (→ {dep})" if dep != arr else "") for m, arr, dep in layovers or [])


def level(price: float, low: float, high: float) -> str:
    return "bas" if price < low else "élevé" if price > high else "habituel"


def plan(search, ctx, today: date) -> list[tuple]:
    """Requêtes du jour, par priorité : moins chères de la veille, moitié de l'échantillon tournant,
    open-jaw autour des meilleures dates, puis le reste de l'échantillon."""
    pairs = date_pairs(search, today)
    valid = set(pairs)
    origins, dests = search.origin_airports, search.dest_airports
    seeds = sorted(
        (q for q in ctx.previous + ctx.quotes_so_far
         if (q.depart_date, q.return_date) in valid and q.origin in origins and q.return_to in origins
         and q.dest in dests and q.return_from in dests),
        key=lambda q: q.price,
    )
    probes = []
    for q in seeds[:SEEDS]:
        if q.origin == q.return_to and q.dest == q.return_from:
            probes.append(("rt", q.origin, q.dest, q.depart_date, q.return_date))
        else:
            probes += [("ow", q.origin, q.dest, q.depart_date), ("ow", q.return_from, q.return_to, q.return_date)]

    rng = random.Random(today.toordinal())  # change chaque jour : toutes les dates finissent couvertes
    explore = [("rt", o, d, dep, ret) for o in origins for d in dests for dep, ret in pairs]
    rng.shuffle(explore)
    half = max(0, ctx.google_budget - len(probes)) // 2
    probes += explore[:half]

    best_pairs = list(dict.fromkeys((q.depart_date, q.return_date) for q in seeds)) or rng.sample(pairs, min(1, len(pairs)))
    for dep, ret in best_pairs[:OPEN_JAW_DATE_PAIRS]:
        probes += [("ow", o, d, dep) for o in origins for d in dests]
        probes += [("ow", d, o, ret) for d in dests for o in origins]
    return list(dict.fromkeys(probes + explore[half:]))[:ctx.google_budget]


def fetch(client, search, probe) -> tuple[list[dict], dict | None, str]:
    if probe[0] == "rt":
        _, o, d, dep, ret = probe
        legs, trip = [(o, d, dep), (d, o, ret)], "round-trip"
    else:
        _, a, b, day = probe
        legs, trip = [(a, b, day)], "one-way"
    # Durée max filtrée après coup : envoyée à Google, elle supprime l'indicateur de prix.
    # Durée d'escale envoyée à Google (s'applique aussi au retour, qu'on ne voit pas) et revérifiée après coup.
    lo, hi = (round(h * 60) for h in search.layover_hours) if search.layover_hours else (None, None)
    query = create_query(
        flights=[FlightQuery(date=day, from_airport=a, to_airport=b, min_layover_minutes=lo, max_layover_minutes=hi)
                 for a, b, day in legs],
        trip=trip, seat=search.cabin, passengers=Passengers(adults=search.passengers),
        currency=search.currency, language="fr", max_stops=search.max_stops,
        checked_bags=1 if search.checked_bag else 0,
    )
    html = client.get(URL, params=query.params(), cookies=COOKIES).text
    flights, insight = parse(html)
    return flights, insight, query.url()


def collect(search, ctx, fetch=fetch, sleep=time.sleep):
    today = date.fromisoformat(ctx.run_date)
    probes = plan(search, ctx, today)
    client = Client(impersonate="chrome_145", impersonate_os="macos", referer=True, cookie_store=True)
    pax = search.passengers
    quotes, outs, backs = [], [], []
    done = errors = consecutive = 0
    last_error = ""
    for i, probe in enumerate(probes):
        if i:
            sleep(random.uniform(*ctx.google_pause))
        try:
            flights, insight, url = fetch(client, search, probe)
            consecutive = 0
        except Exception as e:  # une requête ratée ne doit pas arrêter les autres
            errors, consecutive, last_error = errors + 1, consecutive + 1, str(e)
            if consecutive >= MAX_CONSECUTIVE_ERRORS:
                break
            continue
        finally:
            done += 1
        flights = [f for f in flights
                   if passes_filters(search, f["stops"], f["duration_min"], f["airlines"], f.get("layovers"))]
        if not flights:
            continue
        best = min(flights, key=lambda f: f["price"])
        price = round(best["price"] / pax, 2)
        if probe[0] == "ow":
            leg = Leg(NAME, probe[1], probe[2], probe[3], price, best["airlines"], best["stops"], best["duration_min"], url,
                      layover_text(best.get("layovers")))
            (outs if probe[1] in search.origin_airports else backs).append(leg)
            continue
        _, o, d, dep, ret = probe
        quote = Quote(
            run_date=ctx.run_date, search=search.name, source=NAME, kind="aller-retour",
            origin=o, dest=d, return_from=d, return_to=o, depart_date=dep, return_date=ret, price=price,
            airlines=best["airlines"], stops=best["stops"], duration_min=best["duration_min"], link=url,
        )
        if best.get("layovers"):
            quote.layovers = f"aller : {layover_text(best['layovers'])}"
        if insight:
            quote.typical_low, quote.typical_high = round(insight["low"] / pax, 2), round(insight["high"] / pax, 2)
            quote.price_level = level(quote.price, quote.typical_low, quote.typical_high)
            quote.history = [(day, round(p / pax, 2)) for day, p in insight["history"]]
        quotes.append(quote)
    quotes += combine_one_ways(search, outs, backs, ctx.run_date)

    note = f"{done - errors}/{len(probes)} requêtes réussies"
    if consecutive >= MAX_CONSECUTIVE_ERRORS:
        note += f", arrêt après {consecutive} échecs consécutifs"
    if errors:
        note += f" (dernière erreur : {last_error[:120]})"
    if not quotes and errors:
        raise RuntimeError(note)
    return quotes, note
