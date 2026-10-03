"""Aviasales / Travelpayouts Data API : token gratuit, prix issus du cache des recherches des utilisateurs.

Un appel couvre un mois entier. Le cache ne propose que des allers-retours classiques :
les open-jaw sont composés avec deux allers simples.
"""
import json
import time
from datetime import date
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..airports import tp_city
from ..config import passes_filters
from ..models import Leg, Quote, combine_one_ways, date_pairs

NAME = "Aviasales / Travelpayouts"
API = "https://api.travelpayouts.com"
SITE = "https://www.aviasales.com"
PAUSE_SECONDS = 1.0


def get(path: str, params: dict, token: str) -> list:
    request = Request(f"{API}{path}?{urlencode(params)}", headers={"X-Access-Token": token})
    with urlopen(request, timeout=30) as response:
        body = json.load(response)
    if body.get("success") is False:
        raise RuntimeError(body.get("error") or "erreur de l'API")
    return body.get("data") or []


def _day(value: str) -> str:
    return (value or "")[:10]


def collect(search, ctx, get=get, sleep=time.sleep):
    if not ctx.token:
        raise RuntimeError("secret TRAVELPAYOUTS_TOKEN absent")
    if search.cabin != "economy":
        return [], "ignorée : le cache Travelpayouts ne couvre que la classe économique"
    pairs = date_pairs(search, date.fromisoformat(ctx.run_date))
    valid = set(pairs)
    dep_months = sorted({d[:7] for d, _ in pairs})
    ret_months = sorted({r[:7] for _, r in pairs})
    base = {"currency": search.currency.lower(), "sorting": "price", "limit": 1000, "unique": "false"}
    o_cities = sorted({tp_city(a) for a in search.origin_airports})
    d_cities = sorted({tp_city(a) for a in search.dest_airports})

    requests = [(o, d, m, "false") for o in o_cities for d in d_cities for m in dep_months]
    requests += [(o, d, m, "true") for o in o_cities for d in d_cities for m in dep_months]
    requests += [(d, o, m, "true") for o in o_cities for d in d_cities for m in ret_months]

    quotes, outs, backs = [], [], []
    errors, last_error = 0, ""
    for i, (origin, dest, month, one_way) in enumerate(requests):
        if i:
            sleep(PAUSE_SECONDS)
        params = {**base, "origin": origin, "destination": dest, "departure_at": month, "one_way": one_way}
        try:
            rows = get("/aviasales/v3/prices_for_dates", params, ctx.token)
        except Exception as e:
            errors, last_error = errors + 1, str(e)
            continue
        for r in rows:
            a, b = r.get("origin_airport") or r.get("origin"), r.get("destination_airport") or r.get("destination")
            airline, stops, minutes = r.get("airline", ""), r.get("transfers"), r.get("duration_to") or r.get("duration")
            if not r.get("price") or not passes_filters(search, stops, minutes, airline):
                continue
            link = SITE + r["link"] if r.get("link") else ""
            dep = _day(r.get("departure_at"))
            if one_way == "false":
                ret = _day(r.get("return_at"))
                if (dep, ret) in valid and a in search.origin_airports and b in search.dest_airports:
                    quotes.append(Quote(
                        run_date=ctx.run_date, search=search.name, source=NAME, kind="aller-retour",
                        origin=a, dest=b, return_from=b, return_to=a, depart_date=dep, return_date=ret,
                        price=float(r["price"]), airlines=airline, stops=stops, duration_min=minutes, link=link,
                    ))
            else:
                (outs if a in search.origin_airports else backs).append(
                    Leg(NAME, a, b, dep, float(r["price"]), airline, stops, minutes, link))
    quotes += combine_one_ways(search, outs, backs, ctx.run_date)

    note = f"{len(requests) - errors}/{len(requests)} requêtes réussies, données du cache (peuvent dater de quelques jours)"
    if errors:
        note += f" (dernière erreur : {last_error[:120]})"
    if errors == len(requests):
        raise RuntimeError(note)
    return quotes, note


def baseline(search, token: str, get=get, sleep=time.sleep) -> list[dict]:
    """Prix trouvés l'an passé pour les mêmes mois de départ (référence saisonnière), depuis BCN, les départs configurés et Paris."""
    months = sorted({d[:7] for d, _ in date_pairs(search)})
    origins = sorted({tp_city(a) for a in search.origin_airports} | {"PAR", "BCN"})
    dests = [search.dest_country] if search.dest_country else sorted({tp_city(a) for a in search.dest_airports})
    rows = []
    for origin in origins:
        for dest in dests:
            for month in months:
                last_year = f"{int(month[:4]) - 1}{month[4:]}-01"
                params = {
                    "currency": search.currency.lower(), "origin": origin, "destination": dest,
                    "period_type": "month", "beginning_of_period": last_year, "one_way": "false",
                    "show_to_affiliates": "false", "sorting": "price", "limit": 1000,
                }
                for r in get("/v2/prices/latest", params, token):
                    if r.get("value") and r.get("depart_date"):
                        rows.append({
                            "search": search.name, "source": NAME, "origin": r.get("origin", origin),
                            "dest": r.get("destination", dest), "depart_date": r["depart_date"],
                            "return_date": r.get("return_date") or "", "found_at": _day(r.get("found_at")),
                            "price": float(r["value"]),
                        })
                sleep(PAUSE_SECONDS)
    return rows
