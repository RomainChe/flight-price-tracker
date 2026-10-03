"""Recherche ponctuelle lancée depuis le formulaire GitHub (workflow « Recherche ponctuelle »).

Les champs arrivent en variables d'environnement SEARCH_*. La recherche passe par la même
validation que config.yaml, envoie l'e-mail, mais ne lit ni n'écrit l'historique.

python -m tracker.adhoc
"""
import os
import sys

import yaml

from .__main__ import ROOT, run


def _num(env, key, label, cast=float):
    value = (env.get(key) or "").strip().replace(",", ".")
    if not value:
        return None
    try:
        return cast(value)
    except ValueError:
        raise ValueError(f"{label} : nombre attendu, reçu « {value} ».") from None


def config_from_env(env) -> dict:
    def text(key):
        return (env.get(key) or "").strip()

    def items(key):
        return [x.strip() for x in text(key).split(",") if x.strip()]

    destination = text("SEARCH_DESTINATION")
    search = {
        "name": f"Recherche ponctuelle : {destination}",
        "origins": items("SEARCH_ORIGINS"),
        "destination": destination,
        "depart_from": text("SEARCH_DEPART_FROM"),
        "depart_to": text("SEARCH_DEPART_TO") or text("SEARCH_DEPART_FROM"),
        "passengers": _num(env, "SEARCH_PASSENGERS", "Passagers", int) or 1,
        "cabin": text("SEARCH_CABIN") or "economy",
        "checked_bag": text("SEARCH_CHECKED_BAG") == "true",
        "no_airport_change": text("SEARCH_NO_AIRPORT_CHANGE") == "true",
        "excluded_airlines": items("SEARCH_EXCLUDED_AIRLINES"),
        "currency": text("SEARCH_CURRENCY") or "EUR",
    }
    if text("SEARCH_RETURN_DATE"):
        search["return_date"] = text("SEARCH_RETURN_DATE")
    if text("SEARCH_STAY_DAYS"):
        try:
            search["stay_days"] = [int(x) for x in items("SEARCH_STAY_DAYS")]
        except ValueError:
            raise ValueError(f"Durées de séjour : nombres de jours séparés par des virgules, reçu « {text('SEARCH_STAY_DAYS')} ».") from None
    if text("SEARCH_MAX_STOPS") not in ("", "illimité"):
        search["max_stops"] = _num(env, "SEARCH_MAX_STOPS", "Escales max", int)
    low, high = _num(env, "SEARCH_LAYOVER_MIN_HOURS", "Escale min"), _num(env, "SEARCH_LAYOVER_MAX_HOURS", "Escale max")
    if low is not None or high is not None:
        search["layover_hours"] = [low or 0, high if high is not None else 24]
    for key, field, label in (("SEARCH_MAX_DURATION_HOURS", "max_duration_hours", "Durée max"),
                              ("SEARCH_ALERT_BELOW", "alert_below", "Seuil d'alerte")):
        if (value := _num(env, key, label)) is not None:
            search[field] = value
    return {"email": {"subject": f"Recherche ponctuelle {destination}"}, "searches": [search]}


def main(env=os.environ):
    path = ROOT / "out" / "recherche-ponctuelle.yaml"
    try:
        config = config_from_env(env)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(path.read_text(encoding="utf-8"))
        run(path, dry_run=env.get("DRY_RUN") == "true", env=env, keep_history=False)
    except ValueError as e:
        sys.exit(f"Recherche invalide : {e}")


if __name__ == "__main__":
    main()
