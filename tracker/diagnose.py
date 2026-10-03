"""Diagnostic Travelpayouts : affiche la réponse brute de l'API (jamais le token).

python -m tracker.diagnose
"""
import json
import os
from datetime import date

from .sources.travelpayouts import get


def main():
    token = os.environ.get("TRAVELPAYOUTS_TOKEN", "")
    if not token:
        raise SystemExit("TRAVELPAYOUTS_TOKEN absent.")
    today = date.today()
    next_month = date(today.year + today.month // 12, today.month % 12 + 1, 1).strftime("%Y-%m")
    checks = [
        ("trajet très demandé, mois prochain", "/aviasales/v3/prices_for_dates",
         {"origin": "PAR", "destination": "BCN", "departure_at": next_month, "one_way": "false", "currency": "eur", "limit": 3}),
        ("recherche suivie", "/aviasales/v3/prices_for_dates",
         {"origin": "BCN", "destination": "TYO", "departure_at": "2027-05", "one_way": "false", "currency": "eur", "limit": 3}),
        ("prix trouvés l'an dernier", "/v2/prices/latest",
         {"origin": "BCN", "destination": "JP", "period_type": "month", "beginning_of_period": "2026-05-01",
          "one_way": "false", "show_to_affiliates": "false", "currency": "eur", "limit": 3}),
    ]
    for label, path, params in checks:
        print(f"\n== {label} : {path} {params}")
        try:
            rows = get(path, params, token)
            print(f"{len(rows)} résultat(s)")
            for row in rows[:3]:
                print(json.dumps(row, ensure_ascii=False))
        except Exception as e:
            print(f"ERREUR : {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
