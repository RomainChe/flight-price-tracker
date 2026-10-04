---
name: nouvelle-source
description: Ajoute une source de prix de vols au Flight Price Tracker (nouveau module dans tracker/sources/). Utiliser quand on demande d'« ajouter une source », « brancher l'API X », « intégrer Kiwi / Skyscanner / … » dans le tracker. Pas pour modifier les trajets ou les seuils (skill flight-tracker).
---

# nouvelle-source

Une source est un module de `tracker/sources/` qui expose `NAME` et `collect(search, ctx) -> (quotes, note)`. Il est enregistré dans `sources.SOURCES`.

## Étapes

1. **Éligibilité** : la source doit être gratuite sans limite de temps, comme le reste du projet. Vérifie ses conditions sur sa documentation officielle. Si elle est payante au-delà d'un quota, dis-le avant d'écrire du code (voir « Sources écartées » dans `README.md`).
2. **Modèle** : lis `tracker/sources/travelpayouts.py` et `tracker/models.py` (`Quote`, `Leg`, `Context`, `date_pairs`, `matches_stay`, `combine_one_ways`).
3. **Module** `tracker/sources/<nom>.py` :
   - docstring d'en-tête : ce que la source apporte et ses limites ;
   - `NAME` lisible, affiché dans « État des sources » ;
   - `collect(search, ctx, get=get, sleep=time.sleep)` : appels réseau injectables, bibliothèque standard (`urllib`) plutôt qu'une nouvelle dépendance ;
   - filtres de `config` appliqués (`passes_filters`, `checks_layovers`) ;
   - prix toujours **par personne** ;
   - en cas d'erreur, lève une exception claire (`__main__` la capture), par exemple « secret X absent ».
4. **Enregistrement** : ajoute le module à `SOURCES` dans `tracker/sources/__init__.py`. L'ordre compte : Google Flights réutilise les meilleurs prix des sources placées avant lui.
5. **Secret éventuel** : ajoute-le à `.env.example` sans valeur, aux deux workflows (`daily.yml`, `search.yml`) et au tableau des variables de `docs/README.md`.
6. **Tests** `tests/test_<nom>.py` sur le modèle de `tests/test_travelpayouts.py` : un faux `get` qui enregistre les appels, aucun appel réseau. Couvre au minimum le prix par personne, les filtres, l'erreur et le secret absent.
7. **Vérifie** `python -m pytest -q`, puis propose un `python -m tracker --dry-run` à l'utilisateur, car il fait de vrais appels.
8. **Doc** : arborescence et flux dans `docs/architecture.md`, tableau « Sources de prix » dans `README.md`.

## Interdits

Pas de scraping contraire aux conditions d'utilisation, pas de nouvelle dépendance sans accord, aucun token dans le code ni dans les logs.
