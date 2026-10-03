"""Sources de prix. Chaque module expose NAME et collect(search, ctx) -> (quotes, note).

Pour ajouter une source (gratuite sans limite de temps), créer un module et l'ajouter ici.
L'ordre compte : Google Flights réutilise les meilleurs prix déjà trouvés par Travelpayouts.
"""
from . import google_flights, travelpayouts

SOURCES = [travelpayouts, google_flights]
